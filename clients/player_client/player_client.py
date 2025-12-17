import uuid
import threading
from queue import Queue
import time
from typing import Optional, Callable
from base.message_format_passer import MessageFormatPasser
from base.peer_worker import PeerWorker
from protocols.protocols import Formats, Words
from clients.client_base import ClientBase
import socket
from base.file_receiver import FileReceiver
from pathlib import Path
import shutil

DEFAULT_MAX_CONNECT_TRY_COUNT = 5
DEFAULT_MAX_HANDSHAKE_TRY_COUNT = 5
DEFAULT_CONNECT_TIMEOUT = 3.0
DEFAULT_HANDSHAKE_TIMEOUT = 3.0
DEFAULT_RECEIVE_TIMEOUT = 1.0
DEFAULT_HEARTBEAT_INTERVAL = 10.0
DEFAULT_HEARTBEAT_PATIENCE = 3
DEFAULT_LOBBY_RESPONSE_TIMEOUT = 5.0

GAME_DIR = Path(__file__).resolve().parent / "games"

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
    
    def try_update_store(self) -> tuple[bool, dict]:
        try:
            assert self.worker is not None
            response = self.worker.pend_and_wait(Words.MessageType.REQUEST, {
                Words.DataKeys.Request.COMMAND: Words.Command.CHECK_STORE
                }, self.server_response_timeout)
        except Exception as e:
            return (False, {'error': str(e)})
        params = response.get(Words.DataKeys.PARAMS)
        assert isinstance(params, dict)
        if response.get(Words.DataKeys.Response.RESULT) != Words.Result.SUCCESS:
            return (False, params)
        return (True, params)
    
    def try_download_game(self, game_id: str) -> tuple[bool, dict]:
        try:
            assert self.worker is not None
            response = self.worker.pend_and_wait(Words.MessageType.REQUEST, {
                Words.DataKeys.Request.COMMAND: Words.Command.DOWNLOAD_START, 
                Words.DataKeys.PARAMS: {
                    Words.ParamKeys.Metadata.GAME_ID: game_id
                }
            }, self.server_response_timeout)
        except Exception as e:
            return (False, {'error': str(e)})
        params = response.get(Words.DataKeys.PARAMS)
        assert isinstance(params, dict)
        if response.get(Words.DataKeys.Response.RESULT) != Words.Result.SUCCESS:
            return (False, params)
        port = params.get(Words.ParamKeys.Success.PORT)
        temp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        temp_sock.connect((self.host, port))
        assert self.username is not None
        file_path = GAME_DIR / self.username / game_id / (game_id + ".zip")
        dest_dir = GAME_DIR / self.username / game_id
        file_receiver = FileReceiver(temp_sock, file_path)
        success = file_receiver.receive()
        if not success:
            return (False, {Words.ParamKeys.Failure.REASON: "file receiver error"})
        shutil.unpack_archive(file_path, dest_dir)
        return (True, {})
    
    def try_create_room(self, room_name: str, game_id: str)  -> tuple[bool, dict]:
        try:
            assert self.worker is not None
            response = self.worker.pend_and_wait(Words.MessageType.REQUEST, {
                Words.DataKeys.Request.COMMAND: Words.Command.CREATE_ROOM, 
                Words.DataKeys.PARAMS: {
                    Words.ParamKeys.Room.ROOM_NAME: room_name, 
                    Words.ParamKeys.Room.GAME_ID: game_id
                }
            }, self.server_response_timeout)
        except Exception as e:
            return (False, {'error': str(e)})
        params = response.get(Words.DataKeys.PARAMS)
        assert isinstance(params, dict)
        if response.get(Words.DataKeys.Response.RESULT) != Words.Result.SUCCESS:
            return (False, params)
        return (True, params)

    def try_join_room(self, room_name: str) -> tuple[bool, dict]:
        try:
            assert self.worker is not None
            response = self.worker.pend_and_wait(Words.MessageType.REQUEST, {
                Words.DataKeys.Request.COMMAND: Words.Command.JOIN_ROOM,
                Words.DataKeys.PARAMS: {
                    Words.ParamKeys.Room.ROOM_NAME: room_name
                }
            }, self.server_response_timeout)
        except Exception as e:
            return (False, {'error': str(e)})
        params = response.get(Words.DataKeys.PARAMS)
        assert isinstance(params, dict)
        if response.get(Words.DataKeys.Response.RESULT) != Words.Result.SUCCESS:
            return (False, params)
        return (True, params)

    def try_leave_room(self, room_name: str) -> tuple[bool, dict]:
        try:
            assert self.worker is not None
            response = self.worker.pend_and_wait(Words.MessageType.REQUEST, {
                Words.DataKeys.Request.COMMAND: Words.Command.LEAVE_ROOM,
                Words.DataKeys.PARAMS: {
                    Words.ParamKeys.Room.ROOM_NAME: room_name
                }
            }, self.server_response_timeout)
        except Exception as e:
            return (False, {'error': str(e)})
        params = response.get(Words.DataKeys.PARAMS)
        assert isinstance(params, dict)
        if response.get(Words.DataKeys.Response.RESULT) != Words.Result.SUCCESS:
            return (False, params)
        return (True, params)

    def try_start_game(self, room_name: str) -> tuple[bool, dict]:
        try:
            assert self.worker is not None
            response = self.worker.pend_and_wait(Words.MessageType.REQUEST, {
                Words.DataKeys.Request.COMMAND: Words.Command.START_GAME,
                Words.DataKeys.PARAMS: {
                    Words.ParamKeys.Room.ROOM_NAME: room_name
                }
            }, self.server_response_timeout)
        except Exception as e:
            return (False, {'error': str(e)})
        params = response.get(Words.DataKeys.PARAMS)
        assert isinstance(params, dict) or params is None
        if response.get(Words.DataKeys.Response.RESULT) != Words.Result.SUCCESS:
            return (False, params or {})
        return (True, params or {})

    
    