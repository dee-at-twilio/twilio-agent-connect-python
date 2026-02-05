"""Core TAC (Twilio Agent Connect) class for processing events and configuration."""

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from typing import Any, Optional, Union

from fastapi import Response
from fastapi.datastructures import FormData
from pydantic import ValidationError

from tac.context.conversation import ConversationClient
from tac.context.knowledge import KnowledgeClient
from tac.context.memory import MemoryClient
from tac.core.config import TACConfig
from tac.core.logging import get_logger, setup_logging
from tac.intelligence.operator_result_processor import OperatorResultProcessor
from tac.models.intelligence import OperatorProcessingResult
from tac.models.memory import (
    ProfileLookupResponse,
    ProfileResponse,
)
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse


class TAC:
    _handoff_callback: Optional[Callable[[FormData], Awaitable[Response]]] = None

    def on_handoff(
        self,
        callback: Callable[[FormData], Awaitable[Response]],
    ) -> None:
        """
        Register a callback to be invoked when a handoff event occurs (e.g., Flex handoff).

        The callback will be triggered by the channel when a handoff is required.
        Supports both synchronous and asynchronous callbacks.
        """
        self._handoff_callback = callback

    """
    Main Twilio Agent Connect class for processing webhook events with configuration.

    This class accepts configuration and provides methods to process webhook events.
    """

    def __init__(self, config: Union[TACConfig, dict[str, Any]]):
        """
        Initialize TAC instance with configuration.

        Args:
            config: TACConfig instance or dictionary with configuration settings

        Raises:
            ValueError: If config is invalid
        """
        # Parse and validate configuration
        if isinstance(config, dict):
            try:
                self.config = TACConfig(**config)
            except ValidationError as e:
                raise ValueError(f"Invalid configuration: {e}") from e
        elif isinstance(config, TACConfig):
            self.config = config
        else:
            raise ValueError("Config must be TACConfig instance or dictionary")

        # Setup logging
        setup_logging(log_level=self.config.log_level, log_format="console")
        self.logger = get_logger(__name__)

        # Initialize Memora client only if memory config is provided
        self.memora_client: Optional[MemoryClient] = None
        if self.config.twilio_memory_config:
            self.memora_client = MemoryClient(
                base_url=self.config.memora_base_url,
                store_id=self.config.twilio_memory_config.memory_store_id,
                api_key=self.config.twilio_memory_config.api_key,
                api_token=self.config.twilio_memory_config.api_token,
            )
            self.logger.info("Twilio Memory client initialized")

        # Initialize Knowledge client only if memory config is provided
        # Knowledge client uses the same authentication as Memory client
        self.knowledge_client: Optional[KnowledgeClient] = None
        if self.config.twilio_memory_config:
            self.knowledge_client = KnowledgeClient(
                base_url=self.config.knowledge_base_url,
                api_key=self.config.twilio_memory_config.api_key,
                api_token=self.config.twilio_memory_config.api_token,
            )
            self.logger.info("Twilio Knowledge client initialized")

        self.maestro_client = ConversationClient(
            base_url=self.config.maestro_base_url,
            account_sid=self.config.twilio_account_sid,
            auth_token=self.config.twilio_auth_token,
            service_id=self.config.conversation_service_sid,
        )

        # Initialize CI processor if both memory and CI config are provided
        self.ci_processor: Optional[OperatorResultProcessor] = None
        if self.memora_client and self.config.conversation_intelligence_config:
            self.ci_processor = OperatorResultProcessor(
                memory_client=self.memora_client,
                config=self.config.conversation_intelligence_config,
            )
            self.logger.info("Conversation Intelligence processor initialized")

        # Callback for when message is ready (supports both sync and async)
        self._message_ready_callback: Optional[
            Union[
                Callable[[str, ConversationSession, Optional[TACMemoryResponse]], None],
                Callable[[str, ConversationSession, Optional[TACMemoryResponse]], Awaitable[None]],
            ]
        ] = None

        # Callback for when user interrupts the agent (supports both sync and async)
        self._interrupt_callback: Optional[
            Union[
                Callable[[ConversationSession, Any], None],
                Callable[[ConversationSession, Any], Awaitable[None]],
            ]
        ] = None

    def is_twilio_memory_enabled(self) -> bool:
        """
        Check if Twilio Memory functionality is enabled.

        Returns:
            True if twilio_memory_config is provided and memory client is initialized,
            False otherwise.
        """
        return self.config.twilio_memory_config is not None

    async def retrieve_memory(
        self,
        conversation_context: ConversationSession,
        query: Optional[str] = None,
    ) -> TACMemoryResponse:
        """
        Retrieve memories from Memory Service or fallback to Maestro Communications API.

        This method implements a lenient, graceful degradation strategy for memory retrieval.
        All failures in profile lookup and fetching are logged at WARNING level and handled
        gracefully without raising exceptions.

        Args:
            conversation_context: Conversation context containing conversation_id, profile_id,
                and optional author_info. This object will be mutated to populate profile_id
                (via automatic lookup) and profile (via automatic fetch) if not already present.
            query: Optional semantic search query for memory retrieval (only used with Memory)

        Returns:
            TACMemoryResponse: Unified wrapper providing access to memory data.

            When Memory is available (with profile_id):
            - observations, summaries, and communications with full metadata
            - communications include author name, type, and participant details

            When falling back to Maestro:
            - observations and summaries are empty lists
            - communications have basic fields only (no author metadata)

        Behavior:
            Profile ID Resolution (if Memory is configured):
            1. If profile_id is missing:
               - Attempts lookup using author_info.address (phone number)
               - On successful lookup: Sets profile_id and immediately fetches profile (once)
               - On failure: Logs WARNING and falls back to Maestro
            2. If profile_id exists but profile not fetched:
               - Fetches profile data (one-time attempt only)
               - On failure: Logs WARNING and continues with profile_id only

            Memory Retrieval:
            - If profile_id available: Retrieves from Memory with observations, summaries
            - If profile_id unavailable: Falls back to Maestro Communications API
            - If Memory not configured: Falls back to Maestro Communications API

        Note:
            All profile lookup and fetch failures are handled gracefully. The method never
            raises exceptions for profile-related failures, ensuring memory retrieval
            continues even when profile enrichment is unavailable.

        Raises:
            httpx.HTTPError: Only if the Memory or Maestro API request itself fails
        """
        if self.memora_client and self.config.twilio_memory_config:
            if not conversation_context.profile_id:
                self.logger.debug(
                    "profile_id not found, attempting to lookup profile using phone number"
                )

                if (
                    not conversation_context.author_info
                    or not conversation_context.author_info.address
                ):
                    self.logger.warning(
                        "profile_id is required for memory retrieval but was not found in "
                        "conversation context. Additionally, author_info.address is not available "
                        "for profile lookup. Memory will be retrieved without profile_id."
                    )
                else:
                    # Attempt to lookup profile using phone number
                    phone_number = conversation_context.author_info.address
                    try:
                        self.logger.debug(f"Looking up profile for phone number: {phone_number}")

                        lookup_response: ProfileLookupResponse = (
                            await self.memora_client.lookup_profile(
                                id_type="phone",
                                value=phone_number,
                            )
                        )

                        if not lookup_response.profiles:
                            self.logger.warning(
                                f"No profile found for phone number {phone_number}. "
                                "Profile lookup returned no results. Memory will be retrieved "
                                "without profile_id."
                            )
                        else:
                            # Use the first profile ID
                            conversation_context.profile_id = lookup_response.profiles[0]
                            self.logger.debug(
                                f"Found profile_id: {conversation_context.profile_id}"
                            )

                    except Exception as e:
                        self.logger.warning(
                            f"Failed to lookup profile for {phone_number}: {e}. "
                            "Memory will be retrieved without profile_id."
                        )

            if conversation_context.profile_id and not conversation_context.profile:
                conversation_context.profile = await self.fetch_profile(
                    conversation_context.profile_id
                )

            # If we still don't have a profile_id after lookup attempts, fall back to Maestro
            if not conversation_context.profile_id:
                self.logger.warning(
                    "Memory client is configured but profile_id is not available. "
                    "Falling back to Maestro Communications API."
                )
                communications = await self.maestro_client.list_communications(
                    conversation_id=conversation_context.conversation_id
                )
                return TACMemoryResponse(communications)

            memory_response = await self.memora_client.retrieve_memory(
                profile_id=conversation_context.profile_id,
                conversation_id=conversation_context.conversation_id,
                query=query,
            )
            return TACMemoryResponse(memory_response)

        else:
            self.logger.info(
                "Twilio Memory not configured, falling back to Maestro Communications API"
            )

            communications = await self.maestro_client.list_communications(
                conversation_id=conversation_context.conversation_id
            )

            return TACMemoryResponse(communications)

    async def fetch_profile(self, profile_id: str) -> Optional[ProfileResponse]:
        """
        Fetch profile information with traits for a given profile ID.

        This method retrieves profile data including traits from Twilio Memory.
        If trait_groups are configured in TwilioMemoryConfig, only those trait
        groups will be included in the response.

        Args:
            profile_id: Profile ID using Twilio Type ID (TTID) format

        Returns:
            ProfileResponse with id, created_at, and traits, or None if fetch fails
        """
        # Check if memory client is initialized
        if not self.memora_client or not self.config.twilio_memory_config:
            self.logger.warning(
                "Memory client is not initialized. Cannot fetch profile. "
                "Provide twilio_memory_config when creating TACConfig to enable profile fetching."
            )
            return None

        # Validate profile_id
        if not profile_id:
            self.logger.warning("profile_id is required for profile fetching but was not provided")
            return None

        try:
            # Get trait_groups from config if provided
            trait_groups = self.config.twilio_memory_config.trait_groups

            # Fetch profile
            profile_response = await self.memora_client.get_profile(
                profile_id=profile_id,
                trait_groups=trait_groups,
            )
            return profile_response

        except Exception as e:
            self.logger.warning(
                f"Failed to fetch profile for {profile_id}: {e}. Continuing without profile data."
            )
            return None

    def on_message_ready(
        self,
        callback: Union[
            Callable[[str, ConversationSession, Optional[TACMemoryResponse]], None],
            Callable[[str, ConversationSession, Optional[TACMemoryResponse]], Awaitable[None]],
        ],
    ) -> None:
        """
        Register a callback to be invoked when a message is ready to be processed.

        The callback will be triggered by channels when a new user message arrives,
        regardless of whether memory was fetched. This allows different channels
        (SMS, Voice) to handle memory retrieval differently.

        Supports both synchronous and asynchronous callbacks. Async callbacks
        will be scheduled as background tasks using asyncio.create_task().

        Args:
            callback: A callable that accepts:
                     - str: The user's message content
                     - ConversationSession: Contains conversation_id, profile_id, channel
                     - Optional[TACMemoryResponse]: Retrieved memory data wrapper
                       (None if memory retrieval is skipped or fails)

        Example (Synchronous):
            ```python
            from tac.models.session import ConversationSession
            from tac.models.tac import TACMemoryResponse
            from typing import Optional


            def handle_message(
                user_message: str,
                context: ConversationSession,
                memory_response: Optional[TACMemoryResponse],
            ):
                print(f"User message: {user_message}")
                print(f"Conversation {context.conversation_id} on {context.channel}")

                if memory_response:
                    print(f"Observations: {len(memory_response.observations)}")
                    print(f"Summaries: {len(memory_response.summaries)}")
                    print(f"Communications: {len(memory_response.communications)}")

                # Process user message with LLM
                # llm_response = llm.process(user_message, memory_response)

                # Send response back through the channel
                # channel.send_response(context.conversation_id, llm_response)


            tac = TAC(config)
            tac.on_message_ready(handle_message)
            ```

        Example (Asynchronous):
            ```python
            async def handle_message(
                user_message: str,
                context: ConversationSession,
                memory_response: Optional[TACMemoryResponse],
            ):
                print(f"Message on {context.channel}: {user_message}")

                # Call async operations directly
                response = await call_llm(user_message, memory_response)
                await channel.send_response(context.conversation_id, response)


            tac = TAC(config)
            tac.on_message_ready(handle_message)
            ```
        """
        self._message_ready_callback = callback

    async def trigger_message_ready(
        self,
        user_message: str,
        conversation_context: ConversationSession,
        memory_response: Optional[TACMemoryResponse] = None,
    ) -> None:
        """
        Trigger the registered message ready callback.

        This method is called by channels when a new message is ready to be processed.
        Different channels can call this with or without memory based on their needs.

        Args:
            user_message: The user's message content
            conversation_context: Conversation context with conversation_id, profile_id, channel
            memory_response: Optional memory retrieval response
        """
        if self._message_ready_callback:
            # Check if callback is async
            if inspect.iscoroutinefunction(self._message_ready_callback):
                # Await async callback
                await self._message_ready_callback(
                    user_message, conversation_context, memory_response
                )
            else:
                # Call sync callback directly
                self._message_ready_callback(user_message, conversation_context, memory_response)

    def on_interrupt(
        self,
        callback: Union[
            Callable[[ConversationSession, Any], None],
            Callable[[ConversationSession, Any], Awaitable[None]],
        ],
    ) -> None:
        """
        Register a callback to be invoked when user interrupts the agent.

        The callback will be triggered when the user interrupts the agent's response
        (e.g., in voice conversations when the user starts speaking while the agent
        is still talking). This allows developers to handle interruptions appropriately,
        such as canceling ongoing tool calls, stopping LLM generation, or logging events.

        Supports both synchronous and asynchronous callbacks. Async callbacks
        will be scheduled as background tasks using asyncio.create_task().

        Args:
            callback: A callable that accepts:
                     - ConversationSession: Contains conversation_id, profile_id, channel
                     - InterruptMessage: Details about the interruption (utterance_until_interrupt,
                       duration_until_interrupt_ms)

        Example (Synchronous):
            ```python
            from tac.models.session import ConversationSession
            from tac.models.voice import InterruptMessage


            def handle_interrupt(
                context: ConversationSession,
                interrupt_data: InterruptMessage,
            ):
                print(f"User interrupted conversation {context.conversation_id}")
                print(f"Interrupted at: {interrupt_data.utterance_until_interrupt}")
                print(f"Duration: {interrupt_data.duration_until_interrupt_ms}ms")

                # Cancel ongoing operations, stop LLM generation, etc.
                cancel_pending_operations(context.conversation_id)


            tac = TAC(config)
            tac.on_interrupt(handle_interrupt)
            ```

        Example (Asynchronous):
            ```python
            async def handle_interrupt(
                context: ConversationSession,
                interrupt_data: InterruptMessage,
            ):
                print(f"User interrupted on {context.channel}")

                # Cancel async operations
                await cancel_llm_generation(context.conversation_id)

                # Log to analytics
                await log_interrupt_event(context, interrupt_data)


            tac = TAC(config)
            tac.on_interrupt(handle_interrupt)
            ```
        """
        self._interrupt_callback = callback

    def trigger_interrupt(
        self,
        conversation_context: ConversationSession,
        interrupt_data: Any,
    ) -> None:
        """
        Trigger the registered interrupt callback.

        This method is called by channels when an interrupt event occurs.

        Args:
            conversation_context: Conversation context with conversation_id, profile_id, channel
            interrupt_data: Interrupt details (InterruptMessage for voice channel)
        """
        if self._interrupt_callback:
            # Check if callback is async
            if inspect.iscoroutinefunction(self._interrupt_callback):
                # Schedule async callback as a background task
                try:
                    asyncio.create_task(
                        self._interrupt_callback(conversation_context, interrupt_data)
                    )
                except RuntimeError:
                    # No event loop running, log warning
                    self.logger.warning(
                        "Async interrupt callback registered but no event loop running. "
                        "Callback will not be executed."
                    )
            else:
                # Call sync callback directly
                self._interrupt_callback(conversation_context, interrupt_data)

    async def process_cintel_event(
        self,
        payload: dict[str, Any],
    ) -> OperatorProcessingResult:
        """
        Process a Conversation Intelligence webhook event.

        This method delegates to the internal CI processor to handle incoming
        CI webhook payloads, validate them, and create observations or summaries
        in Memora based on operator results.

        Args:
            payload: The raw webhook payload dictionary from Twilio CI

        Returns:
            OperatorProcessingResult with processing status and details

        Raises:
            ValueError: If CI processor is not initialized (requires both
                twilio_memory_config and conversation_intelligence_config)

        Example:
            ```python
            @app.post("/ci-webhook")
            async def ci_webhook_handler(request: Request):
                payload = await request.json()
                result = await tac.process_cintel_event(payload)

                if result.success:
                    if result.skipped:
                        print(f"Skipped: {result.skip_reason}")
                    else:
                        print(f"Created {result.created_count} {result.event_type}(s)")
                else:
                    print(f"Error: {result.error}")

                return result.model_dump()
            ```
        """
        if not self.ci_processor:
            raise ValueError(
                "Conversation Intelligence processor is not initialized. "
                "Ensure both twilio_memory_config and conversation_intelligence_config "
                "are provided when creating TACConfig."
            )

        return await self.ci_processor.process_event(payload)
