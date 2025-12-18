import threading
import socket
from base.message_format_passer import MessageFormatPasser
from protocols.protocols import Formats, Words
from typing import Optional
import subprocess
import sys
import os
from base.peer_worker import PeerWorker
import time
import uuid
from servers.server_base import ServerBase
from base.file_receiver import FileReceiver
from base.file_sender import FileSender
import queue
from pathlib import Path
import zipfile
import os
import shutil

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

class LobbyServer(ServerBase):
    def __init__(self, host: str = "0.0.0.0", port: int = 21354, 
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
        super().__init__(host, port, db_host, db_port, Words.Roles.LOBBYSERVER, 
                         accept_timeout, connect_timeout, receive_timeout, handshake_timeout, 
                         db_response_timeout, max_handshake_try_count, db_heartbeat_interval, 
                         db_heartbeat_patience, client_heartbeat_timeout)
        
        self.passer_player_dict: dict[MessageFormatPasser, str | None] = {}
        self.player_passer_dict: dict[str, MessageFormatPasser] = {}
        self.passer_player_lock = threading.Lock()
        self.room_dict: dict[str, dict] = {}

        self.download_state: dict[MessageFormatPasser, dict] = {}
        self.download_state_lock = threading.Lock()
        self.download_from_database_queue: queue.Queue[Path] = queue.Queue() # storing path of .zip
        # ensure cache dir exists
        GAME_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # mapping transfer_id -> {'path': Path, 'done': bool, 'success': bool}
        self._transfer_state: dict[str, dict] = {}
        self._transfer_state_lock = threading.Lock()
        # map room_name -> subprocess.Popen for running game server
        self._game_processes: dict[str, subprocess.Popen] = {}
        self._game_logfiles: dict[str, any] = {}

    def on_new_connection(self, received_message_id: str, role: str, passer: MessageFormatPasser, handshake_data: dict):
        match role:
            case Words.Roles.PLAYER:
                self.send_response(passer, received_message_id, Words.Result.SUCCESS)
                self.handle_player(passer)
            case _:
                print(f"Unknown role: {role}")

    def handle_player(self, passer: MessageFormatPasser):
        with self.passer_player_lock:
            self.passer_player_dict[passer] = None
        passer.settimeout(self.receive_timeout)
        last_hb_time = time.time()
        while not self.stop_event.is_set():
            try:
                msg_id, msg_type, data = passer.receive_args(Formats.MESSAGE)
                match msg_type:
                    case Words.MessageType.REQUEST:
                        assert isinstance(data, dict)
                        self._process_request(passer, msg_id, data)
                    case Words.MessageType.HEARTBEAT:
                        # time.sleep(12)
                        last_hb_time = time.time()
                        self.send_response(passer, msg_id, Words.Result.SUCCESS)
            except TimeoutError:
                if time.time() - last_hb_time > self.client_heartbeat_timeout:
                    print(f"[LobbyServer] client heartbeat timeout (>{self.client_heartbeat_timeout}s), terminating connection")
                    break
                continue
            except ConnectionError as e:
                print(f"[LobbyServer] ConnectionError raised in handle_player: {e}")
                break
            except Exception as e:
                print(f"[LobbyServer] exception raised in handle_player: {e}")
                break
        with self.passer_player_lock:
            uname = self.passer_player_dict.pop(passer, None)
            if uname:
                self.player_passer_dict.pop(uname, None)

    def _process_request(self, passer: MessageFormatPasser, msg_id: str, data: dict):
        try:
            cmd = data.get(Words.DataKeys.Request.COMMAND)
            match cmd:
                case Words.Command.SYNC_LOBBY_STATUS:
                    with self.passer_player_lock:
                        online_players = list(self.player_passer_dict.keys())
                        try:
                            plr = self.passer_player_dict.get(passer)
                            assert isinstance(plr, str)
                            online_players.remove(plr)
                        except Exception:
                            pass
                    self.send_response(passer, msg_id, Words.Result.SUCCESS, {
                        Words.ParamKeys.LobbyStatus.ONLINE_PLAYERS: online_players,
                        Words.ParamKeys.LobbyStatus.ROOMS: self.room_dict
                    })
                case Words.Command.CHECK_STORE:
                    result_data = self.try_request_and_wait(Words.Command.CHECK_STORE, {})
                    result = result_data.get(Words.DataKeys.Response.RESULT) or Words.Result.FAILURE
                    params = result_data.get(Words.DataKeys.PARAMS) or {
                        Words.ParamKeys.Failure.REASON: "Unknown result."
                    }
                    self.send_response(passer, msg_id, result, params)
                case Words.Command.DOWNLOAD_START:
                    params = data.get(Words.DataKeys.PARAMS)
                    assert isinstance(params, dict)
                    result_data = self.try_request_and_wait(Words.Command.DOWNLOAD_START, params)
                    params_from_db = result_data.get(Words.DataKeys.PARAMS)
                    assert isinstance(params_from_db, dict)

                    if result_data.get(Words.DataKeys.Response.RESULT) != Words.Result.SUCCESS:
                        self.send_response(passer, msg_id, Words.Result.FAILURE, params_from_db)
                        return

                    # Start a background transfer: connect to DB and download into cache,
                    # then serve the cached file to the requesting client in a separate thread.
                    db_port = params_from_db.get(Words.ParamKeys.Success.PORT)
                    try:
                        transfer_id = str(uuid.uuid4())
                        # choose cache path (use game id if provided)
                        gid = params.get(Words.ParamKeys.Metadata.GAME_ID) or transfer_id
                        fname = params_from_db.get(Words.ParamKeys.Metadata.FILE_NAME) or f"{gid}.zip"
                        dst_dir = GAME_CACHE_DIR / str(gid)
                        dst_dir.mkdir(parents=True, exist_ok=True)
                        dst_path = dst_dir / fname

                        # connect to database transfer port
                        temp_db_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        temp_db_sock.settimeout(self.connect_timeout + 5)
                        if db_port is None:
                            raise RuntimeError("database did not provide transfer port")
                        temp_db_sock.connect((self.db_host, int(db_port)))
                        print("######database server connected.")

                        with self._transfer_state_lock:
                            self._transfer_state[transfer_id] = {"path": dst_path, "done": False, "success": False}

                        # download thread: receives file from DB and writes to dst_path
                        def dl_thread():
                            try:
                                fr = FileReceiver(temp_db_sock, dst_path)
                                print("start download. Downloading...")
                                ok = fr.receive()
                                fr.close()
                                with self._transfer_state_lock:
                                    self._transfer_state[transfer_id]["done"] = True
                                    self._transfer_state[transfer_id]["success"] = bool(ok)
                            except Exception as e:
                                print(f"[LobbyServer] download thread error: {e}")
                                with self._transfer_state_lock:
                                    self._transfer_state[transfer_id]["done"] = True
                                    self._transfer_state[transfer_id]["success"] = False

                        threading.Thread(target=dl_thread, daemon=True).start()

                        # prepare server socket for client to connect and receive the file
                        temp_server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        temp_server_sock.bind(("0.0.0.0", 0))
                        temp_server_sock.listen(1)
                        client_port = temp_server_sock.getsockname()[1]

                        # serve thread: accept client, wait for download completion, then send file
                        def serve_thread():
                            try:
                                client_sock, addr = temp_server_sock.accept()
                                print(f"client connected: {addr}")
                                temp_server_sock.close()
                                # wait for download to complete (with timeout)
                                waited = 0.0
                                interval = 0.1
                                timeout = max(30.0, self.db_response_timeout * 10)
                                while True:
                                    with self._transfer_state_lock:
                                        st = self._transfer_state.get(transfer_id)
                                    if st is None:
                                        client_sock.close()
                                        return
                                    if st.get("done"):
                                        break
                                    time.sleep(interval)
                                    waited += interval
                                    if waited >= timeout:
                                        client_sock.close()
                                        return

                                # if file downloaded successfully, send it
                                with self._transfer_state_lock:
                                    path = self._transfer_state[transfer_id]["path"]
                                    success = self._transfer_state[transfer_id]["success"]
                                if not success or not path.exists():
                                    client_sock.close()
                                    return
                                fs = FileSender(client_sock, path)
                                try:
                                    fs.send()
                                finally:
                                    fs.close()
                            except Exception as e:
                                print(f"[LobbyServer] serve thread error: {e}")

                        threading.Thread(target=serve_thread, daemon=True).start()

                        # reply to client with port where they should connect
                        self.send_response(passer, msg_id, Words.Result.SUCCESS, {
                            Words.ParamKeys.Success.PORT: client_port,
                        })
                    except Exception as e:
                        print(f"[LobbyServer] failed to start transfer: {e}")
                        self.send_response(passer, msg_id, Words.Result.FAILURE, {Words.ParamKeys.Failure.REASON: str(e)})
                case Words.Command.CREATE_ROOM:
                    params = data.get(Words.DataKeys.PARAMS)
                    assert isinstance(params, dict)
                    room_name = str(params.get(Words.ParamKeys.Room.ROOM_NAME))
                    game_id = params.get(Words.ParamKeys.Room.GAME_ID)
                    if not room_name:
                        self.send_response(passer, msg_id, Words.Result.FAILURE, {
                            Words.ParamKeys.Failure.REASON: "missing field: room_name"
                        })
                        return
                    # get the username of the caller
                    username = self.passer_player_dict.get(passer)
                    result_data = self.try_request_and_wait(Words.Command.CREATE_ROOM, {
                        Words.ParamKeys.Room.USERNAME: username,
                        Words.ParamKeys.Room.ROOM_NAME: room_name,
                        Words.ParamKeys.Room.GAME_ID: game_id
                    })
                    result = result_data.get(Words.DataKeys.Response.RESULT)
                    params = result_data.get(Words.DataKeys.PARAMS)
                    expected_players = params.get(Words.ParamKeys.Room.EXPECTED_PLAYERS) if params else 0
                    if result != Words.Result.SUCCESS:
                        self.send_response(passer, msg_id, Words.Result.FAILURE, params)
                        return
                    self.send_response(passer, msg_id, Words.Result.SUCCESS, params)
                    # register room in lobby's local view
                    self.room_dict[room_name] = {
                        Words.ParamKeys.Room.OWNER: username,
                        Words.ParamKeys.Room.GAME_ID: game_id,
                        Words.ParamKeys.Room.PLAYER_LIST: [username] if username else [],
                        Words.ParamKeys.Room.EXPECTED_PLAYERS: expected_players,
                        Words.ParamKeys.Room.IS_PLAYING: False
                    }
                    # notify all online players about new room
                    try:
                        now_room = self.room_dict.get(room_name)
                        for p, uname in list(self.passer_player_dict.items()):
                            if uname is not None:
                                try:
                                    self.send_event(p, Words.EventName.ROOM_UPDATED, {Words.ParamKeys.Room.ROOM_NAME: room_name, Words.ParamKeys.Room.NOW_ROOM_DATA: now_room})
                                except Exception:
                                    pass
                    except Exception as e:
                        print(f"[LobbyServer] notify create_room error: {e}")
                    # start background fetch of game files into lobby cache and notify owner when ready
                    try:
                        owner = self.passer_player_dict.get(passer)
                        if isinstance(game_id, str) and owner:
                            threading.Thread(target=self._fetch_game_for_room, args=(game_id, owner), daemon=True).start()
                    except Exception as e:
                        print(f"[LobbyServer] failed to start background fetch thread: {e}")
                case Words.Command.JOIN_ROOM:
                    params = data.get(Words.DataKeys.PARAMS)
                    assert isinstance(params, dict)
                    room_name = params.get(Words.ParamKeys.Room.ROOM_NAME)
                    # prefer authenticated username
                    username = self.passer_player_dict.get(passer)
                    if not room_name or not isinstance(room_name, str):
                        self.send_response(passer, msg_id, Words.Result.FAILURE, {Words.ParamKeys.Failure.REASON: 'missing room_name'})
                        return
                    now_room = self.room_dict.get(room_name)
                    if now_room is None:
                        self.send_response(passer, msg_id, Words.Result.FAILURE, {Words.ParamKeys.Failure.REASON: 'room not found'})
                        return
                    result_data = self.try_request_and_wait(Words.Command.JOIN_ROOM, {
                        Words.ParamKeys.Room.ROOM_NAME: room_name,
                        Words.ParamKeys.Room.USERNAME: username
                    })
                    if result_data.get(Words.DataKeys.Response.RESULT) != Words.Result.SUCCESS:
                        params = result_data.get(Words.DataKeys.PARAMS)
                        self.send_response(passer, msg_id, Words.Result.FAILURE, params)
                        return

                    # update lobby's local view
                    players = now_room.get(Words.ParamKeys.Room.PLAYER_LIST) or []
                    expected = now_room.get(Words.ParamKeys.Room.EXPECTED_PLAYERS) or 0
                    if username in players:
                        # already in room
                        return
                    if expected and len(players) >= int(expected):
                        return
                    # add player
                    players.append(username)
                    now_room[Words.ParamKeys.Room.PLAYER_LIST] = players
                    self.room_dict[room_name] = now_room
                    # notify all online players about room update
                    try:
                        for p, uname in list(self.passer_player_dict.items()):
                            if uname is not None:
                                passer_target = p
                                try:
                                    self.send_event(passer_target, Words.EventName.ROOM_UPDATED, {Words.ParamKeys.Room.ROOM_NAME: room_name, Words.ParamKeys.Room.NOW_ROOM_DATA: now_room})
                                except Exception:
                                    pass
                    except Exception as e:
                        print(f"[LobbyServer] notify join_room error: {e}")
                    self.send_response(passer, msg_id, Words.Result.SUCCESS, {Words.ParamKeys.Room.NOW_ROOM_DATA: now_room})
                case Words.Command.LEAVE_ROOM:
                    params = data.get(Words.DataKeys.PARAMS) or {}
                    room_name = params.get(Words.ParamKeys.Room.ROOM_NAME)
                    # prefer authenticated username
                    username = self.passer_player_dict.get(passer) or params.get(Words.ParamKeys.Room.USERNAME)
                    # forward to DB
                    result_data = self.try_request_and_wait(Words.Command.LEAVE_ROOM, {
                        Words.ParamKeys.Room.ROOM_NAME: room_name,
                        Words.ParamKeys.Room.USERNAME: username
                    })
                    if result_data.get(Words.DataKeys.Response.RESULT) != Words.Result.SUCCESS:
                        self.send_response(passer, msg_id, Words.Result.FAILURE, result_data.get(Words.DataKeys.PARAMS))
                        return
                    params_from_db = result_data.get(Words.DataKeys.PARAMS) or {}
                    rn = params_from_db.get(Words.ParamKeys.Room.ROOM_NAME)
                    now_room = params_from_db.get(Words.ParamKeys.Room.NOW_ROOM_DATA)
                    # apply to local view
                    if rn is None:
                        self.send_response(passer, msg_id, Words.Result.FAILURE, {Words.ParamKeys.Failure.REASON: 'db did not return room name'})
                        return
                    if now_room is None:
                        self.room_dict.pop(rn, None)
                    else:
                        self.room_dict[rn] = now_room
                    # notify all online players about room update
                    try:
                        for p, uname in list(self.passer_player_dict.items()):
                            if uname is not None:
                                try:
                                    self.send_event(p, Words.EventName.ROOM_UPDATED, {Words.ParamKeys.Room.ROOM_NAME: rn, Words.ParamKeys.Room.NOW_ROOM_DATA: now_room})
                                except Exception:
                                    pass
                    except Exception as e:
                        print(f"[LobbyServer] notify leave_room error: {e}")
                    # also remove from local player's view
                    self._remove_player_from_rooms(username)
                    self.send_response(passer, msg_id, Words.Result.SUCCESS, params_from_db)
                case Words.Command.START_GAME:
                    params = data.get(Words.DataKeys.PARAMS) or {}
                    room_name = params.get(Words.ParamKeys.Room.ROOM_NAME)
                    username = self.passer_player_dict.get(passer)
                    if not room_name:
                        self.send_response(passer, msg_id, Words.Result.FAILURE, {Words.ParamKeys.Failure.REASON: "missing room_name"})
                        return
                    room_info = self.room_dict.get(room_name)
                    if room_info is None:
                        self.send_response(passer, msg_id, Words.Result.FAILURE, {Words.ParamKeys.Failure.REASON: "room not found"})
                        return
                    # only owner can start
                    owner = room_info.get(Words.ParamKeys.Room.OWNER)
                    if owner != username:
                        self.send_response(passer, msg_id, Words.Result.FAILURE, {Words.ParamKeys.Failure.REASON: "only owner can start the game"})
                        return
                    # ask DB to mark room as playing
                    result_data = self.try_request_and_wait(Words.Command.START_GAME, {Words.ParamKeys.Room.ROOM_NAME: room_name})
                    if result_data.get(Words.DataKeys.Response.RESULT) != Words.Result.SUCCESS:
                        params_from_db = result_data.get(Words.DataKeys.PARAMS) or {}
                        self.send_response(passer, msg_id, Words.Result.FAILURE, params_from_db)
                        return
                    params_from_db = result_data.get(Words.DataKeys.PARAMS) or {}
                    now_room = params_from_db.get(Words.ParamKeys.Room.NOW_ROOM_DATA)
                    if now_room and isinstance(now_room, dict):
                        self.room_dict[room_name] = now_room
                    else:
                        self.room_dict.pop(room_name, None)

                    # start game server subprocess from cache
                    try:
                        game_id = room_info.get(Words.ParamKeys.Room.GAME_ID)
                        if not game_id:
                            raise RuntimeError("missing game_id for room")
                        server_main = GAME_CACHE_DIR / str(game_id) / "server" / "__main__.py"
                        if not server_main.exists():
                            # try fallback: any .py under server folder
                            sdir = GAME_CACHE_DIR / str(game_id) / "server"
                            if sdir.exists() and sdir.is_dir():
                                for f in sdir.iterdir():
                                    if f.suffix == ".py":
                                        server_main = f
                                        break
                        if not server_main.exists():
                            raise FileNotFoundError(f"server entry not found for game {game_id}")

                        # choose an available port for the game server to avoid EADDRINUSE
                        # try:
                        #     temp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        #     temp_sock.bind(("0.0.0.0", 0))
                        #     chosen_port = temp_sock.getsockname()[1]
                        #     temp_sock.close()
                        # except Exception:
                        #     chosen_port = None
                        # if chosen_port:
                        #     cmd = [sys.executable, str(server_main), str(chosen_port)]
                        # else:
                        cmd = [sys.executable, str(server_main)]
                        kwargs = {"cwd": str(server_main.parent)}
                        if os.name == 'nt':
                            kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
                        else:
                            print("Starting game server without new console (non-Windows OS).")
                            kwargs["start_new_session"] = True
                            kwargs["stdin"] = subprocess.DEVNULL
                            kwargs["close_fds"] = True
                            try:
                                log_dir = server_main.parent
                                log_dir.mkdir(parents=True, exist_ok=True)
                            except Exception:
                                pass
                            try:
                                log_path = server_main.parent / "server.log"
                                lf = open(log_path, "a", buffering=1, encoding="utf-8", errors="ignore")
                                kwargs["stdout"] = lf
                                kwargs["stderr"] = subprocess.STDOUT
                                # keep reference to logfile so it isn't garbage-collected/closed
                                self._game_logfiles[room_name] = lf
                            except Exception:
                                # fallback: don't redirect stdout/stderr if log open fails
                                pass
                        proc = subprocess.Popen(cmd, **kwargs)
                        self._game_processes[room_name] = proc
                        # wait briefly then notify players
                        time.sleep(1.0)
                        players = self.room_dict.get(room_name, {}).get(Words.ParamKeys.Room.PLAYER_LIST) or []
                        with self.passer_player_lock:
                            for p, uname in list(self.passer_player_dict.items()):
                                if uname and uname in players:
                                    try:
                                        ev = {Words.ParamKeys.Metadata.GAME_ID: game_id, Words.ParamKeys.Room.ROOM_NAME: room_name}
                                        # if chosen_port:
                                        #     ev[Words.ParamKeys.Success.PORT] = chosen_port
                                        #     try:
                                        #         ev['host'] = self.host
                                        #     except Exception:
                                        #         pass
                                        self.send_event(p, Words.EventName.GAME_STARTED, ev)
                                    except Exception:
                                        pass
                        self.send_response(passer, msg_id, Words.Result.SUCCESS, {Words.ParamKeys.Room.ROOM_NAME: room_name, Words.ParamKeys.Room.NOW_ROOM_DATA: self.room_dict.get(room_name)})
                    except Exception as e:
                        print(f"[LobbyServer] failed to start game server: {e}")
                        self.send_response(passer, msg_id, Words.Result.FAILURE, {Words.ParamKeys.Failure.REASON: str(e)})
                case Words.Command.LEAVE_ROOM:
                    params = data.get(Words.DataKeys.PARAMS)
                    assert isinstance(params, dict)
                    room_name = params.get(Words.ParamKeys.Room.ROOM_NAME)
                    username = self.passer_player_dict.get(passer)
                    if not room_name or not username:
                        self.send_response(passer, msg_id, Words.Result.FAILURE, {Words.ParamKeys.Failure.REASON: 'missing fields'})
                        return
                    # forward to database
                    result_data = self.try_request_and_wait(Words.Command.LEAVE_ROOM, {
                        Words.ParamKeys.Room.ROOM_NAME: room_name,
                        Words.ParamKeys.Room.USERNAME: username
                    })
                    if result_data.get(Words.DataKeys.Response.RESULT) != Words.Result.SUCCESS:
                        self.send_response(passer, msg_id, Words.Result.FAILURE, result_data.get(Words.DataKeys.PARAMS))
                        return

                    params_from_db = result_data.get(Words.DataKeys.PARAMS) or {}
                    rn = params_from_db.get(Words.ParamKeys.Room.ROOM_NAME)
                    now_room = params_from_db.get(Words.ParamKeys.Room.NOW_ROOM_DATA)
                    # apply to local view
                    if rn is None:
                        self.send_response(passer, msg_id, Words.Result.FAILURE, {Words.ParamKeys.Failure.REASON: 'db did not return room name'})
                        return
                    if now_room is None:
                        # room deleted
                        self.room_dict.pop(rn, None)
                    else:
                        self.room_dict[rn] = now_room

                    # notify all online players about room update
                    try:
                        for p, uname in list(self.passer_player_dict.items()):
                            if uname is not None:
                                try:
                                    self.send_event(p, Words.EventName.ROOM_UPDATED, {Words.ParamKeys.Room.ROOM_NAME: rn, Words.ParamKeys.Room.NOW_ROOM_DATA: now_room})
                                except Exception:
                                    pass
                    except Exception as e:
                        print(f"[LobbyServer] notify leave_room error: {e}")

                    # also remove from local player's view
                    self._remove_player_from_rooms(username)
                    self.send_response(passer, msg_id, Words.Result.SUCCESS, params_from_db)
                case Words.Command.LOGIN:
                    params = data.get(Words.DataKeys.PARAMS)
                    assert isinstance(params, dict)
                    username = params.get(Words.ParamKeys.Login.USERNAME)
                    assert isinstance(username, str)
                    login_data = self.try_request_and_wait(Words.Command.LOGIN, params)

                    if login_data[Words.DataKeys.Response.RESULT] == Words.Result.SUCCESS:
                        with self.passer_player_lock:
                            self.passer_player_dict[passer] = username
                            self.player_passer_dict[username] = passer
                        self.send_response(passer, msg_id, Words.Result.SUCCESS)
                        self.broadcast_player_online(username)
                    elif login_data[Words.DataKeys.Response.RESULT] == Words.Result.FAILURE:
                        params = login_data.get(Words.DataKeys.PARAMS)
                        assert isinstance(params, dict)
                        self.send_response(passer, msg_id, Words.Result.FAILURE, params)
                    else:
                        self.send_response(passer, msg_id, Words.Result.FAILURE, {
                            Words.ParamKeys.Failure.REASON: "Unknown login result."
                        })
                case Words.Command.REGISTER:
                    params = data.get(Words.DataKeys.PARAMS)
                    assert isinstance(params, dict)
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
                    with self.passer_player_lock:
                        username = self.passer_player_dict.get(passer)
                    if not username:
                        self.send_response(passer, msg_id, Words.Result.FAILURE, {
                            Words.ParamKeys.Failure.REASON: "Player not logged in yet."
                        })
                        return
                    result_data = self.try_request_and_wait(Words.Command.LOGOUT, {
                        Words.ParamKeys.Logout.USERNAME: username
                    })
                    self.send_response(passer, msg_id, result_data[Words.DataKeys.Response.RESULT], result_data.get(Words.DataKeys.PARAMS))
                    with self.passer_player_lock:
                        self.passer_player_dict[passer] = None
                        self.player_passer_dict.pop(username, None)
                    # remove player from any rooms in lobby view and notify others
                    if username:
                        # if DB returned room info, broadcast update
                        params_from_db = result_data.get(Words.DataKeys.PARAMS) or {}
                        rn = params_from_db.get(Words.ParamKeys.Room.ROOM_NAME)
                        now_room = params_from_db.get(Words.ParamKeys.Room.NOW_ROOM_DATA)
                        if rn:
                            try:
                                for p, uname in list(self.passer_player_dict.items()):
                                    if uname is not None:
                                        try:
                                            self.send_event(p, Words.EventName.ROOM_UPDATED, {Words.ParamKeys.Room.ROOM_NAME: rn, Words.ParamKeys.Room.NOW_ROOM_DATA: now_room})
                                        except Exception:
                                            pass
                            except Exception as e:
                                print(f"[LobbyServer] notify logout leave_room error: {e}")
                        self._remove_player_from_rooms(username)
                    self.broadcast_player_offline(username)
                case Words.Command.EXIT:
                    with self.passer_player_lock:
                        username = self.passer_player_dict.get(passer)
                    if username:
                        result_data = self.try_request_and_wait(Words.Command.LOGOUT, {
                            Words.ParamKeys.Logout.USERNAME: username
                        })
                        with self.passer_player_lock:
                            self.passer_player_dict[passer] = None
                            self.player_passer_dict.pop(username, None)
                        # handle room update returned from DB, notify others
                        params = result_data.get(Words.DataKeys.PARAMS) or {}
                        room_name = params.get(Words.ParamKeys.Room.ROOM_NAME)
                        now_room_data = params.get(Words.ParamKeys.Room.NOW_ROOM_DATA)
                        if room_name:
                            if now_room_data and isinstance(now_room_data, dict):
                                self.room_dict[room_name] = now_room_data
                            else:
                                self.room_dict.pop(room_name, None)
                            try:
                                for p, uname in list(self.passer_player_dict.items()):
                                    if uname is not None:
                                        try:
                                            self.send_event(p, Words.EventName.ROOM_UPDATED, {Words.ParamKeys.Room.ROOM_NAME: room_name, Words.ParamKeys.Room.NOW_ROOM_DATA: now_room_data})
                                        except Exception:
                                            pass
                            except Exception as e:
                                print(f"[LobbyServer] notify exit leave_room error: {e}")
                        # remove player from rooms before broadcasting offline
                        self._remove_player_from_rooms(username)
                        self.broadcast_player_offline(username)

                    self.send_response(passer, msg_id, Words.Result.SUCCESS)
                    time.sleep(3)
        except Exception as e:
            print(f"[LobbyServer] _process_request error: {e}")

    def download_from_db(self, params: dict):
        # simple wrapper to fetch a game into cache (no owner notification)
        try:
            game_id = params.get(Words.ParamKeys.Metadata.GAME_ID)
            if not game_id:
                return False
            # reuse fetch logic; no owner to notify
            self._fetch_game_for_room(str(game_id), None)
            return True
        except Exception as e:
            print(f"[LobbyServer] download_from_db error: {e}")
            return False
        
    def _safe_extract(self, zip_path: Path, dest_dir: Path) -> bool:
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path, 'r') as z:
                for info in z.infolist():
                    member_path = dest_dir.joinpath(*Path(info.filename).parts)
                    if not str(member_path.resolve()).startswith(str(dest_dir.resolve())):
                        # suspicious path -> skip
                        continue
                    if info.is_dir():
                        member_path.mkdir(parents=True, exist_ok=True)
                    else:
                        member_path.parent.mkdir(parents=True, exist_ok=True)
                        with member_path.open('wb') as outf:
                            outf.write(z.read(info.filename))
            return True
        except Exception as e:
            print(f"[LobbyServer] _safe_extract error: {e}")
            return False

    def _fetch_game_for_room(self, game_id: str, owner_username: Optional[str]):
        try:
            cache_dir = GAME_CACHE_DIR / str(game_id)
            # if already present (metadata), notify immediately
            # if (cache_dir / 'metadata.json').exists() or (cache_dir / 'big_metadata.json').exists():
            #     passer = None
            #     if owner_username:
            #         passer = self.player_passer_dict.get(owner_username)
            #     if passer:
            #         self.send_event(passer, 'game_fetched', {Words.ParamKeys.Metadata.GAME_ID: game_id, 'path': str(cache_dir)})
            #     return

            # request DB to start download
            resp = self.try_request_and_wait(Words.Command.DOWNLOAD_START, {Words.ParamKeys.Metadata.GAME_ID: game_id})
            params_from_db = resp.get(Words.DataKeys.PARAMS) or {}
            if resp.get(Words.DataKeys.Response.RESULT) != Words.Result.SUCCESS:
                print(f"[LobbyServer] DB refused download for {game_id}: {params_from_db}")
                return

            db_port = params_from_db.get(Words.ParamKeys.Success.PORT)
            if db_port is None:
                print(f"[LobbyServer] DB did not return port for {game_id}")
                return

            dst_dir = cache_dir
            dst_dir.mkdir(parents=True, exist_ok=True)
            fname = params_from_db.get(Words.ParamKeys.Metadata.FILE_NAME) or f"{game_id}.zip"
            dst_path = dst_dir / fname

            # connect to db and receive file
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(self.connect_timeout + 5)
                s.connect((self.db_host, int(db_port)))
                fr = FileReceiver(s, dst_path)
                ok = fr.receive()
                fr.close()
                if not ok:
                    print(f"[LobbyServer] failed to download game {game_id}")
                    return

            # extract safely into cache dir
            extracted_ok = self._safe_extract(dst_path, dst_dir)
            if not extracted_ok:
                print(f"[LobbyServer] failed to extract game {game_id}")
                return

            # notify owner
            passer = None
            if owner_username:
                passer = self.player_passer_dict.get(owner_username)
            if passer:
                self.send_event(passer, Words.EventName.GAME_FETCHED, {Words.ParamKeys.Metadata.GAME_ID: game_id, 'path': str(dst_dir)})
        except Exception as e:
            print(f"[LobbyServer] _fetch_game_for_room error: {e}")
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
    def send_event(self, passer: MessageFormatPasser, event_name: str, params: Optional[dict] = None):
        message_id = str(uuid.uuid4())
        data: dict[str, str | dict] = {
            Words.DataKeys.Event.EVENT_NAME: event_name, 
        }
        if params is not None:
            data[Words.DataKeys.PARAMS] = params
        passer.send_args(Formats.MESSAGE, message_id, Words.MessageType.EVENT, data)

    def send_player_online(self, passer: MessageFormatPasser, player_name: str):
        self.send_event(passer, Words.EventName.PLAYER_ONLINE, {
            Words.ParamKeys.PlayerOnline.PLAYER_NAME: player_name
        })

    def broadcast_player_online(self, player_name: str):
        with self.passer_player_lock:
            targets = [p for p, uname in self.passer_player_dict.items() if uname is not None and uname != player_name]
        for p in targets:
            try:
                self.send_player_online(p, player_name)
            except Exception as e:
                print(f"[LobbyServer] send_player_online error: {e}")
    
    def send_player_offline(self, passer: MessageFormatPasser, player_name: str):
        self.send_event(passer, Words.EventName.PLAYER_OFFLINE, {
            Words.ParamKeys.PlayerOnline.PLAYER_NAME: player_name
        })

    def broadcast_player_offline(self, player_name: str):
        with self.passer_player_lock:
            targets = [p for p, uname in self.passer_player_dict.items() if uname is not None and uname != player_name]
        for p in targets:
            try:
                self.send_player_offline(p, player_name)
            except Exception as e:
                print(f"[LobbyServer] send_player_offline error: {e}")

    def _remove_player_from_rooms(self, username: str):
        try:
            if not username:
                return
            removed_rooms = []
            for rname, rdata in list(self.room_dict.items()):
                pl = rdata.get(Words.ParamKeys.Room.PLAYER_LIST) or []
                if username in pl:
                    pl = [p for p in pl if p != username]
                    rdata[Words.ParamKeys.Room.PLAYER_LIST] = pl
                    # if owner left, choose new owner or delete room
                    owner = rdata.get(Words.ParamKeys.Room.OWNER)
                    if owner == username:
                        if pl:
                            rdata[Words.ParamKeys.Room.OWNER] = pl[0]
                        else:
                            # no players left -> remove room
                            self.room_dict.pop(rname, None)
                            removed_rooms.append(rname)
                            continue
                    self.room_dict[rname] = rdata
            # TODO: notify affected players if needed
        except Exception as e:
            print(f"[LobbyServer] _remove_player_from_rooms error: {e}")

