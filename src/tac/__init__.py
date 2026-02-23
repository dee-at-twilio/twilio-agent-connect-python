from importlib.metadata import version

__version__ = version("tac")

from tac.core import TAC, TACConfig, get_logger
from tac.models import TwiMLOptions

__all__ = [
    "TAC",
    "TACConfig",
    "get_logger",
    "TwiMLOptions",
]
