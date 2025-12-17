import json
import socket
import threading
from typing import Callable, Any


class GameServer:
    # host and port fields are essential. You can modify it but don't erase it.
    def __init__(self, host: str = "0.0.0.0", port: int = 12345) -> None:
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients: set[socket.socket] = set()
        self.on_close: Callable[[], None] | None = None
        self.stop_event = threading.Event()

    # This Method is essential. You can modify it but don't erase it.
    def start(self):
        self.sock.bind((self.host, self.port))
        self.sock.listen(16)
        self.sock.settimeout(1.0)
        self.port = self.sock.getsockname()[1]
        threading.Thread(target=self._accept_loop).start()
        print(f"[GameServer] listening on {self.host}:{self.port}")
        while True:
            cmd = input("Enter 'stop' to stop: ")
            if cmd == 'stop':
                self.stop()
                break

    # This Method is essential. You can modify it but don't erase it.
    def stop(self):
        self.stop_event.set()
        try:
            for c in list(self.clients):
                try:
                    c.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                try:
                    c.close()
                except Exception:
                    pass
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            self.sock.close()
        finally:
            if self.on_close:
                try:
                    self.on_close()
                except Exception:
                    pass

    def _accept_loop(self):
        while not self.stop_event.is_set():
            try:
                conn, addr = self.sock.accept()
                print(f"accepted: {addr}")
                self.clients.add(conn)
                threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _handle_client(self, conn: socket.socket, addr: tuple[str, int]) -> None:
        # This is where you handle the behaviour of client
        user = f"user@{addr[1]}"
        try:
            # Do something here.
            f = conn.makefile("rwb")
            f.write(json.dumps({"hello": user}).encode() + b"\n")
            f.flush()
            for line in f:
                msg = json.loads(line.decode())
                resp = self._process(user, msg)
                f.write(json.dumps(resp).encode() + b"\n")
                f.flush()
        except Exception:
            pass
        finally:
            try:
                self.clients.discard(conn)
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
            print("connection closed")

    def _process(self, user: str, msg: dict) -> dict:
        cmd = msg.get("cmd")
        if cmd == "ping":
            return {"ok": True, "pong": True}
        return {"ok": False, "error": f"unknown cmd: {cmd}"}