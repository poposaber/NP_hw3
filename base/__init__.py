"""base package initializer"""
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .message_format_passer import MessageFormatPasser
    from .message_format import MessageFormat

__all__ = ["MessageFormatPasser", "MessageFormat"]
__version__ = "0.1.0"
#from .message_format import MessageFormat
def __getattr__(name: str):
    if name == "PlayerClientWindow":
        from .message_format_passer import MessageFormatPasser
        return MessageFormatPasser
    if name == "PlayerClient":
        from .message_format import MessageFormat
        return MessageFormat
    raise AttributeError(f"module {__name__} has no attribute {name}")