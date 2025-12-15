import threading
import socket
from base.message_format_passer import MessageFormatPasser
from protocols.protocols import Formats, Words
from typing import Optional
from base.peer_worker import PeerWorker
import time
import uuid
from servers.server_base import ServerBase
from base.file_receiver import FileReceiver
from base.file_sender import FileSender
import queue
from pathlib import Path
import hashlib, json, os
from base.file_checker import FileChecker

DEFAULT_ACCEPT_TIMEOUT = 1.0
DEFAULT_CONNECT_TIMEOUT = 3.0
DEFAULT_RECEIVE_TIMEOUT = 1.0
DEFAULT_HANDSHAKE_TIMEOUT = 5.0
DEFAULT_MAX_HANDSHAKE_TRY_COUNT = 5
DEFAULT_DB_HEARTBEAT_INTERVAL = 10.0
DEFAULT_DB_HEARTBEAT_PATIENCE = 3
DEFAULT_DB_RESPONSE_TIMEOUT = 3.0
DEFAULT_CLIENT_HEARTBEAT_TIMEOUT = 30.0

GAME_CACHE_DIR = Path(__file__).resolve().parent / "game_cache"

class DeveloperServer(ServerBase):
    def __init__(self, host: str = "0.0.0.0", port: int = 21355, 
                 db_host: str = "127.0.0.1", db_port: int = 32132, 
                 accept_timeout = DEFAULT_ACCEPT_TIMEOUT, 
                 connect_timeout = DEFAULT_CONNECT_TIMEOUT, 
                 receive_timeout = DEFAULT_RECEIVE_TIMEOUT, 
                 handshake_timeout = DEFAULT_HANDSHAKE_TIMEOUT, 
                 db_response_timeout = DEFAULT_DB_RESPONSE_TIMEOUT, 
                 max_handshake_try_count = DEFAULT_MAX_HANDSHAKE_TRY_COUNT, 
                 db_heartbeat_interval = DEFAULT_DB_HEARTBEAT_INTERVAL, 
                 db_heartbeat_patience = DEFAULT_DB_HEARTBEAT_PATIENCE, 
                 client_heartbeat_timeout = DEFAULT_CLIENT_HEARTBEAT_TIMEOUT) -> None:
        super().__init__(host, port, db_host, db_port, Words.Roles.DEVELOPERSERVER, 
                         accept_timeout, connect_timeout, receive_timeout, handshake_timeout, 
                         db_response_timeout, max_handshake_try_count, db_heartbeat_interval, 
                         db_heartbeat_patience, client_heartbeat_timeout)
        self.passer_developer_dict: dict[MessageFormatPasser, str | None] = {}
                # track ongoing uploads per connection
        self.upload_state: dict[MessageFormatPasser, dict] = {}
        self.upload_state_lock = threading.Lock()
        self.upload_to_database_queue: queue.Queue[Path] = queue.Queue() # storing path of .zip
        self.upload_to_database_thread = threading.Thread(target=self.upload_to_database_loop)
        
    def _run_threads(self):
        super()._run_threads()
        self.upload_to_database_thread.start()

    def upload_to_database_loop(self):
        while not self.stop_event.is_set():
            try:
                path = self.upload_to_database_queue.get(timeout=0.5)
                metadata_path = path.parent / "metadata.json"
                metadata: dict = {}
                try:
                    if not metadata_path.exists():
                        raise FileNotFoundError(str(metadata_path))
                    with metadata_path.open("r", encoding="utf-8") as mf:
                        metadata = json.load(mf)
                    if not isinstance(metadata, dict):
                        raise ValueError("metadata.json does not contain a JSON object")
                except Exception as e:
                    print(f"[DeveloperServer] failed to load metadata: {e}")
                    continue
                response = self.try_request_and_wait(Words.Command.UPLOAD_START, metadata)
                if response.get(Words.DataKeys.Response.RESULT) != Words.Result.SUCCESS:
                    print(f"Upload start failed. Params: {response.get(Words.DataKeys.PARAMS)}")
                    continue
                params = response.get(Words.DataKeys.PARAMS)
                assert isinstance(params, dict)
                port = params.get(Words.ParamKeys.Success.PORT)
                temp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                temp_sock.connect((self.db_host, port))
                file_sender = FileSender(temp_sock, path)
                file_sender.send()

                response = self.try_request_and_wait(Words.Command.UPLOAD_END, {})
                if response.get(Words.DataKeys.Response.RESULT) != Words.Result.SUCCESS:
                    print(f"Upload end failed. Params: {response.get(Words.DataKeys.PARAMS)}")
                    continue
                file_sender.close()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Exception in upload_to_database_loop: {e}")
        print("exited upload_to_database_loop")


    def on_new_connection(self, received_message_id: str, role: str, passer: MessageFormatPasser, handshake_data: dict):
        match role:
            case Words.Roles.DEVELOPER:
                self.send_response(passer, received_message_id, Words.Result.SUCCESS)
                self.handle_developer(passer)
            case _:
                print(f"Unknown role: {role}")

    def handle_developer(self, passer: MessageFormatPasser):
        self.passer_developer_dict[passer] = None
        passer.settimeout(self.receive_timeout)
        last_hb_time = time.time()
        while not self.stop_event.is_set():
            try:
                msg_id, msg_type, data = passer.receive_args(Formats.MESSAGE)
                match msg_type:
                    case Words.MessageType.REQUEST:
                        assert isinstance(data, dict)
                        cmd = data.get(Words.DataKeys.Request.COMMAND)
                        match cmd:
                            case Words.Command.LOGIN:
                                # continue
                                # time.sleep(7)
                                # self.send_response(passer, msg_id, Words.Result.FAILURE, {Words.ParamKeys.Failure.REASON: 'suduiwee', '12': 345})
                                params = data.get(Words.DataKeys.PARAMS)
                                assert isinstance(params, dict)
                                username = params.get(Words.ParamKeys.Login.USERNAME)
                                # password = params.get(Words.ParamKeys.Login.PASSWORD)
                                login_data = self.try_request_and_wait(Words.Command.LOGIN, params)
                                
                                if login_data[Words.DataKeys.Response.RESULT] == Words.Result.SUCCESS:
                                    self.passer_developer_dict[passer] = username
                                    self.send_response(passer, msg_id, Words.Result.SUCCESS)
                                elif login_data[Words.DataKeys.Response.RESULT] == Words.Result.FAILURE:
                                    params = login_data.get(Words.DataKeys.PARAMS)
                                    assert isinstance(params, dict)
                                    # reason = params.get(Words.ParamKeys.Failure.REASON)
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, params)
                                else:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: "Unknown login result."
                                    })
                            case Words.Command.REGISTER:
                                params = data.get(Words.DataKeys.PARAMS)
                                assert isinstance(params, dict)
                                # username = params.get(Words.ParamKeys.Register.USERNAME)
                                # password = params.get(Words.ParamKeys.Register.PASSWORD)
                                reg_data = self.try_request_and_wait(Words.Command.REGISTER, params)

                                
                                if reg_data[Words.DataKeys.Response.RESULT] == Words.Result.SUCCESS:
                                    self.send_response(passer, msg_id, Words.Result.SUCCESS)
                                elif reg_data[Words.DataKeys.Response.RESULT] == Words.Result.FAILURE:
                                    params = reg_data.get(Words.DataKeys.PARAMS)
                                    assert isinstance(params, dict)
                                    reason = params.get(Words.ParamKeys.Failure.REASON)
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: reason
                                    })
                                else:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: "Unknown register result."
                                    })
                            case Words.Command.LOGOUT:
                                # params = data.get(Words.DataKeys.PARAMS)
                                # assert isinstance(params, dict)
                                username = self.passer_developer_dict.get(passer)
                                if not username:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: "Developer not logged in yet."
                                    })
                                    continue
                                result_data = self.try_request_and_wait(Words.Command.LOGOUT, {
                                    Words.ParamKeys.Logout.USERNAME: username
                                })
                                self.send_response(passer, msg_id, result_data[Words.DataKeys.Response.RESULT], result_data.get(Words.DataKeys.PARAMS))
                            case Words.Command.EXIT:
                                username = self.passer_developer_dict.get(passer)
                                if username:
                                    self.try_request_and_wait(Words.Command.LOGOUT, {
                                        Words.ParamKeys.Logout.USERNAME: username
                                    })
                                self.send_response(passer, msg_id, Words.Result.SUCCESS)
                                time.sleep(5)
                                break
                            case Words.Command.UPLOAD_START:
                                # initialize an upload session
                                params = data.get(Words.DataKeys.PARAMS) or {}
                                username = self.passer_developer_dict.get(passer)
                                if not username:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: "Developer not logged in yet."
                                    })
                                    continue
                                game_id = params.get(Words.ParamKeys.Metadata.GAME_ID)
                                version = params.get(Words.ParamKeys.Metadata.VERSION)
                                file_name = params.get(Words.ParamKeys.Metadata.FILE_NAME)
                                size = params.get(Words.ParamKeys.Metadata.SIZE)
                                sha256 = params.get(Words.ParamKeys.Metadata.SHA256)
                                game_name = params.get(Words.ParamKeys.Metadata.GAME_NAME)
                                if not (game_id and version and file_name and isinstance(size, int) and sha256 and game_name):
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: "Missing upload metadata"
                                    })
                                    continue
                                # check game valid
                                result_data = self.try_request_and_wait(Words.Command.CHECK_GAME_VALID, {
                                    Words.ParamKeys.Metadata.GAME_ID: game_id, 
                                    Words.ParamKeys.Metadata.VERSION: version, 
                                    Words.ParamKeys.Metadata.UPLOADER: self.passer_developer_dict.get(passer)
                                })

                                if result_data.get(Words.DataKeys.Response.RESULT) != Words.Result.SUCCESS:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, result_data.get(Words.DataKeys.PARAMS))
                                    continue

                                


                                # prepare cache path
                                from pathlib import Path
                                import os, json, hashlib
                                cache_root = GAME_CACHE_DIR / str(game_id) / str(version)
                                try:
                                    cache_root.mkdir(parents=True, exist_ok=True)
                                except Exception as e:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: f"Cannot create cache: {e}"
                                    })
                                    continue
                                # part_path = cache_root / (str(filename) + ".part")
                                # try:
                                #     f = open(part_path, "wb")
                                # except Exception as e:
                                #     self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                #         Words.ParamKeys.Failure.REASON: f"Cannot open temp file: {e}"
                                #     })
                                #     continue
                                # record state
                                with self.upload_state_lock:
                                    # "file": f,
                                    self.upload_state[passer] = {
                                        Words.ParamKeys.Metadata.SIZE: size,
                                        Words.ParamKeys.Metadata.SHA256: sha256,
                                        Words.ParamKeys.Metadata.FILE_NAME: file_name,
                                        Words.ParamKeys.Metadata.GAME_ID: game_id,
                                        Words.ParamKeys.Metadata.VERSION: version,
                                        Words.ParamKeys.Metadata.GAME_NAME: game_name, 
                                        "upload_done": False
                                    }
                                temp_server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                temp_server_sock.bind(("0.0.0.0", 0))
                                temp_server_sock.listen(1)
                                port = temp_server_sock.getsockname()[1]
                                self.send_response(passer, msg_id, Words.Result.SUCCESS, {
                                    Words.ParamKeys.Success.PORT: port
                                })
                                threading.Thread(target=self.handle_upload, args=(temp_server_sock, passer), daemon=True).start()
                            case Words.Command.UPLOAD_END:
                                # finalize the upload: verify and move into place
                                st = {}
                                with self.upload_state_lock:
                                    st = self.upload_state.get(passer)
                                if not st:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: "No active upload"
                                    })
                                    continue
                                done = False
                                check_count = 0
                                while check_count <= 15:
                                    with self.upload_state_lock:
                                        st = self.upload_state.get(passer) or {}
                                        print(f"upload_done: {st.get('upload_done')}")
                                        if st.get("upload_done"):
                                            done = True
                                            break
                                    check_count += 1
                                    time.sleep(0.2)

                                if not done:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: "Upload not done."
                                    })
                                    continue
                                
                                final_path = GAME_CACHE_DIR / str(st[Words.ParamKeys.Metadata.GAME_ID]) / str(st[Words.ParamKeys.Metadata.VERSION]) / str(st[Words.ParamKeys.Metadata.FILE_NAME])
                                
                                file_checker = FileChecker(final_path, st)
                                success, params = file_checker.check()
                                if not success:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, params)
                                    continue

                                # move into place
                                try:
                                    # part_path.replace(final_path)
                                    # write metadata
                                    meta = {
                                        Words.ParamKeys.Metadata.GAME_ID: st[Words.ParamKeys.Metadata.GAME_ID],
                                        Words.ParamKeys.Metadata.GAME_NAME: st[Words.ParamKeys.Metadata.GAME_NAME], 
                                        Words.ParamKeys.Metadata.VERSION: st[Words.ParamKeys.Metadata.VERSION],
                                        Words.ParamKeys.Metadata.UPLOADER: self.passer_developer_dict.get(passer), 
                                        Words.ParamKeys.Metadata.FILE_NAME: st[Words.ParamKeys.Metadata.FILE_NAME],
                                        Words.ParamKeys.Metadata.SIZE: st[Words.ParamKeys.Metadata.SIZE],
                                        Words.ParamKeys.Metadata.SHA256: st[Words.ParamKeys.Metadata.SHA256],
                                    }
                                    # meta = st.copy()
                                    (GAME_CACHE_DIR / str(st[Words.ParamKeys.Metadata.GAME_ID]) / str(st[Words.ParamKeys.Metadata.VERSION]) / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
                                except Exception as e:
                                    with self.upload_state_lock:
                                        self.upload_state.pop(passer, None)
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: f"Finalize error: {e}"
                                    })
                                    continue

                                with self.upload_state_lock:
                                    self.upload_state.pop(passer, None)
                                self.send_response(passer, msg_id, Words.Result.SUCCESS)
                                self.upload_to_database_queue.put(final_path)
                            case Words.Command.CHECK_MY_WORKS:
                                result_data = self.try_request_and_wait(Words.Command.CHECK_DEV_WORKS, {
                                    Words.ParamKeys.CheckInfo.USERNAME: self.passer_developer_dict[passer]
                                    })
                                params = result_data.get(Words.DataKeys.PARAMS)
                                if result_data.get(Words.DataKeys.Response.RESULT) != Words.Result.SUCCESS:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, params)
                                    continue
                                self.send_response(passer, msg_id, Words.Result.SUCCESS, params)
                            case _:
                                self.send_response(passer, msg_id, Words.Result.FAILURE, {Words.ParamKeys.Failure.REASON: "Unknown command."})
                    case Words.MessageType.HEARTBEAT:
                        # time.sleep(12)
                        last_hb_time = time.time()
                        self.send_response(passer, msg_id, Words.Result.SUCCESS)
            except TimeoutError:
                if time.time() - last_hb_time > self.client_heartbeat_timeout:
                    print(f"[DeveloperServer] client heartbeat timeout (>{self.client_heartbeat_timeout}s), terminating connection")
                    break
                # also try to receive raw chunk frames during idle
                # try:
                #     raw = passer.receive_raw()
                #     if raw:
                #         # parse: [4-byte header_len][header_json][chunk_bytes]
                #         import struct, json as _json
                #         if len(raw) < 4:
                #             raise ValueError("Invalid raw frame: too short for header length")
                #         header_len = struct.unpack("!I", raw[:4])[0]
                #         if 4 + header_len > len(raw):
                #             raise ValueError("Invalid raw frame: header length exceeds payload")
                #         header = raw[4:4+header_len]
                #         chunk = raw[4+header_len:]
                #         info = _json.loads(header.decode('utf-8'))
                #         if info.get('type') == 'UPLOAD_CHUNK':
                #             st = self.upload_state.get(passer)
                #             if st and isinstance(st.get('file'), object):
                #                 seq = info.get('seq', -1)
                #                 # simple sequence monotonic check
                #                 if st['seq'] != -1 and seq != st['seq'] + 1:
                #                     # out-of-order: ignore (could add buffering)
                #                     pass
                #                 else:
                #                     st['seq'] = seq
                #                     st['file'].write(chunk)
                #                     st['bytes'] += len(chunk)
                # except TimeoutError:
                #     pass
                continue
            except ConnectionError as e:
                print(f"[DeveloperServer] ConnectionError raised in handle_developer: {e}")
                break
            except Exception as e:
                print(f"[DeveloperServer] exception raised in handle_developer: {e}")
                break

        self.passer_developer_dict.pop(passer, None)

    def handle_upload(self, server_sock: socket.socket, dev_passer: MessageFormatPasser):
        dev_sock, addr = server_sock.accept()
        server_sock.close()
        print(f"handle_upload get connected from {addr}")
        with self.upload_state_lock:
            st = self.upload_state.get(dev_passer)
        if not st:
            print(f"st is none in handle_upload")
            return
        # file_path = st["cache_root"] / str(st["filename"])
        file_path = GAME_CACHE_DIR / str(st[Words.ParamKeys.Metadata.GAME_ID]) / str(st[Words.ParamKeys.Metadata.VERSION]) / str(st[Words.ParamKeys.Metadata.FILE_NAME])
        file_receiver = FileReceiver(dev_sock, file_path)
        success = file_receiver.receive()
        if not success:
            print("warning: file receiving not successful.")
        with self.upload_state_lock:
            self.upload_state[dev_passer]["upload_done"] = True
        file_receiver.close()
        print("exited handle_upload")
        

    # def try_request_and_wait(self, cmd: str, params: dict) -> dict:
    #     result_data = {}
    #     try:
    #         if self.db_worker is None:
    #             raise ConnectionError
    #         result_data = self.db_worker.pend_and_wait(Words.MessageType.REQUEST, 
    #                         {Words.DataKeys.Request.COMMAND: cmd, 
    #                             Words.DataKeys.PARAMS: params}, self.db_response_timeout)
    #         result_data.pop(Words.DataKeys.Response.RESPONDING_ID, None)
    #     except TimeoutError:
    #         result_data[Words.DataKeys.Response.RESULT] = Words.Result.FAILURE
    #         result_data[Words.DataKeys.PARAMS] = {
    #             Words.ParamKeys.Failure.REASON: "Timeout interacting database server exceeded."
    #         }
    #     except ConnectionError:
    #         result_data[Words.DataKeys.Response.RESULT] = Words.Result.FAILURE
    #         result_data[Words.DataKeys.PARAMS] = {
    #             Words.ParamKeys.Failure.REASON: "Lobby server is not connected to database server."
    #         }
    #     except Exception as e:
    #         result_data[Words.DataKeys.Response.RESULT] = Words.Result.FAILURE
    #         result_data[Words.DataKeys.PARAMS] = {
    #             Words.ParamKeys.Failure.REASON: str(e)
    #         }
    #     return result_data
    
    # def reset_db_passer(self):
    #     try:
    #         if self.db_passer:
    #             self.db_passer.close()
    #     except Exception:
    #         pass
    #     self.db_passer = MessageFormatPasser()

