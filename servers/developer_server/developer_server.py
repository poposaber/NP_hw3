import threading
import socket
from base.message_format_passer import MessageFormatPasser
from protocols.protocols import Formats, Words
from typing import Optional
from base.peer_worker import PeerWorker
import time
import uuid
from servers.server_base import ServerBase

DEFAULT_ACCEPT_TIMEOUT = 1.0
DEFAULT_CONNECT_TIMEOUT = 3.0
DEFAULT_RECEIVE_TIMEOUT = 1.0
DEFAULT_HANDSHAKE_TIMEOUT = 5.0
DEFAULT_MAX_HANDSHAKE_TRY_COUNT = 5
DEFAULT_DB_HEARTBEAT_INTERVAL = 10.0
DEFAULT_DB_HEARTBEAT_PATIENCE = 3
DEFAULT_DB_RESPONSE_TIMEOUT = 3.0
DEFAULT_CLIENT_HEARTBEAT_TIMEOUT = 30.0


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
                if passer in self.upload_state.keys() and self.upload_state[passer]["uploading"]:
                    seq, chunk = passer.recv_chunk()
                    if not chunk: # transmitting done
                        self.upload_state[passer]["uploading"] = False
                    # simple sequence monotonic check
                    st = self.upload_state.get(passer)
                    if st['seq'] != -1 and seq != st['seq'] + 1:
                        # out-of-order: ignore (could add buffering)
                        pass
                    else:
                        st['seq'] = seq
                        if chunk:
                            st['file'].write(chunk)
                            st['bytes'] += len(chunk)
                    continue
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
                                game_id = params.get("game_id")
                                version = params.get("version")
                                filename = params.get("filename")
                                size = params.get("size")
                                sha256 = params.get("sha256")
                                if not (game_id and version and filename and isinstance(size, int) and sha256):
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: "Missing upload metadata"
                                    })
                                    continue
                                # prepare cache path
                                from pathlib import Path
                                import os, json, hashlib
                                cache_root = Path(__file__).resolve().parent.parent / "developer_server" / "game_cache" / str(game_id) / str(version)
                                try:
                                    cache_root.mkdir(parents=True, exist_ok=True)
                                except Exception as e:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: f"Cannot create cache: {e}"
                                    })
                                    continue
                                part_path = cache_root / (str(filename) + ".part")
                                try:
                                    f = open(part_path, "wb")
                                except Exception as e:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: f"Cannot open temp file: {e}"
                                    })
                                    continue
                                # record state
                                self.upload_state[passer] = {
                                    "file": f,
                                    "expected_size": size,
                                    "sha256": sha256,
                                    "bytes": 0,
                                    "seq": -1,
                                    "cache_root": cache_root,
                                    "filename": filename,
                                    "game_id": game_id,
                                    "version": version,
                                    "uploading": True
                                }
                                self.send_response(passer, msg_id, Words.Result.SUCCESS)
                            case Words.Command.UPLOAD_END:
                                # finalize the upload: verify and move into place
                                st = self.upload_state.get(passer)
                                if not st:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: "No active upload"
                                    })
                                    continue
                                params = data.get(Words.DataKeys.PARAMS) or {}
                                last_seq = params.get("last_seq")
                                # close file
                                try:
                                    st["file"].flush(); st["file"].close()
                                except Exception:
                                    pass
                                from pathlib import Path
                                import hashlib, json, os
                                part_path = st["cache_root"] / (str(st["filename"]) + ".part")
                                final_path = st["cache_root"] / str(st["filename"])
                                # verify size
                                try:
                                    actual_size = part_path.stat().st_size
                                except Exception:
                                    actual_size = -1
                                if actual_size != st["expected_size"]:
                                    # cleanup
                                    try: part_path.unlink()
                                    except Exception: pass
                                    self.upload_state.pop(passer, None)
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: f"Size mismatch: {actual_size} != {st['expected_size']}"
                                    })
                                    continue
                                # verify sha256
                                try:
                                    h = hashlib.sha256()
                                    with open(part_path, "rb") as rf:
                                        for b in iter(lambda: rf.read(1024*1024), b""):
                                            h.update(b)
                                    digest = h.hexdigest()
                                except Exception as e:
                                    try: part_path.unlink()
                                    except Exception: pass
                                    self.upload_state.pop(passer, None)
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: f"Checksum error: {e}"
                                    })
                                    continue
                                if digest != st["sha256"]:
                                    try: part_path.unlink()
                                    except Exception: pass
                                    self.upload_state.pop(passer, None)
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: "Checksum mismatch"
                                    })
                                    continue
                                # move into place
                                try:
                                    part_path.replace(final_path)
                                    # write metadata
                                    meta = {
                                        "game_id": st["game_id"],
                                        "version": st["version"],
                                        "filename": st["filename"],
                                        "size": st["expected_size"],
                                        "sha256": st["sha256"],
                                    }
                                    (st["cache_root"] / "metadata.json").write_text(__import__("json").dumps(meta, indent=2), encoding="utf-8")
                                except Exception as e:
                                    self.upload_state.pop(passer, None)
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: f"Finalize error: {e}"
                                    })
                                    continue
                                self.upload_state.pop(passer, None)
                                self.send_response(passer, msg_id, Words.Result.SUCCESS)
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

