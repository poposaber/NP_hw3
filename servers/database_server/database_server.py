# next: supply only two connection, one from lobby server, one from developer server 

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

DATA_DIR = Path(__file__).resolve().parents[2] / "data"  # parents[0]=current dir, parents[1]=上一層, parents[2]=上二層
DATA_DIR.mkdir(parents=True, exist_ok=True)

USER_DB_FILE = DATA_DIR / "user_db.json"
ROOM_DB_FILE = DATA_DIR / "room_db.json"

class DatabaseServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 32132, 
                 accept_timeout = DEFAULT_ACCEPT_TIMEOUT, 
                 receive_timeout = DEFAULT_RECEIVE_TIMEOUT, 
                 handshake_timeout = DEFAULT_HANDSHAKE_TIMEOUT):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = host
        self.port = port
        self.accept_timeout = accept_timeout
        self.receive_timeout = receive_timeout
        self.handshake_timeout = handshake_timeout

        self.stop_event = threading.Event()

        self.lobby_passer: Optional[MessageFormatPasser] = None
        self.developer_passer: Optional[MessageFormatPasser] = None

        self.user_db = self.load_user_db()
        self.room_db = self.load_room_db()

    def load_user_db(self):
        if not os.path.exists(USER_DB_FILE):
            return {}
        with open(USER_DB_FILE, 'r') as f:
            return json.load(f)
        
    def save_user_db(self):
        with open(USER_DB_FILE, 'w') as f:
            json.dump(self.user_db, f, indent=2)

    def load_room_db(self):
        if not os.path.exists(ROOM_DB_FILE):
            return {}
        with open(ROOM_DB_FILE, 'r') as f:
            return json.load(f)

    def save_room_db(self):
        with open(ROOM_DB_FILE, 'w') as f:
            json.dump(self.room_db, f, indent=2)

    def run(self):
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(5)
        self.server_sock.settimeout(self.accept_timeout)
        print(f"Lobby server listening on {self.host}:{self.port}")
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
    
    def handle_connections(self, msgfmt_passer: MessageFormatPasser) -> None:
        """Check handshake and pass to corresponding methods."""
        try:
            #while True:
            msgfmt_passer.settimeout(self.handshake_timeout)
            received_message_id, message_type, data = msgfmt_passer.receive_args(Formats.MESSAGE)
            if message_type != Words.MessageType.HANDSHAKE:
                print(f"[LOBBYSERVER] received message_type {message_type}, expected {Words.MessageType.HANDSHAKE}")

            role = data[Words.DataKeys.Handshake.ROLE]
            match role:
                case Words.Roles.LOBBYSERVER:
                    if self.lobby_passer is None:
                        self.lobby_passer = msgfmt_passer
                        self.send_response(msgfmt_passer, received_message_id, Words.Result.SUCCESS)
                        self.handle_lobby(msgfmt_passer)
                    else:
                        self.send_response(msgfmt_passer, received_message_id, Words.Result.FAILURE)
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
            print(f"Error during handshake: {e}")

        # self.connections.remove(msgfmt_passer)
        # print(f"Connection closed. Active connections: {len(self.connections)}")
        msgfmt_passer.close()

    def handle_lobby(self, passer: MessageFormatPasser):
        passer.settimeout(self.receive_timeout)
        while not self.stop_event.is_set():
            try:
                msg_id, msg_type, data = passer.receive_args(Formats.MESSAGE)
                match msg_type:
                    case Words.MessageType.REQUEST:
                        pass
            except TimeoutError:
                continue
            except Exception as e:
                print(f"[DatabaseServer] Exception occurred in handle_lobby: {e}")

        

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
                    self.stop_event.set()
                    # with self.game_server_lock:
                    #     for game_server in self.game_servers.values():
                    #         game_server.stop()
                    break
                else:
                    print("invalid command.")
        except KeyboardInterrupt:
            self.stop_event.set()
            # with self.game_server_lock:
            #     for game_server in self.game_servers.values():
            #         game_server.stop()

        server_thread.join()

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

    



