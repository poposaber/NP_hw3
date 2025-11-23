import uuid
import threading
import time
from typing import Optional
from base.message_format_passer import MessageFormatPasser
from protocols.protocols import Formats, Words

class PlayerClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 21354,
                 max_connect_try_count: int = 5, max_handshake_try_count: int = 5,
                 passer: Optional[MessageFormatPasser] = None, 
                 connect_timeout = 2.0, handshake_timeout = 3.0, receive_timeout = 1.0) -> None:
        self.host = host
        self.port = port
        self.max_connect_try_count = max_connect_try_count
        self.max_handshake_try_count = max_handshake_try_count
        self.connect_timeout = connect_timeout
        self.handshake_timeout = handshake_timeout
        self.receive_timeout = receive_timeout
        self.lobby_passer = passer or MessageFormatPasser()
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.pending_requests: dict[str, tuple[tuple[str, dict], bool, Optional[tuple[str, dict]]]] = {}
        """{message_id: ((message_type, data) of sending message, is_sent, (message_type, data) of receiving message)}"""
        self.pending_requests_lock = threading.Lock()

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
    
    def pend(self, data: dict) -> str:
        message_id = str(uuid.uuid4())
        with self.pending_requests_lock:
            self.pending_requests[message_id] = ((Words.MessageType.REQUEST, data), False, None)
        return message_id

    def run(self):
        if not self.connect():
            print("[PlayerClient] give up connecting")
            return
        if not self.handshake():
            print("[PlayerClient] give up handshake")
            self.reset_lobby_passer()
            return
        print("[PlayerClient] enter main loop")
        try:
            while not self.stop_event.is_set():
                # TODO: 實作接收/處理訊息
                time.sleep(0.1)
        finally:
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