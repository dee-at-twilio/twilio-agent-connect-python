"""Server module providing batteries-included FastAPI server for TAC channels.

Requires the 'server' optional dependency: pip install tac[server]
"""

from tac.server.config import TACServerConfig
from tac.server.server import FastAPIWebSocketAdapter, TACServer
from tac.server.webhook import validate_twilio_webhook

__all__ = ["TACServer", "TACServerConfig", "FastAPIWebSocketAdapter", "validate_twilio_webhook"]
