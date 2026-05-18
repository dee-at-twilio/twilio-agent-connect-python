# Controlling Auto-Generated Documentation

API documentation is automatically generated from Python source code using mkdocstrings. This guide explains how to control what appears in the docs.

## Quick Reference

**To hide something from docs:**
- Add `_` prefix to method/function name (e.g., `_internal_method`)
- Remove from `__all__` list in module's `__init__.py`
- Don't add a docstring (filtered automatically)

**To show something in docs:**
- Add to `__all__` list in module's `__init__.py`
- Make it public (no `_` prefix)
- Add a docstring

## Method 1: Control with __all__ (Module Level)

The `__all__` list in each module's `__init__.py` controls which classes/functions appear in docs.

### Example: Hide a class from channels

```python
# src/tac/channels/__init__.py
__all__ = [
    "VoiceChannel",
    "SMSChannel",
    # "RCSChannel",  ← Comment out to hide from docs
    "WhatsAppChannel",
    "ChatChannel",
]
```

### Files to Edit:

| Module | File | Controls |
|--------|------|----------|
| Core | `src/tac/core/__init__.py` | TAC, TACConfig, get_logger |
| Channels | `src/tac/channels/__init__.py` | VoiceChannel, SMSChannel, etc. |
| Adapters | `src/tac/adapters/__init__.py` | with_tac_memory |
| Server | `src/tac/server/__init__.py` | TACFastAPIServer |
| Models | `src/tac/models/__init__.py` | TwiMLOptions, etc. |

## Method 2: Use Underscore Prefix (Method Level)

Methods/functions starting with `_` are considered private and hidden from docs.

```python
class TAC:
    def on_message_ready(self):
        """Public method - shows in docs."""
        pass
    
    def _internal_helper(self):
        """Private method - hidden from docs."""
        pass
```

### Example: Hide is_orchestrator_enabled

**Before:**
```python
def is_orchestrator_enabled(self) -> bool:
    """Check if orchestrator is enabled."""
```

**After:**
```python
def _is_orchestrator_enabled(self) -> bool:
    """Internal: Check if orchestrator is enabled."""
```

## Method 3: Remove Docstring

Methods without docstrings are automatically hidden (configured in `mkdocs.yml`).

```python
def internal_method(self):
    # No docstring = hidden from docs
    pass
```

## Current Filters (mkdocs.yml)

These filters are already configured:

```yaml
filters:
  - "!^_"          # Hide _private methods
  - "!^model_"     # Hide Pydantic internals (model_dump, model_config, etc.)
show_if_no_docstring: false  # Hide undocumented members
```

## Typical Workflow

### 1. Adding a new public class

```python
# src/tac/channels/email.py
class EmailChannel:
    """Send messages via email."""
    
    def __init__(self, tac):
        """Initialize email channel."""
        self.tac = tac
```

```python
# src/tac/channels/__init__.py
__all__ = [
    "VoiceChannel",
    "SMSChannel",
    "EmailChannel",  # ← Add here to show in docs
]
```

### 2. Hiding an internal method

Just add `_` prefix - no other changes needed:

```python
class TAC:
    def retrieve_memory(self):
        """Public API - shows in docs."""
        return self._fetch_from_api()
    
    def _fetch_from_api(self):
        """Internal implementation - hidden."""
        pass
```

### 3. Marking something as experimental

Keep it public but note in docstring:

```python
def new_feature(self):
    """Experimental feature.
    
    Warning:
        This API is experimental and may change in future versions.
    """
```

## Rebuilding Docs

After changing `__all__` or method names:

```bash
# Local preview
uv run mkdocs serve

# Build for deployment
uv run mkdocs build
```

Changes are automatically picked up when you push to the `main` branch (via GitHub Actions).

## Summary

**Most common controls:**
1. **Hide class:** Remove from `__all__` in `__init__.py`
2. **Hide method:** Add `_` prefix
3. **Hide undocumented:** Don't add docstring (automatic)

**All control happens in Python source code** - no need to maintain separate doc files!
