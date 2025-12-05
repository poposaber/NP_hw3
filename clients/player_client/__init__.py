"""player_client package initializer."""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # 供型別檢查與 linter 使用（不會在 runtime 執行）
    from .player_client import PlayerClient
    from .player_client_window import PlayerClientWindow

__all__ = ["PlayerClientWindow", "PlayerClient"]
__version__ = "0.1.0"

def __getattr__(name: str):
    if name == "PlayerClientWindow":
        from .player_client_window import PlayerClientWindow
        return PlayerClientWindow
    if name == "PlayerClient":
        from .player_client import PlayerClient
        return PlayerClient
    raise AttributeError(f"module {__name__} has no attribute {name}")