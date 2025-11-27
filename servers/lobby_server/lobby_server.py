import threading
import socket
from base.message_format_passer import MessageFormatPasser
from protocols.protocols import Formats, Words
from typing import Optional
import time
import uuid

class LobbyServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 21354, accept_timeout = 1.0, receive_timeout = 2.0) -> None:
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = host
        self.port = port
        self.accept_timeout = accept_timeout
        self.receive_timeout = receive_timeout
        self.connections: list[MessageFormatPasser] = []
        self.passer_player_dict: dict[MessageFormatPasser, str | None] = {}
        self.db_server_passer: MessageFormatPasser | None = None
        self.stop_event = threading.Event()
        self.pending_db_response_dict: dict[str, tuple[bool, str, dict]] = {}
        """The dict contains all sent db_requests, after processing, received responses will be popped. {request_id: (response_received, result, data)}"""
        self.pending_db_response_lock = threading.Lock()
        self.invitee_inviter_set_pair: set[tuple] = set()  # {(invitee_username, inviter_username)}
        self.invitation_lock = threading.Lock()
        #self.game_servers: dict[str, GameServer] = {}  # {room_id: GameServer}
        self.game_server_threads: dict[str, threading.Thread] = {}  # {room_id: Thread}
        self.game_server_win_recorded: dict[str, bool] = {}  # {room_id: bool}
        self.game_server_lock = threading.Lock()
        
        #self.send_to_DB_queue = queue.Queue()
        #self.accept_thread = threading.Thread(target=self.accept_connections, daemon=True)
        #self.accept_thread.start()

    def run(self):
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(5)
        self.server_sock.settimeout(self.accept_timeout)
        print(f"Lobby server listening on {self.host}:{self.port}")
        self.accept_connections()

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
        # game_servers_manager_thread.join()

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

    def accept_connections(self) -> None:
        while not self.stop_event.is_set():
            try:
                connection_sock, addr = self.server_sock.accept()
                print(f"Accepted connection from {addr}")
                msgfmt_passer = MessageFormatPasser(connection_sock)
                #self.clients.append(msgfmt_passer)
                #self.user_infos[msgfmt_passer] = UserInfo()
                self.connections.append(msgfmt_passer)
                print(f"Active connections: {len(self.connections)}")
                # Since connection may be client, db, or game server, start a thread to handle initial handshake
                threading.Thread(target=self.handle_connections, args=(msgfmt_passer,)).start()
                
            except socket.timeout:
                continue
    
    def handle_connections(self, msgfmt_passer: MessageFormatPasser) -> None:
        """Check handshake and pass to corresponding methods."""
        try:
            #while True:
            received_message_id, message_type, data = msgfmt_passer.receive_args(Formats.MESSAGE)
            if message_type != Words.MessageType.HANDSHAKE:
                print(f"[LOBBYSERVER] received message_type {message_type}, expected {Words.MessageType.HANDSHAKE}")

            if data[Words.DataKeys.Handshake.ROLE] == Words.Roles.PLAYER:
                # message_id = str(uuid.uuid4())
                # msgfmt_passer.send_args(Formats.MESSAGE, message_id, Words.MessageType.RESPONSE, {
                #     Words.DataKeys.Response.RESPONDING_ID: received_message_id, 
                #     Words.DataKeys.Response.RESULT: Words.Result.SUCCESS
                # })
                self.send_response(msgfmt_passer, received_message_id, Words.Result.SUCCESS)
                self.handle_player(msgfmt_passer)
            # if connection_type == Words.ConnectionType.CLIENT:
            #     self.handle_client(msgfmt_passer)
            # elif connection_type == Words.ConnectionType.DATABASE_SERVER:
            #     self.handle_database_server(msgfmt_passer)
            # else:
            #     print(f"Unknown connection type: {connection_type}")
        except Exception as e:
            print(f"Error during handshake: {e}")

        self.connections.remove(msgfmt_passer)
        print(f"Connection closed. Active connections: {len(self.connections)}")
        msgfmt_passer.close()

    def handle_player(self, passer: MessageFormatPasser):
        self.passer_player_dict[passer] = None
        
        try:
            while not self.stop_event.is_set():
                msg_id, msg_type, data = passer.receive_args(Formats.MESSAGE)
                match msg_type:
                    case Words.MessageType.REQUEST:
                        cmd = data[Words.DataKeys.Request.COMMAND]
                        match cmd:
                            case Words.Command.LOGIN:
                                # continue
                                self.send_response(passer, msg_id, Words.Result.FAILURE, {Words.ParamKeys.Failure.REASON: 'suduiwee', '12': 345})
        except Exception as e:
            print(f"[LOBBYSERVER] exception raised in handle_player: {e}")

        del self.passer_player_dict[passer]

