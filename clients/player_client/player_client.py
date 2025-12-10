import uuid
import threading
from queue import Queue
import time
from typing import Optional, Callable
from base.message_format_passer import MessageFormatPasser
from base.peer_worker import PeerWorker
from protocols.protocols import Formats, Words
from clients.client_base import ClientBase

DEFAULT_MAX_CONNECT_TRY_COUNT = 5
DEFAULT_MAX_HANDSHAKE_TRY_COUNT = 5
DEFAULT_CONNECT_TIMEOUT = 3.0
DEFAULT_HANDSHAKE_TIMEOUT = 3.0
DEFAULT_RECEIVE_TIMEOUT = 1.0
DEFAULT_HEARTBEAT_INTERVAL = 10.0
DEFAULT_HEARTBEAT_PATIENCE = 3
DEFAULT_LOBBY_RESPONSE_TIMEOUT = 5.0


class PlayerClient(ClientBase):
    def __init__(self, host: str = "127.0.0.1", port: int = 21354,
                 max_connect_try_count: int = DEFAULT_MAX_CONNECT_TRY_COUNT, 
                 max_handshake_try_count: int = DEFAULT_MAX_HANDSHAKE_TRY_COUNT,
                 connect_timeout = DEFAULT_CONNECT_TIMEOUT, 
                 handshake_timeout = DEFAULT_HANDSHAKE_TIMEOUT, 
                 receive_timeout = DEFAULT_RECEIVE_TIMEOUT, 
                 lobby_response_timeout = DEFAULT_LOBBY_RESPONSE_TIMEOUT, 
                 heartbeat_interval = DEFAULT_HEARTBEAT_INTERVAL, 
                 heartbeat_patience = DEFAULT_HEARTBEAT_PATIENCE, 
                 on_connection_done: Optional[Callable[[], None]] = None, 
                 on_connection_fail: Optional[Callable[[], None]] = None, 
                 on_connection_lost: Optional[Callable[[], None]] = None) -> None:
        super().__init__(host, port, max_connect_try_count, max_handshake_try_count, 
                         connect_timeout, handshake_timeout, receive_timeout, lobby_response_timeout, 
                         heartbeat_interval, heartbeat_patience, on_connection_done, on_connection_fail, on_connection_lost)
    #     self.host = host
    #     self.port = port
    #     self.max_connect_try_count = max(1, max_connect_try_count)
    #     self.max_handshake_try_count = max(1, max_handshake_try_count)
    #     self.connect_timeout = max(1.0, connect_timeout)
    #     self.handshake_timeout = max(2.0, handshake_timeout)
    #     self.receive_timeout = max(0.25, receive_timeout)
    #     self.lobby_response_timeout = lobby_response_timeout
    #     self.heartbeat_interval = max(2.0, heartbeat_interval)
    #     self.heartbeat_patience = max(2, heartbeat_patience)

    #     self.lobby_passer = MessageFormatPasser()
    #     self.worker: Optional[PeerWorker] = None

    #     self.on_connection_done = on_connection_done
    #     self.on_connection_fail = on_connection_fail
    #     self.on_connection_lost = on_connection_lost

    #     self.stop_event = threading.Event()
    #     self.stop_event.set()
    #     # self.connection_loss_event = threading.Event()
    #     # self.connection_loss_event.set()

    #     self.thread: Optional[threading.Thread] = None
    #     # self.send_msg_thread: Optional[threading.Thread] = None
    #     # self.receive_msg_thread: Optional[threading.Thread] = None
    #     # self.heartbeat_thread: Optional[threading.Thread] = None

    #     # self.pending_messages: dict[str, tuple[tuple[str, dict], bool, Optional[tuple[str, dict]]]] = {}
    #     # """{message_id: ((message_type, data) of sending message, is_sent, (message_type, data) of receiving message)}"""
    #     # self.pending_messages_lock = threading.Lock()

    #     self.event_queue: Queue = Queue()

    # def connect(self) -> bool:
    #     attempt = 1
    #     while attempt <= self.max_connect_try_count and not self.stop_event.is_set():
    #         try:
    #             print(f"[PlayerClient] connect attempt {attempt} -> {self.host}:{self.port}")
    #             self.reset_lobby_passer()
    #             self.lobby_passer.settimeout(self.connect_timeout)
    #             self.lobby_passer.connect(self.host, self.port)
    #             print("[PlayerClient] connected")
    #             return True
    #         except Exception as e:
    #             attempt += 1
    #             if attempt > self.max_connect_try_count:
    #                 print(f"[PlayerClient] connect failed: {e}")
    #                 continue
    #             print(f"[PlayerClient] connect failed: {e}, retrying...")
                
    #     return False

    # def handshake(self) -> bool:
    #     attempt = 1
    #     while attempt <= self.max_handshake_try_count and not self.stop_event.is_set():
    #         try:
    #             print(f"[PlayerClient] handshake attempt {attempt}")
    #             # 呼叫 send_args 或其他 handshake 流程
    #             self.lobby_passer.settimeout(self.handshake_timeout)
    #             message_id = str(uuid.uuid4())
    #             self.lobby_passer.send_args(Formats.MESSAGE, message_id, Words.MessageType.HANDSHAKE, 
    #                                         {Words.DataKeys.Handshake.ROLE: Words.Roles.PLAYER})
                
    #             _, message_type, data = self.lobby_passer.receive_args(Formats.MESSAGE)

    #             if message_type != Words.MessageType.RESPONSE:
    #                 error_message = f"received message_type {message_type}, expected {Words.MessageType.RESPONSE}"
    #                 print(f"[PlayerClient] {error_message}")
    #                 raise Exception(error_message)
                
    #             responding_id = data[Words.DataKeys.Response.RESPONDING_ID]
    #             if responding_id != message_id:
    #                 error_message = f"received responding_id {responding_id}, expected {message_id}"
    #                 print(f"[PlayerClient] {error_message}")
    #                 raise Exception(error_message)
                
    #             result = data[Words.DataKeys.Response.RESULT]
    #             if result != Words.Result.SUCCESS:
    #                 error_message = f"received result {result}, expected {Words.Result.SUCCESS}."
    #                 if Words.DataKeys.PARAMS in data.keys():
    #                     error_message += f" params: {data[Words.DataKeys.PARAMS]}"
    #                 print(f"[PlayerClient] {error_message}")
    #                 raise Exception(error_message)
                
    #             return True
    #         except Exception as e:
    #             attempt += 1
    #             if attempt > self.max_handshake_try_count:
    #                 print(f"[PlayerClient] connect failed: {e}")
    #                 continue
    #             print(f"[PlayerClient] handshake failed: {e}, retrying...")
    #             if not self.stop_event.is_set():
    #                 time.sleep(1)
    #     return False
    
    # def try_login(self, username: str, password: str) -> tuple[bool, dict]:
    #     try:
    #         assert self.worker is not None
    #         response = self.worker.pend_and_wait(Words.MessageType.REQUEST, {
    #             Words.DataKeys.Request.COMMAND: Words.Command.LOGIN, 
    #             Words.DataKeys.PARAMS: {
    #                 Words.ParamKeys.Login.USERNAME: username, 
    #                 Words.ParamKeys.Login.PASSWORD: password
    #             }
    #         }, self.lobby_response_timeout)
    #     except Exception as e:
    #         return (False, {'error': str(e)})
    #     if response[Words.DataKeys.Response.RESULT] != Words.Result.SUCCESS:
    #         return (False, response[Words.DataKeys.PARAMS])
    #     return (True, {})
    
    # def try_logout(self) -> tuple[bool, dict]:
    #     try:
    #         assert self.worker is not None
    #         response = self.worker.pend_and_wait(Words.MessageType.REQUEST, {
    #             Words.DataKeys.Request.COMMAND: Words.Command.LOGOUT
    #         }, self.lobby_response_timeout)
    #     except Exception as e:
    #         return (False, {'error': str(e)})
    #     if response[Words.DataKeys.Response.RESULT] != Words.Result.SUCCESS:
    #         return (False, response[Words.DataKeys.PARAMS])
    #     return (True, {})
    
    # def try_register(self, username: str, password: str) -> tuple[bool, dict]:
    #     try:
    #         assert self.worker is not None
    #         response = self.worker.pend_and_wait(Words.MessageType.REQUEST, {
    #             Words.DataKeys.Request.COMMAND: Words.Command.REGISTER, 
    #             Words.DataKeys.PARAMS: {
    #                 Words.ParamKeys.Register.USERNAME: username, 
    #                 Words.ParamKeys.Register.PASSWORD: password
    #             }
    #         }, self.lobby_response_timeout)
    #     except Exception as e:
    #         return (False, {'error': str(e)})
    #     if response[Words.DataKeys.Response.RESULT] != Words.Result.SUCCESS:
    #         return (False, response[Words.DataKeys.PARAMS])
    #     return (True, {})
    
    # # def pend_request(self, message_type: str, data: dict) -> str:
    # #     message_id = str(uuid.uuid4())
    # #     with self.pending_messages_lock:
    # #         self.pending_messages[message_id] = ((message_type, data), False, None)
    # #     return message_id
    
    # # def wait_response(self, message_id: str, timeout: Optional[float] = None) -> dict:
    # #     st = time.monotonic()
    # #     deadline = st + (timeout if timeout is not None else float('inf'))
    # #     # print(f"in wait_response. deadline={deadline}, time.monotonic()={st}")
    # #     clk = time.monotonic()
    # #     while not self.stop_event.is_set() and not self.connection_loss_event.is_set() and clk < deadline:
            
    # #         with self.pending_messages_lock:
    # #             entry = self.pending_messages[message_id]
    # #             _, _, recv = entry
    # #             if recv is not None:
    # #                 del self.pending_messages[message_id]
    # #                 return recv[1]
    # #         time.sleep(0.05)
    # #         clk = time.monotonic()

    # #     with self.pending_messages_lock:
    # #         del self.pending_messages[message_id]
    # #     if clk >= deadline:
    # #         raise TimeoutError("timeout expired")
    # #     elif self.connection_loss_event.is_set():
    # #         raise ConnectionResetError("Client is not connected to server")
    # #     else:
    # #         raise Exception("Client is not started")
            
    # # def pend_and_wait(self, message_type: str, data: dict, timeout: Optional[float] = None) -> dict:
    # #     message_id = self.pend_request(message_type, data)
    # #     return self.wait_response(message_id, timeout)
    
    # # def heartbeat_loop(self):
    # #     print("entered heartbeat_loop")
    # #     now = time.monotonic()
    # #     pre = now
    # #     remain = self.heartbeat_interval
    # #     heartbeat_fail_count = 0

    # #     while not self.stop_event.is_set() and not self.connection_loss_event.is_set():
    # #         if remain <= 0:
    # #             remain = self.heartbeat_interval
    # #             try:
    # #                 hb_result = self.pend_and_wait(Words.MessageType.HEARTBEAT, {}, self.heartbeat_interval / 2)
    # #                 result = hb_result[Words.DataKeys.Response.RESULT]
    # #                 if hb_result[Words.DataKeys.Response.RESULT] != Words.Result.SUCCESS:
    # #                     error_message = f"[PlayerClient] Warning: received non-success heartbeat result: {result}"
    # #                     if Words.DataKeys.PARAMS in hb_result.keys():
    # #                         error_message += f" with params: {hb_result[Words.DataKeys.PARAMS]}"
    # #                     print(error_message)
    # #                     heartbeat_fail_count += 1
    # #                 else:
    # #                     heartbeat_fail_count = 0
    # #             except TimeoutError:
    # #                 print("[PlayerClient] Heartbeat timeout expired")
    # #                 heartbeat_fail_count += 1
    # #             except Exception as e:
    # #                 print(f"[PlayerClient] Exception occurred in heartbeat_loop: {e}")
    # #         if heartbeat_fail_count >= self.heartbeat_patience:
    # #             self.connection_loss_event.set()
    # #         time.sleep(0.1)
    # #         now = time.monotonic()
    # #         remain -= now - pre
    # #         pre = now
    # #     print("exited heartbeat_loop")
    
    # # def send_msg_loop(self):
    # #     print("entered send_msg_loop")
    # #     while not self.stop_event.is_set() and not self.connection_loss_event.is_set():
    # #         with self.pending_messages_lock:
    # #             for msg_id, msg_status in list(self.pending_messages.items()):
    # #                 msg_tuple, is_sent, recv = msg_status
    # #                 if not is_sent:
    # #                     msg_type, data = msg_tuple
    # #                     try:
    # #                         # print(f"sending message with msg_id={msg_id}, msg_type={msg_type}, data={data}")
    # #                         self.lobby_passer.send_args(Formats.MESSAGE, msg_id, msg_type, data)
    # #                         self.pending_messages[msg_id] = (msg_tuple, True, recv)
    # #                     except Exception as e:
    # #                         print(f"[PLAYERCLIENT] Exception occurred in send_msg_loop: {e}")
    # #         time.sleep(0.1)
    # #     print("exited send_msg_loop")

    # # def recv_msg_loop(self):
    # #     print("entered recv_msg_loop")
    # #     while not self.stop_event.is_set() and not self.connection_loss_event.is_set():
    # #         try:
    # #             msg_id, msg_type, data = self.lobby_passer.receive_args(Formats.MESSAGE)
    # #             assert type(msg_id) == str and type(msg_type) == str and type(data) == dict
    # #             match msg_type:
    # #                 case Words.MessageType.RESPONSE:
    # #                     responding_id = data[Words.DataKeys.Response.RESPONDING_ID]
    # #                     with self.pending_messages_lock:
    # #                         msg_tuple, is_sent, _ = self.pending_messages[responding_id]
    # #                         self.pending_messages[responding_id] = (msg_tuple, is_sent, (msg_type, data))
    # #                 case _:
    # #                     print(f"[PlayerClient] received unknown msg_type in recv_msg_loop: {msg_type}")
    # #         except TimeoutError:
    # #             continue
    # #         except ConnectionError as e:
    # #             print(f"[PlayerClient] ConnectionError occurred in recv_msg_loop: {e}")
    # #             self.connection_loss_event.set()
    # #         except Exception as e:
    # #             print(f"[PlayerClient] Exception occurred in recv_msg_loop: {e}")
    # #     print("exited recv_msg_loop")

    # def connect_and_handshake_to_lobby(self) -> bool:
    #     if not self.connect():
    #         print("[PlayerClient] give up connecting")
    #         if self.on_connection_fail and not self.stop_event.is_set():
    #             try:
    #                 self.on_connection_fail()
    #             except Exception as e:
    #                 print(f"[PlayerClient] exception raised when calling on_connection_fail(): {e}")
    #         self.stop_event.set()
    #         return False
        
    #     if not self.handshake():
    #         print("[PlayerClient] give up handshake")
    #         if self.on_connection_fail and not self.stop_event.is_set():
    #             try:
    #                 self.on_connection_fail()
    #             except Exception as e:
    #                 print(f"[PlayerClient] exception raised when calling on_connection_fail(): {e}")
    #         self.stop_event.set()
    #         self.reset_lobby_passer()
    #         return False
        
    #     # self.connection_loss_event.clear()
    #     if self.on_connection_done:
    #         try:
    #             self.on_connection_done()
    #         except Exception as e:
    #             print(f"[PlayerClient] exception raised when calling on_connection_done(): {e}")

    #     return True

    # def run(self):
    #     while not self.stop_event.is_set():
    #         if not self.connect_and_handshake_to_lobby():
    #             break
            
    #         def on_recv(msg_tuple):
    #             msg_id, msg_type, data = msg_tuple
    #             # push non-response messages to event queue if needed
    #             self.event_queue.put((msg_id, msg_type, data))

    #         def on_lost():
    #             # self.connection_loss_event.set()
    #             if self.on_connection_lost:
    #                 try: self.on_connection_lost()
    #                 except Exception as e: print(f"[PlayerClient] on_connection_lost error: {e}")

    #         def make_hb():
    #             return (Words.MessageType.HEARTBEAT, {})

    #         self.worker = PeerWorker(
    #             passer=self.lobby_passer,
    #             receive_timeout=self.receive_timeout,
    #             heartbeat_interval=self.heartbeat_interval,
    #             heartbeat_patience=self.heartbeat_patience,
    #             on_recv_message=on_recv,
    #             on_connection_lost=on_lost,
    #             make_heartbeat=make_hb,
    #         )
    #         self.worker.start()

    #         # block until lost/stop
    #         while not self.stop_event.is_set() and not self.worker.conn_loss_event.is_set():
    #             time.sleep(0.2)

    #         try:
    #             self.worker.stop()
    #         except Exception:
    #             pass

    #         # self.lobby_passer.settimeout(self.receive_timeout)
    #         # self.receive_msg_thread = threading.Thread(target=self.recv_msg_loop)
    #         # self.receive_msg_thread.start()
    #         # self.heartbeat_thread = threading.Thread(target=self.heartbeat_loop)
    #         # self.heartbeat_thread.start()
    #         # self.send_msg_thread = threading.Thread(target=self.send_msg_loop)
    #         # self.send_msg_thread.start()

    #         # print("[PlayerClient] enter main loop")
    #         # self.receive_msg_thread.join()
    #         # self.heartbeat_thread.join()
    #         # self.send_msg_thread.join()

    #         if not self.stop_event.is_set() and self.worker.conn_loss_event.is_set():
    #             print("Reconnecting...")
    #             # with self.pending_messages_lock:
    #             #     self.pending_messages.clear()
    #             # if self.on_connection_lost:
    #             #     try:
    #             #         self.on_connection_lost()
    #             #     except Exception as e:
    #             #         print(f"[PlayerClient] Exception occurrred executing self.on_connection_lost(): {e}")

    #         self.reset_lobby_passer()
    #         # time.sleep(0.5)

    #     print("[PlayerClient] stopped")

    # def start(self):
    #     if self.thread and self.thread.is_alive():
    #         return
    #     # self._shutdown = False
    #     self.stop_event.clear()
    #     self.thread = threading.Thread(target=self.run)
    #     self.thread.start()

    # def stop(self):
    #     # self._shutdown = True
    #     self.stop_event.set()

    #     if not self.worker or self.worker.conn_loss_event.is_set(): # no connection
    #         self.reset_lobby_passer()
    #     # if self.worker:
    #     #     try:
    #     #         self.worker.stop()
    #     #     except Exception:
    #     #         pass
    #     if self.thread:
    #         self.thread.join(timeout=5)
    #     # self.reset_lobby_passer()

    # def exit_server(self):
    #     if self.worker is None:
    #         return
    #     if self.worker.conn_loss_event.is_set():
    #         return
    #     try:
    #         response = self.worker.pend_and_wait(Words.MessageType.REQUEST, {
    #             Words.DataKeys.Request.COMMAND: Words.Command.EXIT
    #         }, self.lobby_response_timeout)
    #         if response[Words.DataKeys.Response.RESULT] != Words.Result.SUCCESS:
    #             print("[PlayerClient] Warning: did not received exit success from server")
    #     except Exception as e:
    #         print(f"[PlayerClient] Exception occurred in exit_server: {e}")
        

    # def reset_lobby_passer(self):
    #     try:
    #         self.lobby_passer.close()
    #     except Exception:
    #         pass
    #     self.lobby_passer = MessageFormatPasser()

# if __name__ == '__main__':
#     pc = PlayerClient()
#     pc.start()