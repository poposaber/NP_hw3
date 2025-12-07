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


class LobbyServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 21354, 
                 db_host: str = "127.0.0.1", db_port: int = 32132, 
                 accept_timeout = DEFAULT_ACCEPT_TIMEOUT, 
                 connect_timeout = DEFAULT_CONNECT_TIMEOUT, 
                 receive_timeout = DEFAULT_RECEIVE_TIMEOUT, 
                 handshake_timeout = DEFAULT_HANDSHAKE_TIMEOUT, 
                 db_response_timeout = DEFAULT_DB_RESPONSE_TIMEOUT, 
                 max_handshake_try_count = DEFAULT_MAX_HANDSHAKE_TRY_COUNT, 
                 db_heartbeat_interval = DEFAULT_DB_HEARTBEAT_INTERVAL, 
                 db_heartbeat_patience = DEFAULT_DB_HEARTBEAT_PATIENCE) -> None:
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = host
        self.port = port
        self.db_host = db_host
        self.db_port = db_port
        self.accept_timeout = accept_timeout
        self.connect_timeout = connect_timeout
        self.receive_timeout = receive_timeout
        self.handshake_timeout = handshake_timeout
        self.db_response_timeout = db_response_timeout
        self.max_handshake_try_count = max_handshake_try_count
        self.db_heartbeat_interval = db_heartbeat_interval
        self.db_heartbeat_patience = db_heartbeat_patience
        self.connections: list[MessageFormatPasser] = []
        self.passer_player_dict: dict[MessageFormatPasser, str | None] = {}

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
        self.invitee_inviter_set_pair: set[tuple] = set()  # {(invitee_username, inviter_username)}
        self.invitation_lock = threading.Lock()
        #self.game_servers: dict[str, GameServer] = {}  # {room_id: GameServer}
        self.game_server_threads: dict[str, threading.Thread] = {}  # {room_id: Thread}
        self.game_server_win_recorded: dict[str, bool] = {}  # {room_id: bool}
        self.game_server_lock = threading.Lock()

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
                print(f"[LobbyServer] connect attempt {attempt} -> {self.db_host}:{self.db_port}")
                self.reset_db_passer()
                self.db_passer.settimeout(self.connect_timeout)
                self.db_passer.connect(self.db_host, self.db_port)
                print("[LobbyServer] connected")
                return True
            except Exception as e:
                attempt += 1
                print(f"[LobbyServer] connect failed: {e}, retrying...")
                
                
        return False

    def handshake(self) -> bool:
        attempt = 1
        while attempt <= self.max_handshake_try_count and not self.stop_event.is_set():
            try:
                print(f"[LobbyServer] handshake attempt {attempt}")
                # 呼叫 send_args 或其他 handshake 流程
                self.db_passer.settimeout(self.handshake_timeout)
                message_id = str(uuid.uuid4())
                self.db_passer.send_args(Formats.MESSAGE, message_id, Words.MessageType.HANDSHAKE, 
                                            {Words.DataKeys.Handshake.ROLE: Words.Roles.LOBBYSERVER})
                
                _, message_type, data = self.db_passer.receive_args(Formats.MESSAGE)
                if message_type != Words.MessageType.RESPONSE:
                    error_message = f"received message_type {message_type}, expected {Words.MessageType.RESPONSE}"
                    # print(f"[LobbyServer] {error_message}")
                    raise Exception(error_message)
                responding_id = data[Words.DataKeys.Response.RESPONDING_ID]
                if responding_id != message_id:
                    error_message = f"received responding_id {responding_id}, expected {message_id}"
                    # print(f"[LobbyServer] {error_message}")
                    raise Exception(error_message)
                result = data[Words.DataKeys.Response.RESULT]
                if result != Words.Result.SUCCESS:
                    error_message = f"received result {result}, expected {Words.Result.SUCCESS}."
                    if Words.DataKeys.PARAMS in data.keys():
                        error_message += f" params: {data[Words.DataKeys.PARAMS]}"
                    # print(f"[LobbyServer] {error_message}")
                    raise Exception(error_message)
                return True
            except Exception as e:
                attempt += 1
                if attempt > self.max_handshake_try_count:
                    print(f"[LobbyServer] handshake failed: {e}")
                    continue
                print(f"[LobbyServer] handshake failed: {e}, retrying...")
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
            #         print(f"[LobbyServer] received unknown msg_type from DB: {msg_type}")

            def on_db_lost():
                print("[LobbyServer] DB connection lost")
                # self.connection_to_db_loss_event.set()

            def make_db_hb():
                return (Words.MessageType.HEARTBEAT, {})

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
                print("[LobbyServer] Reconnecting to database server...")
                # with self.pending_db_messages_lock:
                #     self.pending_db_messages.clear()
            
            # self.reset_db_passer()

        print("[LobbyServer] stopped")
            # self.connection_to_db_loss_event.clear()
            # self.send_msg_thread = threading.Thread(target=self.send_msg_loop)
            # self.send_msg_thread.start()
            # self.receive_msg_thread = threading.Thread(target=self.recv_msg_loop)
            # self.receive_msg_thread.start()
            # self.heartbeat_thread = threading.Thread(target=self.heartbeat_loop)
            # self.heartbeat_thread.start()

            # self.receive_msg_thread.join()
            # self.heartbeat_thread.join()
            # self.send_msg_thread.join()


    # def heartbeat_loop(self):
    #     print("Entered heartbeat_loop")
    #     now = time.monotonic()
    #     pre = now
    #     remain = self.db_heartbeat_interval
    #     heartbeat_fail_count = 0

    #     while not self.stop_event.is_set() and not self.connection_to_db_loss_event.is_set():
    #         if remain <= 0:
    #             remain = self.db_heartbeat_interval
    #             try:
    #                 hb_result = self.db_worker.pend_and_wait(Words.MessageType.HEARTBEAT, {}, self.db_heartbeat_interval / 2)
    #                 result = hb_result[Words.DataKeys.Response.RESULT]
    #                 if hb_result[Words.DataKeys.Response.RESULT] != Words.Result.SUCCESS:
    #                     error_message = f"[LobbyServer] Warning: received non-success heartbeat result: {result}"
    #                     if Words.DataKeys.PARAMS in hb_result.keys():
    #                         error_message += f" with params: {hb_result[Words.DataKeys.PARAMS]}"
    #                     print(error_message)
    #                     heartbeat_fail_count += 1
    #                 else:
    #                     heartbeat_fail_count = 0
    #             except TimeoutError:
    #                 print("[LobbyServer] Heartbeat timeout expired")
    #                 heartbeat_fail_count += 1
    #             except Exception as e:
    #                 print(f"[LobbyServer] Exception occurred in heartbeat_loop: {e}")
    #         if heartbeat_fail_count >= self.db_heartbeat_patience:
    #             self.connection_to_db_loss_event.set()
    #         time.sleep(0.1)
    #         now = time.monotonic()
    #         remain -= now - pre
    #         pre = now
    #     print("exited heartbeat_loop")
    
    # def send_msg_loop(self):
    #     print("Entered send_msg_loop")
    #     while not self.stop_event.is_set() and not self.connection_to_db_loss_event.is_set():
    #         with self.pending_db_messages_lock:
    #             for msg_id, msg_status in list(self.pending_db_messages.items()):
    #                 msg_tuple, is_sent, recv = msg_status
    #                 if not is_sent:
    #                     msg_type, data = msg_tuple
    #                     try:
    #                         # print(f"sending message with msg_id={msg_id}, msg_type={msg_type}, data={data}")
    #                         self.db_passer.send_args(Formats.MESSAGE, msg_id, msg_type, data)
    #                         self.pending_db_messages[msg_id] = (msg_tuple, True, recv)
    #                     except Exception as e:
    #                         print(f"[LobbyServer] Exception occurred in send_msg_loop: {e}")
    #         time.sleep(0.1)
    #     print("exited send_msg_loop")

    # def recv_msg_loop(self):
    #     print("Entered recv_msg_loop")
    #     while not self.stop_event.is_set() and not self.connection_to_db_loss_event.is_set():
    #         try:
    #             msg_id, msg_type, data = self.db_passer.receive_args(Formats.MESSAGE)
    #             assert type(msg_id) == str and type(msg_type) == str and type(data) == dict
    #             match msg_type:
    #                 case Words.MessageType.RESPONSE:
    #                     responding_id = data[Words.DataKeys.Response.RESPONDING_ID]
    #                     with self.pending_db_messages_lock:
    #                         msg_tuple, is_sent, _ = self.pending_db_messages[responding_id]
    #                         self.pending_db_messages[responding_id] = (msg_tuple, is_sent, (msg_type, data))
    #                 case _:
    #                     print(f"[LobbyServer] received unknown msg_type in recv_msg_loop: {msg_type}")
    #         except TimeoutError:
    #             continue
    #         except ConnectionError as e:
    #             print(f"[LobbyServer] ConnectionError occurred in recv_msg_loop: {e}")
    #             self.connection_to_db_loss_event.set()
    #         except Exception as e:
    #             print(f"[LobbyServer] Exception occurred in recv_msg_loop: {e}")
    #     print("exited recv_msg_loop")

    def run(self):
        self.interact_to_db_thread = threading.Thread(target=self.interact_to_db_loop)
        self.interact_to_db_thread.start()

        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(5)
        self.server_sock.settimeout(self.accept_timeout)
        print(f"Lobby server listening on {self.host}:{self.port}")
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
            self.db_passer.close()

        try:
            self.server_sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            self.server_sock.close()
        except Exception:
            pass

        for psr in self.connections:
            psr.close()

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
            except Exception as e:
                print(f"[LobbyServer] Exception in accept_connections: {e}")
    
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
                case Words.Roles.PLAYER:
                    self.send_response(msgfmt_passer, received_message_id, Words.Result.SUCCESS)
                    self.handle_player(msgfmt_passer)
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

        self.connections.remove(msgfmt_passer)
        print(f"Connection closed. Active connections: {len(self.connections)}")
        msgfmt_passer.close()

    def handle_player(self, passer: MessageFormatPasser):
        self.passer_player_dict[passer] = None
        passer.settimeout(self.receive_timeout)
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
                                password = params.get(Words.ParamKeys.Login.PASSWORD)
                                login_data = {}
                                try:
                                    if self.db_worker is None:
                                        raise ConnectionError
                                    login_data = self.db_worker.pend_and_wait(Words.MessageType.REQUEST, 
                                                    {Words.DataKeys.Request.COMMAND: Words.Command.LOGIN, 
                                                        Words.DataKeys.PARAMS: {
                                                            Words.ParamKeys.Login.USERNAME: username, 
                                                            Words.ParamKeys.Login.PASSWORD: password
                                                        }}, self.db_response_timeout)
                                except TimeoutError:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: "Timeout interacting database server exceeded."
                                    })
                                    continue
                                except ConnectionError:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: "Lobby server is not connected to database server."
                                    })
                                    continue
                                except Exception as e:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: str(e)
                                    })
                                    continue
                                if login_data[Words.DataKeys.Response.RESULT] == Words.Result.SUCCESS:
                                    self.send_response(passer, msg_id, Words.Result.SUCCESS)
                                elif login_data[Words.DataKeys.Response.RESULT] == Words.Result.FAILURE:
                                    params = login_data.get(Words.DataKeys.PARAMS)
                                    assert isinstance(params, dict)
                                    reason = params.get(Words.ParamKeys.Failure.REASON)
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: reason
                                    })
                                else:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: "Unknown login result."
                                    })
                            case Words.Command.REGISTER:
                                params = data.get(Words.DataKeys.PARAMS)
                                assert isinstance(params, dict)
                                username = params.get(Words.ParamKeys.Register.USERNAME)
                                password = params.get(Words.ParamKeys.Register.PASSWORD)
                                reg_data = {}
                                try:
                                    if self.db_worker is None:
                                        raise ConnectionError
                                    reg_data = self.db_worker.pend_and_wait(Words.MessageType.REQUEST, 
                                                    {Words.DataKeys.Request.COMMAND: Words.Command.REGISTER, 
                                                        Words.DataKeys.PARAMS: {
                                                            Words.ParamKeys.Register.USERNAME: username, 
                                                            Words.ParamKeys.Register.PASSWORD: password
                                                        }}, self.db_response_timeout)
                                except TimeoutError:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: "Timeout interacting database server exceeded."
                                    })
                                    continue
                                except ConnectionError:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: "Lobby server is not connected to database server."
                                    })
                                    continue
                                except Exception as e:
                                    self.send_response(passer, msg_id, Words.Result.FAILURE, {
                                        Words.ParamKeys.Failure.REASON: str(e)
                                    })
                                    continue
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
                            case Words.Command.EXIT:
                                self.send_response(passer, msg_id, Words.Result.SUCCESS)
                                time.sleep(5)
                                break
                    case Words.MessageType.HEARTBEAT:
                        # time.sleep(12)
                        self.send_response(passer, msg_id, Words.Result.SUCCESS)
            except TimeoutError:
                # print("timeout")
                continue
            except ConnectionError as e:
                print(f"[LobbyServer] ConnectionError raised in handle_player: {e}")
                break
            except Exception as e:
                print(f"[LobbyServer] exception raised in handle_player: {e}")

        del self.passer_player_dict[passer]

    # def pend_request(self, message_type: str, data: dict) -> str:
    #     message_id = str(uuid.uuid4())
    #     with self.pending_db_messages_lock:
    #         self.pending_db_messages[message_id] = ((message_type, data), False, None)
    #     return message_id
    
    # def wait_response(self, message_id: str, timeout: Optional[float] = None) -> dict:
    #     st = time.monotonic()
    #     deadline = st + (timeout if timeout is not None else float('inf'))
    #     # print(f"in wait_response. deadline={deadline}, time.monotonic()={st}")
    #     clk = time.monotonic()
    #     while not self.stop_event.is_set() and not self.connection_to_db_loss_event.is_set() and clk < deadline:
    #         with self.pending_db_messages_lock:
    #             entry = self.pending_db_messages[message_id]
    #             _, _, recv = entry
    #             if recv is not None:
    #                 del self.pending_db_messages[message_id]
    #                 return recv[1]
    #         time.sleep(0.05)
    #         clk = time.monotonic()

    #     with self.pending_db_messages_lock:
    #         del self.pending_db_messages[message_id]
    #     if clk >= deadline:
    #         raise TimeoutError("timeout expired")
    #     elif self.connection_to_db_loss_event.is_set():
    #         raise ConnectionResetError("Lobby server is not connected to database server.")
    #     else:
    #         raise Exception("Lobby server is not started")
        
    # def pend_and_wait(self, message_type: str, data: dict, timeout: Optional[float] = None) -> dict:
    #     message_id = self.pend_request(message_type, data)
    #     return self.wait_response(message_id, timeout)
    
    def reset_db_passer(self):
        try:
            self.db_passer.close()
        except Exception:
            pass
        self.db_passer = MessageFormatPasser()

