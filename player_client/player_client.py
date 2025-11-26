# next: put the loop to run()

import uuid
import threading
from queue import Queue
import time
from typing import Optional, Callable
from base.message_format_passer import MessageFormatPasser
from protocols.protocols import Formats, Words

class PlayerClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 21354,
                 max_connect_try_count: int = 5, max_handshake_try_count: int = 5,
                 passer: Optional[MessageFormatPasser] = None, 
                 connect_timeout = 2.0, handshake_timeout = 3.0, receive_timeout = 1.0, 
                 on_connection_done: Optional[Callable[[], None]] = None, 
                 on_connection_fail: Optional[Callable[[], None]] = None) -> None:
        self.host = host
        self.port = port
        self.max_connect_try_count = max_connect_try_count
        self.max_handshake_try_count = max_handshake_try_count
        self.connect_timeout = connect_timeout
        self.handshake_timeout = handshake_timeout
        self.receive_timeout = receive_timeout
        self.lobby_passer = passer or MessageFormatPasser()
        self.on_connection_done = on_connection_done
        self.on_connection_fail = on_connection_fail
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        # self.send_msg_thread: Optional[threading.Thread] = None
        self.receive_msg_thread: Optional[threading.Thread] = None
        self.pending_messages: dict[str, tuple[tuple[str, dict], bool, Optional[tuple[str, dict]]]] = {}
        """{message_id: ((message_type, data) of sending message, is_sent, (message_type, data) of receiving message)}"""
        self.pending_messages_lock = threading.Lock()
        self.event_queue: Queue = Queue()

    def connect(self) -> bool:
        attempt = 1
        while attempt <= self.max_connect_try_count and not self.stop_event.is_set():
            try:
                print(f"[PlayerClient] connect attempt {attempt} -> {self.host}:{self.port}")
                self.lobby_passer.settimeout(self.connect_timeout)
                self.lobby_passer.connect(self.host, self.port)
                print("[PlayerClient] connected")
                return True
            except Exception as e:
                attempt += 1
                if attempt > self.max_connect_try_count:
                    print(f"[PlayerClient] connect failed: {e}")
                    continue
                print(f"[PlayerClient] connect failed: {e}, retrying...")
                time.sleep(1)
                
        return False

    def handshake(self) -> bool:
        attempt = 1
        while attempt <= self.max_handshake_try_count and not self.stop_event.is_set():
            try:
                print(f"[PlayerClient] handshake attempt {attempt}")
                # 呼叫 send_args 或其他 handshake 流程
                self.lobby_passer.settimeout(self.handshake_timeout)
                message_id = str(uuid.uuid4())
                self.lobby_passer.send_args(Formats.MESSAGE, message_id, Words.MessageType.HANDSHAKE, 
                                            {Words.DataKeys.Handshake.ROLE: Words.Roles.PLAYER})
                
                _, message_type, data = self.lobby_passer.receive_args(Formats.MESSAGE)
                if message_type != Words.MessageType.RESPONSE:
                    error_message = f"received message_type {message_type}, expected {Words.MessageType.RESPONSE}"
                    print(f"[PlayerClient] {error_message}")
                    raise Exception(error_message)
                responding_id = data[Words.DataKeys.Response.RESPONDING_ID]
                if responding_id != message_id:
                    error_message = f"received responding_id {responding_id}, expected {message_id}"
                    print(f"[PlayerClient] {error_message}")
                    raise Exception(error_message)
                result = data[Words.DataKeys.Response.RESULT]
                if result != Words.Result.SUCCESS:
                    error_message = f"received result {result}, expected {Words.Result.SUCCESS}"
                    print(f"[PlayerClient] {error_message}")
                    raise Exception(error_message)
                return True
            except Exception as e:
                attempt += 1
                if attempt > self.max_handshake_try_count:
                    print(f"[PlayerClient] connect failed: {e}")
                    continue
                print(f"[PlayerClient] handshake failed: {e}, retrying...")
                time.sleep(1)
        return False
    
    def try_login(self, username: str, password: str) -> tuple[bool, dict]:
        return (False, {})
    
    def pend_request(self, data: dict) -> str:
        message_id = str(uuid.uuid4())
        with self.pending_messages_lock:
            self.pending_messages[message_id] = ((Words.MessageType.REQUEST, data), False, None)
        return message_id
    
    def wait_response(self, message_id: str, timeout: Optional[float] = None) -> Optional[dict]:
        deadline = time.monotonic() + (timeout if timeout is not None else float('inf'))
        while not self.stop_event.is_set and time.monotonic() < deadline:
            with self.pending_messages_lock:
                entry = self.pending_messages[message_id]
                if entry is None:
                    return None
                _, _, recv = entry
                if recv is not None:
                    return recv[1]
            time.sleep(0.05)
            
    
    def send_msg_loop(self):
        print("entered send_msg_loop")
        while not self.stop_event.is_set():
            with self.pending_messages_lock:
                for msg_id, msg_status in list(self.pending_messages.items()):
                    msg_tuple, is_sent, recv = msg_status
                    if not is_sent:
                        msg_type, data = msg_tuple
                        try:
                            print(f"sending message with msg_id={msg_id}, msg_type={msg_type}, data={data}")
                            self.lobby_passer.send_args(Formats.MESSAGE, msg_id, msg_type, data)
                            self.pending_messages[msg_id] = (msg_tuple, True, recv)
                        except Exception as e:
                            print(f"[PLAYERCLIENT] Exception occurred in send_msg_loop: {e}")
            time.sleep(0.1)
        print("exited send_msg_loop")

    def recv_msg_loop(self):
        print("entered recv_msg_loop")
        while not self.stop_event.is_set():
            try:
                msg_id, msg_type, data = self.lobby_passer.receive_args(Formats.MESSAGE)
                assert type(msg_id) == str and type(msg_type) == str and type(data) == dict
                match msg_type:
                    case Words.MessageType.RESPONSE:
                        responding_id = data[Words.DataKeys.Response.RESPONDING_ID]
                        with self.pending_messages_lock:
                            msg_tuple, is_sent, _ = self.pending_messages[responding_id]
                            self.pending_messages[responding_id] = (msg_tuple, is_sent, (msg_type, data))
                    case _:
                        print(f"[PLAYERCLIENT] received unknown msg_type in recv_msg_loop: {msg_type}")
            except TimeoutError:
                continue
            except Exception as e:
                print(f"[PLAYERCLIENT] Exception occurred in recv_msg_loop: {e}")
        print("exited recv_msg_loop")

    def run(self):
        if not self.connect():
            print("[PlayerClient] give up connecting")
            if self.on_connection_fail and not self.stop_event.is_set():
                try:
                    self.on_connection_fail()
                except Exception as e:
                    print(f"[PlayerClient] exception raised when calling on_connection_fail(): {e}")
            return
        if not self.handshake():
            print("[PlayerClient] give up handshake")
            if self.on_connection_fail and not self.stop_event.is_set():
                try:
                    self.on_connection_fail()
                except Exception as e:
                    print(f"[PlayerClient] exception raised when calling on_connection_fail(): {e}")
            self.reset_lobby_passer()
            return
        
        if self.on_connection_done:
            try:
                self.on_connection_done()
            except Exception as e:
                print(f"[PlayerClient] exception raised when calling on_connection_done(): {e}")

        self.lobby_passer.settimeout(self.receive_timeout)
        self.receive_msg_thread = threading.Thread(target=self.recv_msg_loop)
        self.receive_msg_thread.start()

        print("[PlayerClient] enter main loop")
        self.send_msg_loop()

        try:
            self.reset_lobby_passer()
        except Exception:
            pass
        print("[PlayerClient] stopped")

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.run)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
        self.reset_lobby_passer()

    def reset_lobby_passer(self):
        self.lobby_passer.close()
        self.lobby_passer = MessageFormatPasser()

# if __name__ == '__main__':
#     pc = PlayerClient()
#     pc.start()