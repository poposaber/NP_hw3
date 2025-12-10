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
                                    self._set_online(username)
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
                                self._set_offline(username)
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
                                if self._verify_regable(username):
                                    self.write_player_data(username, password)
                                    self.send_response(passer, msg_id, Words.Result.SUCCESS)
                                else:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, 
                                                       {Words.ParamKeys.Failure.REASON: "Username used by others"})

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
                    print(f"[LobbyServer] client heartbeat timeout (>{self.heartbeat_timeout}s), terminating connection")
                    break
                continue
            except ConnectionError as e:
                print(f"[DatabaseServer] ConnectionError raised in handle_lobby: {e}")
                break
            except Exception as e:
                self.send_response(passer, msg_id, Words.Result.FAILURE, 
                                            {Words.ParamKeys.Failure.REASON: "Error occurred in database server."})
                print(f"[DatabaseServer] Exception occurred in handle_lobby: {e}")

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
    
    def _verify_regable(self, username) -> bool:
        return not username in self.player_db.keys()
    
    def _set_online(self, username: str):
        self.player_db[username]["last_login_time"] = time.time()
        self.player_db[username]["online"] = True
        self.save_player_db()

    def _set_offline(self, username):
        self.player_db[username]["online"] = False
        self.save_player_db()

    def write_player_data(self, username: str, password: str):
        self.player_db[username] = {
            "password": password, 
            "create_time": time.time(), 
            "last_login_time": None, 
            "online": False
        }
        self.save_player_db()

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
        self.save_player_db()

            

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

    



