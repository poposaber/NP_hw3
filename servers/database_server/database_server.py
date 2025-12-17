# next: 
# supply only two connection, one from lobby server, one from developer server 

import threading
import socket
from base.message_format_passer import MessageFormatPasser
from protocols.protocols import Formats, Words
from typing import Optional
import time
import uuid
import json
import os
from pathlib import Path
from base.file_receiver import FileReceiver
import hashlib
from base.file_checker import FileChecker
from base.file_sender import FileSender

DEFAULT_ACCEPT_TIMEOUT = 1.0
DEFAULT_RECEIVE_TIMEOUT = 1.0
DEFAULT_HANDSHAKE_TIMEOUT = 5.0
DEFAULT_HEARTBEAT_TIMEOUT = 30.0

PARENT_DIR = Path(__file__).resolve().parents[0]

DATA_DIR = PARENT_DIR / "data"  # parents[0]=current dir, parents[1]=上一層, parents[2]=上二層
DATA_DIR.mkdir(parents=True, exist_ok=True)

PLAYER_DB_FILE = DATA_DIR / "player_db.json"
ROOM_DB_FILE = DATA_DIR / "room_db.json"

DEVELOPER_DB_FILE = DATA_DIR / "developer_db.json"

GAME_FOLDER = PARENT_DIR / "games"
GAME_FOLDER.mkdir(parents=True, exist_ok=True)

class DatabaseServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 32132, 
                 accept_timeout = DEFAULT_ACCEPT_TIMEOUT, 
                 receive_timeout = DEFAULT_RECEIVE_TIMEOUT, 
                 handshake_timeout = DEFAULT_HANDSHAKE_TIMEOUT, 
                 heartbeat_timeout = DEFAULT_HEARTBEAT_TIMEOUT):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = host
        self.port = port
        self.accept_timeout = accept_timeout
        self.receive_timeout = receive_timeout
        self.handshake_timeout = handshake_timeout
        self.heartbeat_timeout = heartbeat_timeout

        self.stop_event = threading.Event()

        self.lobby_passer: Optional[MessageFormatPasser] = None
        self.developer_passer: Optional[MessageFormatPasser] = None

        self.player_db = self.load_player_db()
        self.developer_db = self.load_developer_db()
        self.room_db = self.load_room_db()

        self.upload_params: dict = {}
        self.upload_lock = threading.Lock()

    def load_db(self, path: Path):
        if not os.path.exists(path):
            return {}
        with open(path, 'r') as f:
            return json.load(f)
    
    def save_db(self, path: Path, data: dict):
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    def load_player_db(self):
        return self.load_db(PLAYER_DB_FILE)
        
    def save_player_db(self):
        self.save_db(PLAYER_DB_FILE, self.player_db)

    def load_developer_db(self):
        return self.load_db(DEVELOPER_DB_FILE)
        
    def save_developer_db(self):
        self.save_db(DEVELOPER_DB_FILE, self.developer_db)

    def load_room_db(self):
        return self.load_db(ROOM_DB_FILE)
        
    def save_room_db(self):
        self.save_db(ROOM_DB_FILE, self.room_db)

    # def load_room_db(self):
    #     if not os.path.exists(ROOM_DB_FILE):
    #         return {}
    #     with open(ROOM_DB_FILE, 'r') as f:
    #         return json.load(f)

    # def save_room_db(self):
    #     with open(ROOM_DB_FILE, 'w') as f:
    #         json.dump(self.room_db, f, indent=2)

    def run(self):
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(5)
        self.server_sock.settimeout(self.accept_timeout)
        print(f"Database server listening on {self.host}:{self.port}")
        self.accept_connections()

    def accept_connections(self) -> None:
        while not self.stop_event.is_set():
            try:
                connection_sock, addr = self.server_sock.accept()
                print(f"Accepted connection from {addr}")
                msgfmt_passer = MessageFormatPasser(connection_sock)
                #self.clients.append(msgfmt_passer)
                #self.user_infos[msgfmt_passer] = UserInfo()
                # self.connections.append(msgfmt_passer)
                # print(f"Active connections: {len(self.connections)}")
                # Since connection may be client, db, or game server, start a thread to handle initial handshake
                threading.Thread(target=self.handle_connections, args=(msgfmt_passer,)).start()
                
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[DatabaseServer] Exception in accept_connections: {e}")
    
    def handle_connections(self, msgfmt_passer: MessageFormatPasser) -> None:
        """Check handshake and pass to corresponding methods."""
        try:
            #while True:
            msgfmt_passer.settimeout(self.handshake_timeout)
            received_message_id, message_type, data = msgfmt_passer.receive_args(Formats.MESSAGE)
            if message_type != Words.MessageType.HANDSHAKE:
                print(f"[DatabaseServer] received message_type {message_type}, expected {Words.MessageType.HANDSHAKE}")

            role = data[Words.DataKeys.Handshake.ROLE]
            match role:
                case Words.Roles.LOBBYSERVER:
                    if self.lobby_passer is None:
                        self.lobby_passer = msgfmt_passer
                        self.send_response(msgfmt_passer, received_message_id, Words.Result.SUCCESS)
                        self.handle_lobby(msgfmt_passer)
                        self.lobby_passer.close()
                        self.lobby_passer = None
                    else:
                        self.send_response(msgfmt_passer, received_message_id, Words.Result.FAILURE, 
                                           {Words.ParamKeys.Failure.REASON: "already connected one lobby server"})
                case Words.Roles.DEVELOPERSERVER:
                    if self.developer_passer is None:
                        self.developer_passer = msgfmt_passer
                        self.send_response(msgfmt_passer, received_message_id, Words.Result.SUCCESS)
                        self.handle_developer(msgfmt_passer)
                        self.developer_passer.close()
                        self.developer_passer = None
                    else:
                        self.send_response(msgfmt_passer, received_message_id, Words.Result.FAILURE, 
                                           {Words.ParamKeys.Failure.REASON: "already connected one developer server"})
                case _:
                    print(f"Unknown role: {role}")
            # if data[Words.DataKeys.Handshake.ROLE] == Words.Roles.PLAYER:
            #     # message_id = str(uuid.uuid4())
            #     # msgfmt_passer.send_args(Formats.MESSAGE, message_id, Words.MessageType.RESPONSE, {
            #     #     Words.DataKeys.Response.RESPONDING_ID: received_message_id, 
            #     #     Words.DataKeys.Response.RESULT: Words.Result.SUCCESS
            #     # })
            #     self.send_response(msgfmt_passer, received_message_id, Words.Result.SUCCESS)
            #     self.handle_player(msgfmt_passer)
            # # if connection_type == Words.ConnectionType.CLIENT:
            # #     self.handle_client(msgfmt_passer)
            # # elif connection_type == Words.ConnectionType.DATABASE_SERVER:
            # #     self.handle_database_server(msgfmt_passer)
            # else:
            #     print(f"Unknown connection type: {connection_type}")
        except Exception as e:
            print(f"Error during handle_connections: {e}")

        # self.connections.remove(msgfmt_passer)
        # print(f"Connection closed. Active connections: {len(self.connections)}")
        msgfmt_passer.close()

    def handle_lobby(self, passer: MessageFormatPasser):
        passer.settimeout(self.receive_timeout)
        last_hb_time = time.time()
        while not self.stop_event.is_set():
            try:
                msg_id, msg_type, data = passer.receive_args(Formats.MESSAGE)
                match msg_type:
                    case Words.MessageType.REQUEST:
                        assert isinstance(data, dict)
                        cmd = data.get(Words.DataKeys.Request.COMMAND)
                        params = data.get(Words.DataKeys.PARAMS)
                        match cmd:
                            case Words.Command.LOGIN:
                                # time.sleep(10)
                                assert isinstance(params, dict)
                                username = params.get(Words.ParamKeys.Login.USERNAME)
                                password = params.get(Words.ParamKeys.Login.PASSWORD)
                                
                                success, reason = self._verify_player_credential(username, password)
                                if success:
                                    assert username is not None
                                    self._set_player_online(username)
                                    self.send_response(passer, msg_id, Words.Result.SUCCESS)
                                else:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, 
                                                       {Words.ParamKeys.Failure.REASON: reason})
                            case Words.Command.LOGOUT:
                                assert isinstance(params, dict)
                                username = params.get(Words.ParamKeys.Logout.USERNAME)
                                if not username:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, 
                                                       {Words.ParamKeys.Failure.REASON: "Missing username."})
                                    continue
                                room_id = None
                                try:
                                    room_id = self.player_db[username].get("current_room")
                                except Exception:
                                    room_id = None

                                if room_id and room_id in self.room_db:
                                    players = self.room_db[room_id].get("player_list") or []
                                    if username in players:
                                        try:
                                            players.remove(username)
                                        except ValueError:
                                            # already not in list
                                            pass
                                    # update or remove room
                                    if not players:
                                        self.room_db.pop(room_id, None)
                                    else:
                                        # assign new owner if needed
                                        room_owner = self.room_db[room_id].get("owner")
                                        if room_owner == username:
                                            self.room_db[room_id]["owner"] = players[0]
                                        self.room_db[room_id]["player_list"] = players
                                    self.save_room_db()

                                now_room_data = self.room_db.get(room_id)

                                self._set_player_offline(username)
                                self.send_response(passer, msg_id, Words.Result.SUCCESS, {
                                    Words.ParamKeys.Room.ROOM_NAME: room_id,
                                    Words.ParamKeys.Room.NOW_ROOM_DATA: now_room_data
                                })
                                
                            case Words.Command.REGISTER:
                                assert isinstance(params, dict)
                                username = params.get(Words.ParamKeys.Register.USERNAME)
                                password = params.get(Words.ParamKeys.Register.PASSWORD)
                                if not username:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, 
                                                       {Words.ParamKeys.Failure.REASON: "Missing username."})
                                    continue
                                if not password:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, 
                                                       {Words.ParamKeys.Failure.REASON: "Missing password."})
                                    continue
                                if self._verify_player_regable(username):
                                    self.write_player_data(username, password)
                                    self.send_response(passer, msg_id, Words.Result.SUCCESS)
                                else:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, 
                                                       {Words.ParamKeys.Failure.REASON: "Username used by others"})
                            case Words.Command.DOWNLOAD_START:
                                try:
                                    assert isinstance(params, dict)
                                    game_id = str(params.get(Words.ParamKeys.Metadata.GAME_ID))
                                    game_dir = GAME_FOLDER / game_id
                                    if not game_dir.exists():
                                        self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                            Words.ParamKeys.Failure.REASON: f"game_id {game_id} not found."
                                        })
                                        continue
                                    big_meta_dir = game_dir / "big_metadata.json"
                                    if not big_meta_dir.exists():
                                        self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                            Words.ParamKeys.Failure.REASON: f"big_metadata.json in game_id {game_id} not found."
                                        })
                                        continue
                                    with open(big_meta_dir, "rb") as rf:
                                        big_meta = json.load(rf)
                                    assert isinstance(big_meta, dict)
                                    latest_version = str(big_meta.get(Words.ParamKeys.Metadata.VERSION))
                                    file_name = str(big_meta.get(Words.ParamKeys.Metadata.FILE_NAME))
                                    game_file_dir = game_dir / latest_version / file_name
                                    if not game_file_dir.exists():
                                        self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                            Words.ParamKeys.Failure.REASON: f"game file of latest version not found."
                                        })
                                        continue
                                    temp_server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                    temp_server_sock.bind(("0.0.0.0", 0))
                                    temp_server_sock.listen(1)
                                    port = temp_server_sock.getsockname()[1]
                                    self.send_response(passer, msg_id, Words.Result.SUCCESS, {
                                        Words.ParamKeys.Success.PORT: port
                                    })
                                    threading.Thread(target=self.handle_download, args=(temp_server_sock, game_file_dir), daemon=True).start()
                                except Exception as e:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE,
                                                       {Words.ParamKeys.Failure.REASON: f"Exception calling download_start: {str(e)}"})

                            case Words.Command.CHECK_STORE:
                                result_dict = self.check_game_folder()
                                self.send_response(passer, msg_id, Words.Result.SUCCESS, result_dict)
                            case Words.Command.CREATE_ROOM:
                                assert isinstance(params, dict)
                                room_name = params.get(Words.ParamKeys.Room.ROOM_NAME)
                                game_id = str(params.get(Words.ParamKeys.Room.GAME_ID))
                                username = params.get(Words.ParamKeys.Room.USERNAME)
                                if not (room_name and username and game_id):
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: "missing fields"
                                    })
                                    continue
                                if room_name in self.room_db:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: "room name occupied by others"
                                    })
                                    continue
                                big_meta_dir = GAME_FOLDER / game_id / "big_metadata.json"
                                with open(big_meta_dir, "rb") as rf:
                                    big_meta = json.load(rf)

                                assert isinstance(big_meta, dict)
                                players = big_meta.get(Words.ParamKeys.Metadata.PLAYERS)

                                self.room_db[room_name] = {
                                    Words.ParamKeys.Room.OWNER: username, 
                                    Words.ParamKeys.Room.GAME_ID: game_id, 
                                    Words.ParamKeys.Room.PLAYER_LIST: [username], 
                                    Words.ParamKeys.Room.EXPECTED_PLAYERS: players, 
                                    Words.ParamKeys.Room.IS_PLAYING: False
                                }
                                self.save_room_db()
                                self.player_db[username]["current_room"] = room_name
                                self.save_player_db()
                                self.send_response(passer, msg_id, Words.Result.SUCCESS, {
                                    Words.ParamKeys.Room.EXPECTED_PLAYERS: players
                                })
                            case Words.Command.JOIN_ROOM:
                                assert isinstance(params, dict)
                                room_name = params.get(Words.ParamKeys.Room.ROOM_NAME)
                                username = params.get(Words.ParamKeys.Room.USERNAME)
                                if not (room_name and username):
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: "missing fields"
                                    })
                                    continue
                                now_room = self.room_db.get(room_name)
                                if now_room is None:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {Words.ParamKeys.Failure.REASON: 'room not found'})
                                    continue
                                players = now_room.get(Words.ParamKeys.Room.PLAYER_LIST) or []
                                expected = now_room.get(Words.ParamKeys.Room.EXPECTED_PLAYERS) or 0
                                if username in players:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: "already in room"
                                    })
                                    continue
                                if len(players) >= expected:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: "room full"
                                    })
                                    continue
                                players.append(username)
                                now_room[Words.ParamKeys.Room.PLAYER_LIST] = players
                                self.room_db[room_name] = now_room
                                self.save_room_db()
                                self.player_db[username]["current_room"] = room_name
                                self.save_player_db()
                                self.send_response(passer, msg_id, Words.Result.SUCCESS)
                            case Words.Command.LEAVE_ROOM:
                                assert isinstance(params, dict)
                                room_name = params.get(Words.ParamKeys.Room.ROOM_NAME)
                                username = params.get(Words.ParamKeys.Room.USERNAME)
                                if not (room_name and username):
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: "missing fields"
                                    })
                                    continue
                                now_room = self.room_db.get(room_name)
                                if now_room is None:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {Words.ParamKeys.Failure.REASON: 'room not found'})
                                    continue
                                players = now_room.get(Words.ParamKeys.Room.PLAYER_LIST) or []
                                if username not in players:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {Words.ParamKeys.Failure.REASON: 'not in room'})
                                    continue
                                # remove player
                                players = [p for p in players if p != username]
                                now_room[Words.ParamKeys.Room.PLAYER_LIST] = players
                                # if owner left, assign new owner or remove room
                                owner = now_room.get(Words.ParamKeys.Room.OWNER)
                                if owner == username:
                                    if players:
                                        now_room[Words.ParamKeys.Room.OWNER] = players[0]
                                    else:
                                        # remove empty room
                                        self.room_db.pop(room_name, None)
                                        self.save_room_db()
                                        self.send_response(passer, msg_id, Words.Result.SUCCESS, {
                                            Words.ParamKeys.Room.ROOM_NAME: room_name,
                                            Words.ParamKeys.Room.NOW_ROOM_DATA: None
                                        })
                                        continue
                                self.room_db[room_name] = now_room
                                self.save_room_db()
                                self.send_response(passer, msg_id, Words.Result.SUCCESS, {
                                    Words.ParamKeys.Room.ROOM_NAME: room_name,
                                    Words.ParamKeys.Room.NOW_ROOM_DATA: now_room
                                })
                            case Words.Command.START_GAME:
                                assert isinstance(params, dict)
                                room_name = params.get(Words.ParamKeys.Room.ROOM_NAME)
                                if not room_name:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: "missing room_name"
                                    })
                                    continue
                                now_room = self.room_db.get(room_name)
                                if now_room is None:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: "room not found"
                                    })
                                    continue
                                now_room[Words.ParamKeys.Room.IS_PLAYING] = True
                                self.room_db[room_name] = now_room
                                self.save_room_db()
                                self.send_response(passer, msg_id, Words.Result.SUCCESS, {
                                    Words.ParamKeys.Room.ROOM_NAME: room_name,
                                    Words.ParamKeys.Room.NOW_ROOM_DATA: now_room
                                })
                            case _:
                                self.send_response(passer, msg_id, Words.Result.FAILURE, 
                                                   {Words.ParamKeys.Failure.REASON: "Invalid command"})
                    case Words.MessageType.HEARTBEAT:
                        last_hb_time = time.time()
                        self.send_response(passer, msg_id, Words.Result.SUCCESS)   
                    case _:
                        self.send_response(passer, msg_id, Words.Result.FAILURE, 
                                            {Words.ParamKeys.Failure.REASON: "Invalid command"})

            except TimeoutError:
                if time.time() - last_hb_time > self.heartbeat_timeout:
                    print(f"[DatabaseServer] client heartbeat timeout (>{self.heartbeat_timeout}s), terminating connection")
                    break
                continue
            except ConnectionError as e:
                print(f"[DatabaseServer] ConnectionError raised in handle_lobby: {e}")
                break
            except Exception as e:
                safe_msg_id = locals().get("msg_id")
                if safe_msg_id:
                    try:
                        self.send_response(passer, safe_msg_id, Words.Result.FAILURE, 
                                            {Words.ParamKeys.Failure.REASON: "Error occurred in database server."})
                    except Exception:
                        pass
                print(f"[DatabaseServer] Exception occurred in handle_lobby: {e}")

    def handle_developer(self, passer: MessageFormatPasser):
        passer.settimeout(self.receive_timeout)
        last_hb_time = time.time()
        while not self.stop_event.is_set():
            try:
                msg_id, msg_type, data = passer.receive_args(Formats.MESSAGE)
                match msg_type:
                    case Words.MessageType.REQUEST:
                        assert isinstance(data, dict)
                        cmd = data.get(Words.DataKeys.Request.COMMAND)
                        params = data.get(Words.DataKeys.PARAMS)
                        match cmd:
                            case Words.Command.LOGIN:
                                # time.sleep(10)
                                assert isinstance(params, dict)
                                username = params.get(Words.ParamKeys.Login.USERNAME)
                                password = params.get(Words.ParamKeys.Login.PASSWORD)
                                
                                success, reason = self._verify_developer_credential(username, password)
                                if success:
                                    assert username is not None
                                    self._set_developer_online(username)
                                    self.send_response(passer, msg_id, Words.Result.SUCCESS)
                                else:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, 
                                                       {Words.ParamKeys.Failure.REASON: reason})
                            case Words.Command.LOGOUT:
                                assert isinstance(params, dict)
                                username = params.get(Words.ParamKeys.Logout.USERNAME)
                                if not username:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, 
                                                       {Words.ParamKeys.Failure.REASON: "Missing username."})
                                    continue
                                if username in self.room_db:
                                    room_info = self.room_db[username]
                                    if room_info.get(Words.ParamKeys.Room.IS_PLAYING, False):
                                        self.send_response(passer, msg_id, Words.Result.FAILURE, 
                                                           {Words.ParamKeys.Failure.REASON: "Cannot logout when game is in playing."})
                                        continue
                                    else:
                                        del self.room_db[username]
                                        self.save_room_db()
                                self._set_developer_offline(username)
                                self.send_response(passer, msg_id, Words.Result.SUCCESS)
                            case Words.Command.REGISTER:
                                assert isinstance(params, dict)
                                username = params.get(Words.ParamKeys.Register.USERNAME)
                                password = params.get(Words.ParamKeys.Register.PASSWORD)
                                if not username:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, 
                                                       {Words.ParamKeys.Failure.REASON: "Missing username."})
                                    continue
                                if not password:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, 
                                                       {Words.ParamKeys.Failure.REASON: "Missing password."})
                                    continue
                                if self._verify_developer_regable(username):
                                    self.write_developer_data(username, password)
                                    self.send_response(passer, msg_id, Words.Result.SUCCESS)
                                else:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, 
                                                       {Words.ParamKeys.Failure.REASON: "Username used by others"})
                            case Words.Command.CHECK_GAME_VALID:
                                assert isinstance(params, dict)
                                game_id = str(params.get(Words.ParamKeys.Metadata.GAME_ID))
                                version = str(params.get(Words.ParamKeys.Metadata.VERSION))
                                uploader = str(params.get(Words.ParamKeys.Metadata.UPLOADER))

                                big_meta_path = GAME_FOLDER / game_id / "big_metadata.json"
                                if big_meta_path.exists():
                                    # big_meta_path = path / "big_metadata.json"
                                    try:
                                        with open(big_meta_path, "rb") as rf:
                                            big_meta = json.load(rf)
                                        assert isinstance(big_meta, dict)
                                        actual_uploader = str(big_meta.get(Words.ParamKeys.Metadata.UPLOADER))
                                        if actual_uploader != uploader:
                                            self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                                Words.ParamKeys.Failure.REASON: f"Exists same game_id but not yours. Uploader: {actual_uploader}"
                                            })
                                            continue
                                    except Exception as e:
                                        self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                            Words.ParamKeys.Failure.REASON: f"Exception when comparing uploaders: {e}"
                                        })
                                        continue
                                    previous_version = str(big_meta.get(Words.ParamKeys.Metadata.VERSION))
                                    try:
                                        px, py, pz = [int(s) for s in previous_version.split(".")]
                                        nx, ny, nz = [int(s) for s in version.split(".")]
                                        if px > nx or (px == nx and py > ny) or (px == nx and py == ny and pz >= nz):
                                            self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                                Words.ParamKeys.Failure.REASON: f"version not lexigraphically bigger than previous version. Previous version: {previous_version}, Uploading version: {version}"
                                            })
                                            continue
                                    except Exception as e:
                                        self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                            Words.ParamKeys.Failure.REASON: f"Exception when comparing versions: {e}"
                                        })
                                        continue
                                self.send_response(passer, msg_id, Words.Result.SUCCESS)
                                    

                            case Words.Command.UPLOAD_START:
                                with self.upload_lock:
                                    if self.upload_params:
                                        self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                            Words.ParamKeys.Failure.REASON: "Other data is uploading."
                                        })
                                        continue
                                assert isinstance(params, dict)
                                game_id = params.get(Words.ParamKeys.Metadata.GAME_ID)
                                game_name = params.get(Words.ParamKeys.Metadata.GAME_NAME)
                                version = params.get(Words.ParamKeys.Metadata.VERSION)
                                uploader = params.get(Words.ParamKeys.Metadata.UPLOADER)
                                file_name = params.get(Words.ParamKeys.Metadata.FILE_NAME)
                                players = params.get(Words.ParamKeys.Metadata.PLAYERS)
                                size = params.get(Words.ParamKeys.Metadata.SIZE)
                                sha256 = params.get(Words.ParamKeys.Metadata.SHA256)
                                assert isinstance(game_id, str) and isinstance(version, str) and isinstance(file_name, str) and isinstance(players, int)
                                assert isinstance(uploader, str) and isinstance(size, int) and isinstance(sha256, str) and isinstance(game_name, str)
                                # game_root_dir = GAME_FOLDER / game_id
                                # game_root_dir.mkdir(parents=True, exist_ok=True)
                                # metadata_path = GAME_FOLDER / game_id / "metadata.json"
                                # try:
                                #     meta_obj = params
                                #     with metadata_path.open("w", encoding="utf-8") as outf:
                                #         json.dump(meta_obj, outf, ensure_ascii=False, indent=2)
                                # except Exception as e:
                                #     self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                #         Words.ParamKeys.Failure.REASON: f"Failed to write metadata: {e}"
                                #     })
                                #     continue
                                game_dir = GAME_FOLDER / game_id / version
                                game_dir.mkdir(parents=True, exist_ok=True)
                                # game_file_path = game_dir / file_name
                                with self.upload_lock:
                                    self.upload_params = dict(params)
                                    self.upload_params["upload_done"] = False
                                    # self.upload_params["game_file_path"] = game_file_path
                                server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                server_sock.bind(("0.0.0.0", 0))
                                server_sock.listen(1)
                                port = server_sock.getsockname()[1]
                                self.send_response(passer, msg_id, Words.Result.SUCCESS, {
                                    Words.ParamKeys.Success.PORT: port
                                })
                                threading.Thread(target=self.handle_upload, args=(server_sock,), daemon=True).start()
                            case Words.Command.UPLOAD_END:
                                with self.upload_lock:
                                    if not self.upload_params:
                                        self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                            Words.ParamKeys.Failure.REASON: "No data is uploading."
                                        })
                                        continue
                                done = False
                                check_count = 0
                                while check_count <= 15:
                                    with self.upload_lock:
                                        upload_done = self.upload_params.get("upload_done")
                                        print(f"upload_done: {upload_done}")
                                        if upload_done:
                                            done = True
                                            break
                                    check_count += 1
                                    time.sleep(0.2)
                                if not done:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                            Words.ParamKeys.Failure.REASON: "Upload is not done"
                                        })
                                    continue
                                    
                                with self.upload_lock:
                                    st = self.upload_params.copy()

                                # part_path = st["cache_root"] / (str(st["filename"]) + ".part")
                                game_id = str(st.get(Words.ParamKeys.Metadata.GAME_ID))
                                game_name = str(st.get(Words.ParamKeys.Metadata.GAME_NAME))
                                version = str(st.get(Words.ParamKeys.Metadata.VERSION))
                                uploader = str(st.get(Words.ParamKeys.Metadata.UPLOADER))
                                file_name = str(st.get(Words.ParamKeys.Metadata.FILE_NAME))
                                size = st.get(Words.ParamKeys.Metadata.SIZE)
                                players = st.get(Words.ParamKeys.Metadata.PLAYERS)
                                sha256 = str(st.get(Words.ParamKeys.Metadata.SHA256))

                                final_path = GAME_FOLDER / game_id / version / file_name
                                assert isinstance(size, int)

                                file_checker = FileChecker(final_path, st)
                                success, params = file_checker.check()
                                if not success:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, params)
                                    continue

                                # move into place
                                try:
                                    # final_path.replace(final_path)
                                    # write metadata
                                    meta = {
                                        Words.ParamKeys.Metadata.GAME_ID: game_id,
                                        Words.ParamKeys.Metadata.GAME_NAME: game_name, 
                                        Words.ParamKeys.Metadata.VERSION: version,
                                        Words.ParamKeys.Metadata.UPLOADER: uploader, 
                                        Words.ParamKeys.Metadata.FILE_NAME: file_name,
                                        Words.ParamKeys.Metadata.PLAYERS: players, 
                                        Words.ParamKeys.Metadata.SIZE: size,
                                        Words.ParamKeys.Metadata.SHA256: sha256,
                                    }

                                    big_meta_path = GAME_FOLDER / game_id / "big_metadata.json"
                                    # big_meta = {}
                                    version_list = []
                                    if big_meta_path.exists():
                                        with open(big_meta_path, "rb") as rf:
                                            temp_big_meta = json.load(rf)
                                            version_list = temp_big_meta[Words.ParamKeys.Metadata.ALL_VERSIONS]
                                    big_meta = meta.copy()
                                    version_list.append(version)
                                    big_meta[Words.ParamKeys.Metadata.ALL_VERSIONS] = version_list
                                    # else:
                                    #     big_meta = meta.copy()
                                    #     big_meta[Words.ParamKeys.Metadata.ALL_VERSIONS] = []
                                    # try:
                                    #     big_meta[Words.ParamKeys.Metadata.ALL_VERSIONS].append(version)
                                    # except Exception:
                                    #     print("failed to add version to all_versions")
                                        
                                    
                                    (GAME_FOLDER / game_id / version / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
                                    big_meta_path.write_text(json.dumps(big_meta, indent=2), encoding="utf-8")
                                except Exception as e:
                                    with self.upload_lock:
                                        self.upload_params.clear()
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: f"Finalize error: {e}"
                                    })
                                    continue
                                self.add_developer_uploaded_games(uploader, game_id, game_name, version)
                                with self.upload_lock:
                                    self.upload_params.clear()
                                self.send_response(passer, msg_id, Words.Result.SUCCESS)
                            case Words.Command.CHECK_DEV_WORKS:
                                assert isinstance(params, dict)
                                username = str(params.get(Words.ParamKeys.CheckInfo.USERNAME))
                                params = self.developer_db[username]["uploaded_games"]
                                self.send_response(passer, msg_id, Words.Result.SUCCESS, params)
                            case _:
                                self.send_response(passer, msg_id, Words.Result.FAILURE, 
                                                   {Words.ParamKeys.Failure.REASON: "Invalid command"})
                    case Words.MessageType.HEARTBEAT:
                        last_hb_time = time.time()
                        self.send_response(passer, msg_id, Words.Result.SUCCESS)   
                    case _:
                        self.send_response(passer, msg_id, Words.Result.FAILURE, 
                                            {Words.ParamKeys.Failure.REASON: "Invalid command"})

            except TimeoutError:
                if time.time() - last_hb_time > self.heartbeat_timeout:
                    print(f"[DatabaseServer] client heartbeat timeout (>{self.heartbeat_timeout}s), terminating connection")
                    break
                continue
            except ConnectionError as e:
                print(f"[DatabaseServer] ConnectionError raised in handle_developer: {e}")
                break
            except Exception as e:
                self.send_response(passer, msg_id, Words.Result.FAILURE, 
                                            {Words.ParamKeys.Failure.REASON: "Error occurred in database server."})
                print(f"[DatabaseServer] Exception occurred in handle_developer: {e}")

    def check_game_folder(self) -> dict:
        result: dict[str, dict] = {}
        print("Entered check_game_folder")
        try:
            for p in GAME_FOLDER.iterdir():
                if not p.is_dir():
                    continue
                game_id = p.name
                big_meta_path = p / "big_metadata.json"
                meta_obj: dict | None = None
                if big_meta_path.exists():
                    try:
                        meta_obj = json.loads(big_meta_path.read_text(encoding="utf-8"))
                    except Exception as e:
                        print(f"[check_game_folder] failed to read big_metadata for {game_id}: {e}")
                        meta_obj = None
                else:
                    # try to collect metadata from version folders (pick one and collect versions)
                    versions = []
                    for v in p.iterdir():
                        if not v.is_dir():
                            continue
                        mpath = v / "metadata.json"
                        if mpath.exists():
                            try:
                                m = json.loads(mpath.read_text(encoding="utf-8"))
                                versions.append(m)
                            except Exception:
                                continue
                    if versions:
                        # build a simple aggregate big_meta from first entry and versions list
                        base = dict(versions[0])
                        base[Words.ParamKeys.Metadata.ALL_VERSIONS] = [str(m.get(Words.ParamKeys.Metadata.VERSION)) for m in versions if isinstance(m, dict)]
                        meta_obj = base

                if meta_obj is None:
                    # no metadata available
                    continue

                # remove game_id from the metadata value (we keep folder name as the key)
                cleaned = dict(meta_obj)
                try:
                    cleaned.pop(Words.ParamKeys.Metadata.GAME_ID, None)
                except Exception:
                    pass

                result[game_id] = cleaned
        except Exception as e:
            print(f"[check_game_folder] unexpected error: {e}")
        return result
    
    def handle_upload(self, server_sock: socket.socket):
        sock, addr = server_sock.accept()
        print(f"accepted connection in handle_upload: {addr}")
        server_sock.close()
        with self.upload_lock:
            game_id = str(self.upload_params.get(Words.ParamKeys.Metadata.GAME_ID))
            version = str(self.upload_params.get(Words.ParamKeys.Metadata.VERSION))
            file_name = str(self.upload_params.get(Words.ParamKeys.Metadata.FILE_NAME))
            game_file_path = GAME_FOLDER / game_id / version / file_name
        if not isinstance(game_file_path, Path):
            print("game_file_path is not Path. Closing sock...")
            with self.upload_lock:
                self.upload_params.clear()
            sock.close()
            return
        file_receiver = FileReceiver(sock, game_file_path)
        success = file_receiver.receive()
        if not success:
            print("Warning: file receive not success.")
        file_receiver.close()
        with self.upload_lock:
            self.upload_params["upload_done"] = True
        print("exited handle_upload")

    def handle_download(self, server_sock: socket.socket, path: Path):
        sock, addr = server_sock.accept()
        print(f"accepted connection in handle_upload: {addr}")
        server_sock.close()
        file_sender = FileSender(sock, path)
        file_sender.send()
        file_sender.close()
        print("exited handle_download")

    def _verify_player_credential(self, username, password) -> tuple[bool, str]:
        if not username:
            return (False, "Missing username.")
        if not password:
            return (False, "Missing password.")
        
        record = self.player_db.get(username)

        if not record:
            return (False, "Incorrect username or password.")
        if isinstance(record, dict):
            correct_password = record.get("password")
        else:
            correct_password = record
        if password == correct_password:
            if not record.get("online"):
                return (True, "")
            else:
                return (False, "Account using by other clients")
        else:
            return (False, "Incorrect username or password.")
    
    def _verify_player_regable(self, username) -> bool:
        return not username in self.player_db.keys()
    
    def _set_player_online(self, username: str):
        self.player_db[username]["last_login_time"] = time.time()
        self.player_db[username]["online"] = True
        self.save_player_db()

    def _set_player_offline(self, username):
        self.player_db[username]["online"] = False
        self.player_db[username]["current_room"] = None
        self.save_player_db()

    def write_player_data(self, username: str, password: str):
        self.player_db[username] = {
            "password": password, 
            "create_time": time.time(), 
            "last_login_time": None, 
            "current_room": None,
            "online": False
        }
        self.save_player_db()

    def _verify_developer_credential(self, username, password) -> tuple[bool, str]:
        if not username:
            return (False, "Missing username.")
        if not password:
            return (False, "Missing password.")
        
        record = self.developer_db.get(username)

        if not record:
            return (False, "Incorrect username or password.")
        if isinstance(record, dict):
            correct_password = record.get("password")
        else:
            correct_password = record
        if password == correct_password:
            if not record.get("online"):
                return (True, "")
            else:
                return (False, "Account using by other clients")
        else:
            return (False, "Incorrect username or password.")
    
    def _verify_developer_regable(self, username) -> bool:
        return not username in self.developer_db.keys()
    
    def _set_developer_online(self, username: str):
        self.developer_db[username]["last_login_time"] = time.time()
        self.developer_db[username]["online"] = True
        self.save_developer_db()

    def _set_developer_offline(self, username):
        self.developer_db[username]["online"] = False
        self.save_developer_db()

    def write_developer_data(self, username: str, password: str):
        self.developer_db[username] = {
            "password": password, 
            "create_time": time.time(), 
            "last_login_time": None, 
            "online": False, 
            "uploaded_games": {}
        }
        self.save_developer_db()

    def add_developer_uploaded_games(self, username: str, game_id: str, game_name: str, version: str):
        if username not in self.developer_db:
            return
        self.developer_db[username]["uploaded_games"][game_id] = {Words.ParamKeys.Metadata.GAME_NAME: game_name, 
                                                                  Words.ParamKeys.Metadata.VERSION: version, 
                                                                  "last_update": time.time()}
        self.save_developer_db()

    def start(self) -> None:
        server_thread = threading.Thread(target=self.run)
        server_thread.start()
        # game_servers_manager_thread = threading.Thread(target=self.manage_game_servers)
        # game_servers_manager_thread.start()
        time.sleep(0.2)
        try:
            while True:
                cmd = input("Enter 'stop' to stop the server: ")
                if cmd == 'stop':
                    self.stop()
                    break
                elif cmd == 'resetplayer':
                    self.reset_player()
                elif cmd == 'resetdeveloper':
                    self.reset_developer()
                elif cmd == 'clearrooms':
                    self.room_db.clear()
                    self.save_room_db()
                else:
                    print("invalid command.")
        except KeyboardInterrupt:
            self.stop()
            # with self.game_server_lock:
            #     for game_server in self.game_servers.values():
            #         game_server.stop()

        server_thread.join()

        self.save_player_db()
        self.save_room_db()
        self.save_developer_db()

    def reset_player(self):
        for username in self.player_db.keys():
            self.player_db[username]["online"] = False
            self.player_db[username]["current_room"] = None
        self.save_player_db()

    def reset_developer(self):
        for username in self.developer_db.keys():
            self.developer_db[username]["online"] = False
        self.save_developer_db()

    def stop(self):
        self.stop_event.set()

        try:
            self.server_sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            self.server_sock.close()
        except Exception:
            pass

        if self.lobby_passer:
            try:
                self.lobby_passer.close()
            except Exception:
                pass

        if self.developer_passer:
            try:
                self.developer_passer.close()
            except Exception:
                pass
        

    def send_response(self, passer: MessageFormatPasser, responding_id: str, result: str, params: Optional[dict] = None) -> str:
        message_id = str(uuid.uuid4())
        data: dict[str, str | dict] = {
            Words.DataKeys.Response.RESPONDING_ID: responding_id, 
            Words.DataKeys.Response.RESULT: result
        }
        if params is not None:
            data[Words.DataKeys.PARAMS] = params
        passer.send_args(Formats.MESSAGE, message_id, Words.MessageType.RESPONSE, data)
        return message_id

    



