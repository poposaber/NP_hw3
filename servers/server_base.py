import threading
import socket
from base.message_format_passer import MessageFormatPasser
from protocols.protocols import Formats, Words
from typing import Optional
from base.peer_worker import PeerWorker
import time
import uuid

DEFAULT_ACCEPT_TIMEOUT = 1.0
DEFAULT_CONNECT_TIMEOUT = 3.0
DEFAULT_RECEIVE_TIMEOUT = 1.0
DEFAULT_HANDSHAKE_TIMEOUT = 5.0
DEFAULT_MAX_HANDSHAKE_TRY_COUNT = 5
DEFAULT_DB_HEARTBEAT_INTERVAL = 10.0
DEFAULT_DB_HEARTBEAT_PATIENCE = 3
DEFAULT_DB_RESPONSE_TIMEOUT = 3.0
DEFAULT_CLIENT_HEARTBEAT_TIMEOUT = 30.0


class ServerBase:
    def __init__(self, host: str, port: int, 
                 db_host: str, db_port: int, role: str, 
                 accept_timeout = DEFAULT_ACCEPT_TIMEOUT, 
                 connect_timeout = DEFAULT_CONNECT_TIMEOUT, 
                 receive_timeout = DEFAULT_RECEIVE_TIMEOUT, 
                 handshake_timeout = DEFAULT_HANDSHAKE_TIMEOUT, 
                 db_response_timeout = DEFAULT_DB_RESPONSE_TIMEOUT, 
                 max_handshake_try_count = DEFAULT_MAX_HANDSHAKE_TRY_COUNT, 
                 db_heartbeat_interval = DEFAULT_DB_HEARTBEAT_INTERVAL, 
                 db_heartbeat_patience = DEFAULT_DB_HEARTBEAT_PATIENCE, 
                 client_heartbeat_timeout = DEFAULT_CLIENT_HEARTBEAT_TIMEOUT) -> None:
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = host
        self.port = port
        self.db_host = db_host
        self.db_port = db_port
        self.role = role
        self.accept_timeout = accept_timeout
        self.connect_timeout = connect_timeout
        self.receive_timeout = receive_timeout
        self.handshake_timeout = handshake_timeout
        self.db_response_timeout = db_response_timeout
        self.max_handshake_try_count = max_handshake_try_count
        self.db_heartbeat_interval = db_heartbeat_interval
        self.db_heartbeat_patience = db_heartbeat_patience
        self.client_heartbeat_timeout = client_heartbeat_timeout
        self.connections: list[MessageFormatPasser] = []
        # self.passer_player_dict: dict[MessageFormatPasser, str | None] = {}

        self.db_passer: MessageFormatPasser | None = None
        self.db_worker: Optional[PeerWorker] = None

        self.stop_event = threading.Event()
        self.stop_event.set()
        # self.connection_to_db_loss_event = threading.Event()
        # self.connection_to_db_loss_event.set()

        self.pending_db_messages: dict[str, tuple[tuple[str, dict], bool, Optional[tuple[str, dict]]]] = {}
        """{message_id: ((message_type, data) of sending message, is_sent, (message_type, data) of receiving message)}"""
        self.pending_db_messages_lock = threading.Lock()
        # self.pending_db_response_dict: dict[str, tuple[bool, str, dict]] = {}
        # """The dict contains all sent db_requests, after processing, received responses will be popped. {request_id: (response_received, result, data)}"""
        # self.pending_db_response_lock = threading.Lock()
        # self.invitee_inviter_set_pair: set[tuple] = set()  # {(invitee_username, inviter_username)}
        # self.invitation_lock = threading.Lock()
        #self.game_servers: dict[str, GameServer] = {}  # {room_id: GameServer}
        # self.game_server_threads: dict[str, threading.Thread] = {}  # {room_id: Thread}
        # self.game_server_win_recorded: dict[str, bool] = {}  # {room_id: bool}
        # self.game_server_lock = threading.Lock()

        self.thread: Optional[threading.Thread] = None
        self.interact_to_db_thread: Optional[threading.Thread] = None
        # self.send_msg_thread: Optional[threading.Thread] = None
        # self.receive_msg_thread: Optional[threading.Thread] = None
        # self.heartbeat_thread: Optional[threading.Thread] = None
        
        
        #self.send_to_DB_queue = queue.Queue()
        #self.accept_thread = threading.Thread(target=self.accept_connections, daemon=True)
        #self.accept_thread.start()

    def connect(self) -> bool:
        attempt = 1
        while not self.stop_event.is_set():
            try:
                print(f"[Server] connect attempt {attempt} -> {self.db_host}:{self.db_port}")
                self.reset_db_passer()
                assert self.db_passer is not None
                self.db_passer.settimeout(self.connect_timeout)
                self.db_passer.connect(self.db_host, self.db_port)
                print("[Server] connected")
                return True
            except Exception as e:
                attempt += 1
                print(f"[Server] connect failed: {e}, retrying...")
                
                
        return False

    def handshake(self) -> bool:
        attempt = 1
        while attempt <= self.max_handshake_try_count and not self.stop_event.is_set():
            try:
                print(f"[Server] handshake attempt {attempt}")
                # 呼叫 send_args 或其他 handshake 流程
                assert self.db_passer is not None
                self.db_passer.settimeout(self.handshake_timeout)
                message_id = str(uuid.uuid4())
                self.db_passer.send_args(Formats.MESSAGE, message_id, Words.MessageType.HANDSHAKE, 
                                            {Words.DataKeys.Handshake.ROLE: self.role})
                
                _, message_type, data = self.db_passer.receive_args(Formats.MESSAGE)
                if message_type != Words.MessageType.RESPONSE:
                    error_message = f"received message_type {message_type}, expected {Words.MessageType.RESPONSE}"
                    # print(f"[Server] {error_message}")
                    raise Exception(error_message)
                responding_id = data[Words.DataKeys.Response.RESPONDING_ID]
                if responding_id != message_id:
                    error_message = f"received responding_id {responding_id}, expected {message_id}"
                    # print(f"[Server] {error_message}")
                    raise Exception(error_message)
                result = data[Words.DataKeys.Response.RESULT]
                if result != Words.Result.SUCCESS:
                    error_message = f"received result {result}, expected {Words.Result.SUCCESS}."
                    if Words.DataKeys.PARAMS in data.keys():
                        error_message += f" params: {data[Words.DataKeys.PARAMS]}"
                    # print(f"[Server] {error_message}")
                    raise Exception(error_message)
                return True
            except Exception as e:
                attempt += 1
                if attempt > self.max_handshake_try_count:
                    print(f"[Server] handshake failed: {e}")
                    continue
                print(f"[Server] handshake failed: {e}, retrying...")
                if not self.stop_event.is_set():
                    time.sleep(1)
        return False
    
    def interact_to_db_loop(self):
        while not self.stop_event.is_set():
            if not self.connect():
                continue
            if not self.handshake():
                continue

            # def on_db_recv(msg_tuple):
            #     msg_id, msg_type, data = msg_tuple
            #     # currently DB only sends RESPONSE; log others
            #     if msg_type != Words.MessageType.RESPONSE:
            #         print(f"[Server] received unknown msg_type from DB: {msg_type}")

            def on_db_lost():
                print("[Server] DB connection lost")
                # self.connection_to_db_loss_event.set()

            def make_db_hb():
                return (Words.MessageType.HEARTBEAT, {})
            
            assert self.db_passer is not None
            self.db_worker = PeerWorker(
                passer=self.db_passer,
                receive_timeout=self.receive_timeout,
                heartbeat_interval=self.db_heartbeat_interval,
                heartbeat_patience=self.db_heartbeat_patience,
                on_connection_lost=on_db_lost,
                make_heartbeat=make_db_hb,
            )
            self.db_worker.start()

            # block until loss or stop
            while not self.stop_event.is_set() and not self.db_worker.conn_loss_event.is_set():
                time.sleep(0.2)

            # cleanup
            try:
                self.db_worker.stop()
            except Exception:
                pass
            # with self.pending_db_messages_lock:
            #     self.pending_db_messages.clear()
            self.reset_db_passer()

            if not self.stop_event.is_set() and self.db_worker.conn_loss_event.is_set():
                print("[Server] Reconnecting to database server...")
                # with self.pending_db_messages_lock:
                #     self.pending_db_messages.clear()
            
            # self.reset_db_passer()

        print("[Server] stopped")

    def run(self):
        self.interact_to_db_thread = threading.Thread(target=self.interact_to_db_loop)
        self.interact_to_db_thread.start()

        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(5)
        self.server_sock.settimeout(self.accept_timeout)
        print(f"Server listening on {self.host}:{self.port}")
        self.accept_connections()

    def start(self) -> None:
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.run)
        self.thread.start()
        # game_servers_manager_thread = threading.Thread(target=self.manage_game_servers)
        # game_servers_manager_thread.start()
        time.sleep(0.2)
        try:
            while True:
                cmd = input("Enter 'stop' to stop the server: ")
                if cmd == 'stop':
                    self.stop()
                    break
                else:
                    print("invalid command.")
        except KeyboardInterrupt:
            self.stop()
            # with self.game_server_lock:
            #     for game_server in self.game_servers.values():
            #         game_server.stop()
        
        self.thread.join()
        # game_servers_manager_thread.join()

    def stop(self):
        self.stop_event.set()
        # with self.game_server_lock:
        #     for game_server in self.game_servers.values():
        #         game_server.stop()
        if not self.db_worker or self.db_worker.conn_loss_event.is_set():
            if self.db_passer:
                self.db_passer.close()

        try:
            self.server_sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            self.server_sock.close()
        except Exception:
            pass

        for psr in list(self.connections):
            try:
                psr.close()
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
                threading.Thread(target=self.handle_connections, args=(msgfmt_passer,), daemon=True).start()
                
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[Server] Exception in accept_connections: {e}")
    
    def handle_connections(self, msgfmt_passer: MessageFormatPasser) -> None:
        """Check handshake and pass to corresponding methods."""
        try:
            #while True:
            msgfmt_passer.settimeout(self.handshake_timeout)
            received_message_id, message_type, data = msgfmt_passer.receive_args(Formats.MESSAGE)
            if message_type != Words.MessageType.HANDSHAKE:
                print(f"[Server] received message_type {message_type}, expected {Words.MessageType.HANDSHAKE}")
                self.connections.remove(msgfmt_passer)
                print(f"Connection closed. Active connections: {len(self.connections)}")
                msgfmt_passer.close()
                return
            
            role = data.get(Words.DataKeys.Handshake.ROLE)
            self.send_response(msgfmt_passer, received_message_id, Words.Result.SUCCESS)
            try:
                self.on_new_connection(role, msgfmt_passer, data)
            except Exception as e:
                print(f"[Server] exception in on_new_connection: {e}")
        except Exception as e:
            print(f"[Server] Error during handshake: {e}")
        try:
            self.connections.remove(msgfmt_passer)
        except Exception:
            pass

        print(f"Connection closed. Active connections: {len(self.connections)}")

        try:
            msgfmt_passer.close()
        except Exception:
            pass

    def on_new_connection(self, role: str, passer: MessageFormatPasser, handshake_data: dict):
        """接到 handshake 後的委派點(預設只是記錄未知 role)"""
        print(f"[ServerBase] on_new_connection called with role={role} (no handler implemented)")

    # def handle_player(self, passer: MessageFormatPasser):
    #     self.passer_player_dict[passer] = None
    #     passer.settimeout(self.receive_timeout)
    #     last_hb_time = time.time()
    #     while not self.stop_event.is_set():
    #         try:
    #             msg_id, msg_type, data = passer.receive_args(Formats.MESSAGE)
    #             match msg_type:
    #                 case Words.MessageType.REQUEST:
    #                     assert isinstance(data, dict)
    #                     cmd = data.get(Words.DataKeys.Request.COMMAND)
    #                     match cmd:
    #                         case Words.Command.LOGIN:
    #                             # continue
    #                             # time.sleep(7)
    #                             # self.send_response(passer, msg_id, Words.Result.FAILURE, {Words.ParamKeys.Failure.REASON: 'suduiwee', '12': 345})
    #                             params = data.get(Words.DataKeys.PARAMS)
    #                             assert isinstance(params, dict)
    #                             username = params.get(Words.ParamKeys.Login.USERNAME)
    #                             # password = params.get(Words.ParamKeys.Login.PASSWORD)
    #                             login_data = self.try_request_and_wait(Words.Command.LOGIN, params)
                                
    #                             if login_data[Words.DataKeys.Response.RESULT] == Words.Result.SUCCESS:
    #                                 self.passer_player_dict[passer] = username
    #                                 self.send_response(passer, msg_id, Words.Result.SUCCESS)
    #                             elif login_data[Words.DataKeys.Response.RESULT] == Words.Result.FAILURE:
    #                                 params = login_data.get(Words.DataKeys.PARAMS)
    #                                 assert isinstance(params, dict)
    #                                 # reason = params.get(Words.ParamKeys.Failure.REASON)
    #                                 self.send_response(passer, msg_id, Words.Result.FAILURE, params)
    #                             else:
    #                                 self.send_response(passer, msg_id, Words.Result.FAILURE, {
    #                                     Words.ParamKeys.Failure.REASON: "Unknown login result."
    #                                 })
    #                         case Words.Command.REGISTER:
    #                             params = data.get(Words.DataKeys.PARAMS)
    #                             assert isinstance(params, dict)
    #                             # username = params.get(Words.ParamKeys.Register.USERNAME)
    #                             # password = params.get(Words.ParamKeys.Register.PASSWORD)
    #                             reg_data = self.try_request_and_wait(Words.Command.REGISTER, params)

                                
    #                             if reg_data[Words.DataKeys.Response.RESULT] == Words.Result.SUCCESS:
    #                                 self.send_response(passer, msg_id, Words.Result.SUCCESS)
    #                             elif reg_data[Words.DataKeys.Response.RESULT] == Words.Result.FAILURE:
    #                                 params = reg_data.get(Words.DataKeys.PARAMS)
    #                                 assert isinstance(params, dict)
    #                                 reason = params.get(Words.ParamKeys.Failure.REASON)
    #                                 self.send_response(passer, msg_id, Words.Result.FAILURE, {
    #                                     Words.ParamKeys.Failure.REASON: reason
    #                                 })
    #                             else:
    #                                 self.send_response(passer, msg_id, Words.Result.FAILURE, {
    #                                     Words.ParamKeys.Failure.REASON: "Unknown register result."
    #                                 })
    #                         case Words.Command.LOGOUT:
    #                             # params = data.get(Words.DataKeys.PARAMS)
    #                             # assert isinstance(params, dict)
    #                             username = self.passer_player_dict.get(passer)
    #                             if not username:
    #                                 self.send_response(passer, msg_id, Words.Result.FAILURE, {
    #                                     Words.ParamKeys.Failure.REASON: "Player not logged in yet."
    #                                 })
    #                                 continue
    #                             result_data = self.try_request_and_wait(Words.Command.LOGOUT, {
    #                                 Words.ParamKeys.Logout.USERNAME: username
    #                             })
    #                             self.send_response(passer, msg_id, result_data[Words.DataKeys.Response.RESULT], result_data.get(Words.DataKeys.PARAMS))
    #                         case Words.Command.EXIT:
    #                             username = self.passer_player_dict.get(passer)
    #                             if username:
    #                                 self.try_request_and_wait(Words.Command.LOGOUT, {
    #                                     Words.ParamKeys.Logout.USERNAME: username
    #                                 })
    #                             self.send_response(passer, msg_id, Words.Result.SUCCESS)
    #                             time.sleep(5)
    #                             break
    #                 case Words.MessageType.HEARTBEAT:
    #                     # time.sleep(12)
    #                     last_hb_time = time.time()
    #                     self.send_response(passer, msg_id, Words.Result.SUCCESS)
    #         except TimeoutError:
    #             if time.time() - last_hb_time > self.client_heartbeat_timeout:
    #                 print(f"[Server] client heartbeat timeout (>{self.client_heartbeat_timeout}s), terminating connection")
    #                 break
    #             continue
    #         except ConnectionError as e:
    #             print(f"[Server] ConnectionError raised in handle_player: {e}")
    #             break
    #         except Exception as e:
    #             print(f"[Server] exception raised in handle_player: {e}")
    #             break

    #     del self.passer_player_dict[passer]
    def try_request_and_wait(self, cmd: str, params: dict) -> dict:
        result_data = {}
        try:
            if self.db_worker is None:
                raise ConnectionError
            result_data = self.db_worker.pend_and_wait(Words.MessageType.REQUEST, 
                            {Words.DataKeys.Request.COMMAND: cmd, 
                                Words.DataKeys.PARAMS: params}, self.db_response_timeout)
            result_data.pop(Words.DataKeys.Response.RESPONDING_ID, None)
        except TimeoutError:
            result_data[Words.DataKeys.Response.RESULT] = Words.Result.FAILURE
            result_data[Words.DataKeys.PARAMS] = {
                Words.ParamKeys.Failure.REASON: "Timeout interacting database server exceeded."
            }
        except ConnectionError:
            result_data[Words.DataKeys.Response.RESULT] = Words.Result.FAILURE
            result_data[Words.DataKeys.PARAMS] = {
                Words.ParamKeys.Failure.REASON: "Server is not connected to database server."
            }
        except Exception as e:
            result_data[Words.DataKeys.Response.RESULT] = Words.Result.FAILURE
            result_data[Words.DataKeys.PARAMS] = {
                Words.ParamKeys.Failure.REASON: str(e)
            }
        return result_data
    
    def reset_db_passer(self):
        try:
            if self.db_passer:
                self.db_passer.close()
        except Exception:
            pass
        self.db_passer = MessageFormatPasser()

