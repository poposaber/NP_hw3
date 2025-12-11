import uuid
import threading
from queue import Queue
import time
from typing import Optional, Callable
from base.message_format_passer import MessageFormatPasser
from base.peer_worker import PeerWorker
from protocols.protocols import Formats, Words

DEFAULT_MAX_CONNECT_TRY_COUNT = 5
DEFAULT_MAX_HANDSHAKE_TRY_COUNT = 5
DEFAULT_CONNECT_TIMEOUT = 3.0
DEFAULT_HANDSHAKE_TIMEOUT = 3.0
DEFAULT_RECEIVE_TIMEOUT = 1.0
DEFAULT_HEARTBEAT_INTERVAL = 10.0
DEFAULT_HEARTBEAT_PATIENCE = 3
DEFAULT_SERVER_RESPONSE_TIMEOUT = 5.0


class ClientBase:
    def __init__(self, host: str, port: int, role: str, 
                 max_connect_try_count: int = DEFAULT_MAX_CONNECT_TRY_COUNT, 
                 max_handshake_try_count: int = DEFAULT_MAX_HANDSHAKE_TRY_COUNT,
                 connect_timeout = DEFAULT_CONNECT_TIMEOUT, 
                 handshake_timeout = DEFAULT_HANDSHAKE_TIMEOUT, 
                 receive_timeout = DEFAULT_RECEIVE_TIMEOUT, 
                 server_response_timeout = DEFAULT_SERVER_RESPONSE_TIMEOUT, 
                 heartbeat_interval = DEFAULT_HEARTBEAT_INTERVAL, 
                 heartbeat_patience = DEFAULT_HEARTBEAT_PATIENCE, 
                 on_connection_done: Optional[Callable[[], None]] = None, 
                 on_connection_fail: Optional[Callable[[], None]] = None, 
                 on_connection_lost: Optional[Callable[[], None]] = None) -> None:
        self.host = host
        self.port = port
        self.role = role
        self.max_connect_try_count = max(1, max_connect_try_count)
        self.max_handshake_try_count = max(1, max_handshake_try_count)
        self.connect_timeout = max(1.0, connect_timeout)
        self.handshake_timeout = max(2.0, handshake_timeout)
        self.receive_timeout = max(0.25, receive_timeout)
        self.server_response_timeout = server_response_timeout
        self.heartbeat_interval = max(2.0, heartbeat_interval)
        self.heartbeat_patience = max(2, heartbeat_patience)

        self.server_passer = MessageFormatPasser()
        self.worker: Optional[PeerWorker] = None

        self.on_connection_done = on_connection_done
        self.on_connection_fail = on_connection_fail
        self.on_connection_lost = on_connection_lost

        self.stop_event = threading.Event()
        self.stop_event.set()
        # self.connection_loss_event = threading.Event()
        # self.connection_loss_event.set()

        self.thread: Optional[threading.Thread] = None
        # self.send_msg_thread: Optional[threading.Thread] = None
        # self.receive_msg_thread: Optional[threading.Thread] = None
        # self.heartbeat_thread: Optional[threading.Thread] = None

        # self.pending_messages: dict[str, tuple[tuple[str, dict], bool, Optional[tuple[str, dict]]]] = {}
        # """{message_id: ((message_type, data) of sending message, is_sent, (message_type, data) of receiving message)}"""
        # self.pending_messages_lock = threading.Lock()

        self.event_queue: Queue = Queue()

    def connect(self) -> bool:
        attempt = 1
        while attempt <= self.max_connect_try_count and not self.stop_event.is_set():
            try:
                print(f"[Client] connect attempt {attempt} -> {self.host}:{self.port}")
                self.reset_server_passer()
                self.server_passer.settimeout(self.connect_timeout)
                self.server_passer.connect(self.host, self.port)
                print("[Client] connected")
                return True
            except Exception as e:
                attempt += 1
                if attempt > self.max_connect_try_count:
                    print(f"[Client] connect failed: {e}")
                    continue
                print(f"[Client] connect failed: {e}, retrying...")
                
        return False

    def handshake(self) -> bool:
        attempt = 1
        while attempt <= self.max_handshake_try_count and not self.stop_event.is_set():
            try:
                print(f"[Client] handshake attempt {attempt}")
                # 呼叫 send_args 或其他 handshake 流程
                self.server_passer.settimeout(self.handshake_timeout)
                message_id = str(uuid.uuid4())
                self.server_passer.send_args(Formats.MESSAGE, message_id, Words.MessageType.HANDSHAKE, 
                                            {Words.DataKeys.Handshake.ROLE: self.role})
                
                _, message_type, data = self.server_passer.receive_args(Formats.MESSAGE)

                if message_type != Words.MessageType.RESPONSE:
                    error_message = f"received message_type {message_type}, expected {Words.MessageType.RESPONSE}"
                    print(f"[Client] {error_message}")
                    raise Exception(error_message)
                
                responding_id = data[Words.DataKeys.Response.RESPONDING_ID]
                if responding_id != message_id:
                    error_message = f"received responding_id {responding_id}, expected {message_id}"
                    print(f"[Client] {error_message}")
                    raise Exception(error_message)
                
                result = data[Words.DataKeys.Response.RESULT]
                if result != Words.Result.SUCCESS:
                    error_message = f"received result {result}, expected {Words.Result.SUCCESS}."
                    if Words.DataKeys.PARAMS in data.keys():
                        error_message += f" params: {data[Words.DataKeys.PARAMS]}"
                    print(f"[Client] {error_message}")
                    raise Exception(error_message)
                
                return True
            except Exception as e:
                attempt += 1
                if attempt > self.max_handshake_try_count:
                    print(f"[Client] connect failed: {e}")
                    continue
                print(f"[Client] handshake failed: {e}, retrying...")
                if not self.stop_event.is_set():
                    time.sleep(1)
        return False
    
    def try_login(self, username: str, password: str) -> tuple[bool, dict]:
        try:
            assert self.worker is not None
            response = self.worker.pend_and_wait(Words.MessageType.REQUEST, {
                Words.DataKeys.Request.COMMAND: Words.Command.LOGIN, 
                Words.DataKeys.PARAMS: {
                    Words.ParamKeys.Login.USERNAME: username, 
                    Words.ParamKeys.Login.PASSWORD: password
                }
            }, self.server_response_timeout)
        except Exception as e:
            return (False, {'error': str(e)})
        if response[Words.DataKeys.Response.RESULT] != Words.Result.SUCCESS:
            return (False, response[Words.DataKeys.PARAMS])
        return (True, {})
    
    def try_logout(self) -> tuple[bool, dict]:
        try:
            assert self.worker is not None
            response = self.worker.pend_and_wait(Words.MessageType.REQUEST, {
                Words.DataKeys.Request.COMMAND: Words.Command.LOGOUT
            }, self.server_response_timeout)
        except Exception as e:
            return (False, {'error': str(e)})
        if response[Words.DataKeys.Response.RESULT] != Words.Result.SUCCESS:
            return (False, response[Words.DataKeys.PARAMS])
        return (True, {})
    
    def try_register(self, username: str, password: str) -> tuple[bool, dict]:
        try:
            assert self.worker is not None
            response = self.worker.pend_and_wait(Words.MessageType.REQUEST, {
                Words.DataKeys.Request.COMMAND: Words.Command.REGISTER, 
                Words.DataKeys.PARAMS: {
                    Words.ParamKeys.Register.USERNAME: username, 
                    Words.ParamKeys.Register.PASSWORD: password
                }
            }, self.server_response_timeout)
        except Exception as e:
            return (False, {'error': str(e)})
        if response[Words.DataKeys.Response.RESULT] != Words.Result.SUCCESS:
            return (False, response[Words.DataKeys.PARAMS])
        return (True, {})

    def connect_and_handshake_to_server(self) -> bool:
        if not self.connect():
            print("[Client] give up connecting")
            if self.on_connection_fail and not self.stop_event.is_set():
                try:
                    self.on_connection_fail()
                except Exception as e:
                    print(f"[Client] exception raised when calling on_connection_fail(): {e}")
            self.stop_event.set()
            return False
        
        if not self.handshake():
            print("[Client] give up handshake")
            if self.on_connection_fail and not self.stop_event.is_set():
                try:
                    self.on_connection_fail()
                except Exception as e:
                    print(f"[Client] exception raised when calling on_connection_fail(): {e}")
            self.stop_event.set()
            self.reset_server_passer()
            return False
        
        # self.connection_loss_event.clear()
        if self.on_connection_done:
            try:
                self.on_connection_done()
            except Exception as e:
                print(f"[Client] exception raised when calling on_connection_done(): {e}")

        return True

    def run(self):
        while not self.stop_event.is_set():
            if not self.connect_and_handshake_to_server():
                break
            
            def on_recv(msg_tuple):
                msg_id, msg_type, data = msg_tuple
                # push non-response messages to event queue if needed
                self.event_queue.put((msg_id, msg_type, data))

            def on_lost():
                # self.connection_loss_event.set()
                if self.on_connection_lost:
                    try: self.on_connection_lost()
                    except Exception as e: print(f"[Client] on_connection_lost error: {e}")

            def make_hb():
                return (Words.MessageType.HEARTBEAT, {})

            self.worker = PeerWorker(
                passer=self.server_passer,
                receive_timeout=self.receive_timeout,
                heartbeat_interval=self.heartbeat_interval,
                heartbeat_patience=self.heartbeat_patience,
                on_recv_message=on_recv,
                on_connection_lost=on_lost,
                make_heartbeat=make_hb,
            )
            self.worker.start()

            # block until lost/stop
            while not self.stop_event.is_set() and not self.worker.conn_loss_event.is_set():
                time.sleep(0.2)

            try:
                self.worker.stop()
            except Exception:
                pass

            # self.server_passer.settimeout(self.receive_timeout)
            # self.receive_msg_thread = threading.Thread(target=self.recv_msg_loop)
            # self.receive_msg_thread.start()
            # self.heartbeat_thread = threading.Thread(target=self.heartbeat_loop)
            # self.heartbeat_thread.start()
            # self.send_msg_thread = threading.Thread(target=self.send_msg_loop)
            # self.send_msg_thread.start()

            # print("[Client] enter main loop")
            # self.receive_msg_thread.join()
            # self.heartbeat_thread.join()
            # self.send_msg_thread.join()

            if not self.stop_event.is_set() and self.worker.conn_loss_event.is_set():
                print("Reconnecting...")
                # with self.pending_messages_lock:
                #     self.pending_messages.clear()
                # if self.on_connection_lost:
                #     try:
                #         self.on_connection_lost()
                #     except Exception as e:
                #         print(f"[Client] Exception occurrred executing self.on_connection_lost(): {e}")

            self.reset_server_passer()
            # time.sleep(0.5)

        print("[Client] stopped")

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        # self._shutdown = False
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.run)
        self.thread.start()

    def stop(self):
        # self._shutdown = True
        self.stop_event.set()

        if not self.worker or self.worker.conn_loss_event.is_set(): # no connection
            self.reset_server_passer()
        # if self.worker:
        #     try:
        #         self.worker.stop()
        #     except Exception:
        #         pass
        if self.thread:
            self.thread.join(timeout=5)
        # self.reset_server_passer()

    def exit_server(self):
        if self.worker is None:
            return
        if self.worker.conn_loss_event.is_set():
            return
        try:
            response = self.worker.pend_and_wait(Words.MessageType.REQUEST, {
                Words.DataKeys.Request.COMMAND: Words.Command.EXIT
            }, self.server_response_timeout)
            if response[Words.DataKeys.Response.RESULT] != Words.Result.SUCCESS:
                print("[Client] Warning: did not received exit success from server")
        except Exception as e:
            print(f"[Client] Exception occurred in exit_server: {e}")
        

    def reset_server_passer(self):
        try:
            self.server_passer.close()
        except Exception:
            pass
        self.server_passer = MessageFormatPasser()