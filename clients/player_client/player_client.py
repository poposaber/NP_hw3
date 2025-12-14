import uuid
import threading
from queue import Queue
import time
from typing import Optional, Callable
from base.message_format_passer import MessageFormatPasser
from base.peer_worker import PeerWorker
from protocols.protocols import Formats, Words
from clients.client_base import ClientBase

DEFAULT_MAX_CONNECT_TRY_COUNT = 5
DEFAULT_MAX_HANDSHAKE_TRY_COUNT = 5
DEFAULT_CONNECT_TIMEOUT = 3.0
DEFAULT_HANDSHAKE_TIMEOUT = 3.0
DEFAULT_RECEIVE_TIMEOUT = 1.0
DEFAULT_HEARTBEAT_INTERVAL = 10.0
DEFAULT_HEARTBEAT_PATIENCE = 3
DEFAULT_LOBBY_RESPONSE_TIMEOUT = 5.0


class PlayerClient(ClientBase):
    def __init__(self, host: str = "127.0.0.1", port: int = 21354,
                 max_connect_try_count: int = DEFAULT_MAX_CONNECT_TRY_COUNT, 
                 max_handshake_try_count: int = DEFAULT_MAX_HANDSHAKE_TRY_COUNT,
                 connect_timeout = DEFAULT_CONNECT_TIMEOUT, 
                 handshake_timeout = DEFAULT_HANDSHAKE_TIMEOUT, 
                 receive_timeout = DEFAULT_RECEIVE_TIMEOUT, 
                 lobby_response_timeout = DEFAULT_LOBBY_RESPONSE_TIMEOUT, 
                 heartbeat_interval = DEFAULT_HEARTBEAT_INTERVAL, 
                 heartbeat_patience = DEFAULT_HEARTBEAT_PATIENCE, 
                 on_connection_done: Optional[Callable[[], None]] = None, 
                 on_connection_fail: Optional[Callable[[], None]] = None, 
                 on_connection_lost: Optional[Callable[[], None]] = None, 
                 on_recv_message: Optional[Callable[[tuple[str, str, dict]], None]] = None) -> None:
        super().__init__(host, port, Words.Roles.PLAYER, max_connect_try_count, max_handshake_try_count, 
                         connect_timeout, handshake_timeout, receive_timeout, lobby_response_timeout, 
                         heartbeat_interval, heartbeat_patience, 
                         on_connection_done, on_connection_fail, on_connection_lost, on_recv_message)
    
    def try_sync_lobby_status(self) -> tuple[bool, dict]:
        try:
            assert self.worker is not None
            response = self.worker.pend_and_wait(Words.MessageType.REQUEST, {
                Words.DataKeys.Request.COMMAND: Words.Command.SYNC_LOBBY_STATUS
            }, self.server_response_timeout) # expected {responding_id: ..., result: success, params: {online_player: [...], rooms: {room_name: {owner: owner_name, players: [...], spectators: [...]}}}}
        except Exception as e:
            return (False, {'error': str(e)})
        params = response.get(Words.DataKeys.PARAMS)
        assert isinstance(params, dict)
        if response.get(Words.DataKeys.Response.RESULT) != Words.Result.SUCCESS:
            return (False, params)
        return (True, params)