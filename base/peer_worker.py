from __future__ import annotations
import threading
import time
import uuid
from typing import Callable, Optional, Tuple, Dict
from base.message_format_passer import MessageFormatPasser
from protocols.protocols import Formats, Words

class PeerWorker:
    """
    Generic peer worker:
    - owns a MessageFormatPasser
    - handles pending messages {id: ((type, data), sent, recv)}
    - runs send/recv/heartbeat threads
    - exposes pend_and_wait API
    """
    def __init__(
        self,
        passer: MessageFormatPasser,
        receive_timeout: float,
        heartbeat_interval: float,
        heartbeat_patience: int,
        on_recv_message: Optional[Callable[[Tuple[str, str, dict]], None]] = None,
        on_connection_lost: Optional[Callable[[], None]] = None,
        make_heartbeat: Optional[Callable[[], Tuple[str, dict]]] = None,
    ) -> None:
        self.passer = passer
        self.receive_timeout = receive_timeout
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_patience = heartbeat_patience
        self.on_recv_message = on_recv_message
        self.on_connection_lost = on_connection_lost
        self.make_heartbeat = make_heartbeat  # returns (msg_type, data) or None

        self.stop_event = threading.Event()
        self.conn_loss_event = threading.Event()

        self.pending_messages: Dict[str, Tuple[Tuple[str, dict], bool, Optional[Tuple[str, dict]]]] = {}
        self.pending_lock = threading.Lock()

        self.send_thread: Optional[threading.Thread] = None
        self.recv_thread: Optional[threading.Thread] = None
        self.hb_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self.stop_event.clear()
        self.conn_loss_event.clear()
        self.passer.settimeout(self.receive_timeout)

        self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self.recv_thread.start()

        self.hb_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.hb_thread.start()

        self.send_thread = threading.Thread(target=self._send_loop, daemon=True)
        self.send_thread.start()

    def join(self) -> None:
        if self.recv_thread: self.recv_thread.join(timeout=3)
        if self.hb_thread: self.hb_thread.join(timeout=3)
        if self.send_thread: self.send_thread.join(timeout=3)

    def stop(self) -> None:
        # Signal loops
        self.stop_event.set()
        self.conn_loss_event.set()
        try:
            self.passer.close()
        except Exception:
            pass
        # print("stop here")
        self.join()
        
        # Cleanup pending
        with self.pending_lock:
            self.pending_messages.clear()
        

    def pend_request(self, message_type: str, data: dict) -> str:
        message_id = str(uuid.uuid4())
        with self.pending_lock:
            self.pending_messages[message_id] = ((message_type, data), False, None)
        return message_id

    def wait_response(self, message_id: str, timeout: Optional[float] = None) -> dict:
        deadline = time.monotonic() + (timeout if timeout is not None else float('inf'))
        while not self.stop_event.is_set() and not self.conn_loss_event.is_set() and time.monotonic() < deadline:
            with self.pending_lock:
                entry = self.pending_messages.get(message_id)
                if entry is not None:
                    _, _, recv = entry
                    if recv is not None:
                        del self.pending_messages[message_id]
                        return recv[1] # {responding_id: ..., result: ..., params: ...}
                
            time.sleep(0.05)

        with self.pending_lock:
            self.pending_messages.pop(message_id, None)
        if time.monotonic() >= deadline:
            raise TimeoutError("timeout expired")
        elif self.conn_loss_event.is_set():
            raise ConnectionResetError("connection lost")
        else:
            raise Exception("worker stopped")

    def pend_and_wait(self, message_type: str, data: dict, timeout: Optional[float] = None) -> dict:
        message_id = self.pend_request(message_type, data)
        return self.wait_response(message_id, timeout)

    def _send_loop(self):
        print("[Worker] Entered send_loop")
        while not self.stop_event.is_set() and not self.conn_loss_event.is_set():
            try:
                with self.pending_lock:
                    for msg_id, (msg_tuple, is_sent, recv) in list(self.pending_messages.items()):
                        if not is_sent:
                            msg_type, data = msg_tuple
                            self.passer.send_args(Formats.MESSAGE, msg_id, msg_type, data)
                            self.pending_messages[msg_id] = (msg_tuple, True, recv)
            except Exception as e:
                # Sending failed -> likely connection gone
                self.conn_loss_event.set()
                if self.on_connection_lost:
                    self.on_connection_lost()
            time.sleep(0.1)
        print("[Worker] Exited send_loop")

    def _recv_loop(self):
        print("[Worker] Entered recv_loop")
        while not self.stop_event.is_set() and not self.conn_loss_event.is_set():
            try:
                # print("recv loop here")
                msg_id, msg_type, data = self.passer.receive_args(Formats.MESSAGE)
                # Route responses to pending; others to callback
                if msg_type == Words.MessageType.RESPONSE:
                    responding_id = data[Words.DataKeys.Response.RESPONDING_ID]
                    with self.pending_lock:
                        entry = self.pending_messages.get(responding_id)
                        if entry:
                            msg_tuple, is_sent, _ = entry
                            self.pending_messages[responding_id] = (msg_tuple, is_sent, (msg_type, data))
                        else:
                            print(f"[PeerWorker] received response with unknown responding_id: {data}")
                else:
                    # Push non-response messages to upper layer
                    if self.on_recv_message:
                        self.on_recv_message((msg_id, msg_type, data))
                    else:
                        print(f"[PeerWorker] Received non-response message: {(msg_id, msg_type, data)}")
            except TimeoutError:
                continue
            except ConnectionError:
                print("recv loop connectionerror")
                self.conn_loss_event.set()
                if self.on_connection_lost:
                    self.on_connection_lost()
            except Exception as e:
                print(f"recv loop exception: {e}")
                self.conn_loss_event.set()
                if self.on_connection_lost:
                    self.on_connection_lost()
                # print("exception here")
        # exit
        print("[Worker] Exited recv_loop")

    def _heartbeat_loop(self):
        if not self.make_heartbeat:
            return  # optional
        print("[Worker] Entered heartbeat_loop")
        now = time.monotonic()
        pre = now
        remain = self.heartbeat_interval
        fail_count = 0
        while not self.stop_event.is_set() and not self.conn_loss_event.is_set():
            if remain <= 0:
                remain = self.heartbeat_interval
                try:
                    hb_type, hb_data = self.make_heartbeat()
                    hb_resp = self.pend_and_wait(hb_type, hb_data, self.heartbeat_interval / 2)
                    rslt = hb_resp.get(Words.DataKeys.Response.RESULT)
                    if rslt != Words.Result.SUCCESS:
                        print(f"[Worker] Received handshake result: {rslt}, expected: {Words.Result.SUCCESS}")
                        fail_count += 1
                    else:
                        fail_count = 0
                except TimeoutError:
                    print("[Worker] Handshake timeout expired.")
                    fail_count += 1
                except Exception as e:
                    print(f"[Worker] Unknown exception occurred in heartbeat_loop: {e}")
                    fail_count += 1
            if fail_count >= self.heartbeat_patience:
                self.conn_loss_event.set()
                if self.on_connection_lost:
                    self.on_connection_lost()
            time.sleep(0.1)
            now = time.monotonic()
            remain -= now - pre
            pre = now
        print("[Worker] Exited heartbeat_loop")