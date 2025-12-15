import uuid
import threading
from queue import Queue
import time
from typing import Optional, Callable
from base.message_format_passer import MessageFormatPasser
from base.peer_worker import PeerWorker
from protocols.protocols import Formats, Words
from clients.client_base import ClientBase
from pathlib import Path
from base.file_sender import FileSender
import hashlib
# from datetime import datetime, timezone
import zipfile
import json
import socket

DEFAULT_MAX_CONNECT_TRY_COUNT = 5
DEFAULT_MAX_HANDSHAKE_TRY_COUNT = 5
DEFAULT_CONNECT_TIMEOUT = 3.0
DEFAULT_HANDSHAKE_TIMEOUT = 3.0
DEFAULT_RECEIVE_TIMEOUT = 1.0
DEFAULT_HEARTBEAT_INTERVAL = 10.0
DEFAULT_HEARTBEAT_PATIENCE = 3
DEFAULT_LOBBY_RESPONSE_TIMEOUT = 5.0


class DeveloperClient(ClientBase):
    def __init__(self, host: str = "127.0.0.1", port: int = 21355,
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
                 on_connection_lost: Optional[Callable[[], None]] = None) -> None:
        super().__init__(host, port, Words.Roles.DEVELOPER, max_connect_try_count, max_handshake_try_count, 
                         connect_timeout, handshake_timeout, receive_timeout, lobby_response_timeout, 
                         heartbeat_interval, heartbeat_patience, on_connection_done, on_connection_fail, on_connection_lost)
    
    def upload_file(self, path: Path) -> tuple[bool, dict]:
        def _sha256_file(path: Path) -> str:
            h = hashlib.sha256()
            with path.open("rb") as f:
                for b in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(b)
            return h.hexdigest()

        def _is_safe(name: str) -> bool:
            p = Path(name)
            return not p.is_absolute() and (".." not in p.parts)
        
        try:
            size = path.stat().st_size
            sha256 = _sha256_file(path)
            # Defaults if manifest is missing fields
            game_id = path.stem
            version = "0.1.0"
            game_name = game_id

            # Strict validation against your template rules
            with zipfile.ZipFile(path, "r") as z:
                names = z.namelist()
                # path safety
                bad = [n for n in names if not _is_safe(n)]
                if bad:
                    return (False, {Words.ParamKeys.Failure.REASON: f"Unsafe paths in zip: {bad[:3]}..."})

                # must-have files at expected locations
                required = ["config.json", "client/__main__.py", "server/__main__.py"]
                missing = [r for r in required if r not in names]
                if missing:
                    return (False, {Words.ParamKeys.Failure.REASON: f"Missing required files: {', '.join(missing)}"})

                # parse config.json at root
                try:
                    manifest = json.loads(z.read("config.json").decode("utf-8"))
                except Exception as e:
                    return (False, {Words.ParamKeys.Failure.REASON: f"Invalid config.json: {e}"})

                game_id = manifest.get("id") or game_id
                version = manifest.get("version") or version
                game_name = manifest.get("name") or game_name

            # start sending
            assert self.worker is not None
            response = self.worker.pend_and_wait(Words.MessageType.REQUEST, {
                Words.DataKeys.Request.COMMAND: Words.Command.UPLOAD_START, 
                Words.DataKeys.PARAMS: {
                            Words.ParamKeys.Metadata.GAME_ID: game_id,
                            Words.ParamKeys.Metadata.GAME_NAME: game_name, 
                            Words.ParamKeys.Metadata.VERSION: version,
                            Words.ParamKeys.Metadata.FILE_NAME: path.name,
                            Words.ParamKeys.Metadata.SIZE: size,
                            Words.ParamKeys.Metadata.SHA256: sha256,
                            # Optional: echo manifest details for server-side validation
                            # "manifest": {"min_players": manifest.get("min_players"), "max_players": manifest.get("max_players")}
                        }
            }, self.server_response_timeout)

            if response.get(Words.DataKeys.Response.RESULT) != Words.Result.SUCCESS:
                params = response.get(Words.DataKeys.PARAMS) or {}
                reason = params.get(Words.ParamKeys.Failure.REASON, "Upload start rejected")
                return (False, {Words.ParamKeys.Failure.REASON: reason})
            
            params = response.get(Words.DataKeys.PARAMS)
            assert isinstance(params, dict)
            port = params.get(Words.ParamKeys.Success.PORT)
            temp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            assert isinstance(port, int)
            temp_sock.connect((self.host, port))
            temp_sender = FileSender(temp_sock, path)
            temp_sender.send()

            # end sending
            response = self.worker.pend_and_wait(Words.MessageType.REQUEST, {
                Words.DataKeys.Request.COMMAND: Words.Command.UPLOAD_END
            }, self.server_response_timeout)

            if response.get(Words.DataKeys.Response.RESULT) != Words.Result.SUCCESS:
                params = response.get(Words.DataKeys.PARAMS) or {}
                reason = params.get(Words.ParamKeys.Failure.REASON, "Upload end rejected")
                return (False, {Words.ParamKeys.Failure.REASON: reason})

            temp_sender.close()
            return (True, {})

        except Exception as e:
            return (False, {Words.ParamKeys.Failure.REASON: str(e)})
        
    def try_check_my_works(self) -> tuple[bool, dict]:
        try:
            assert self.worker is not None
            result_data = self.worker.pend_and_wait(Words.MessageType.REQUEST, {Words.DataKeys.Request.COMMAND: Words.Command.CHECK_MY_WORKS}, self.server_response_timeout)
            params = result_data.get(Words.DataKeys.PARAMS) or {}
            if result_data.get(Words.DataKeys.Response.RESULT) != Words.Result.SUCCESS:
                # params = result_data.get(Words.DataKeys.PARAMS) or {}
                reason = params.get(Words.ParamKeys.Failure.REASON, "unknown")
                return (False, {Words.ParamKeys.Failure.REASON: reason})
            return (True, params)
        except Exception as e:
            print(f"Exception in try_check_my_works: {e}")
            return (False, {Words.ParamKeys.Failure.REASON: str(e)})