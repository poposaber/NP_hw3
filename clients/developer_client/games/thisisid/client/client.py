import json
import socket
import time
from typing import Optional

class GameClient:
    # host and port fields are essential. You can modify it but don't erase it.
    def __init__(self, host: str = "127.0.0.1", port: int = 12345):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None

    # This Method is essential. You can modify it but don't erase it.
    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        f = self.sock.makefile("rwb")
        # read greeting
        line = f.readline()
        if not line:
            raise RuntimeError("server closed")
        print("greeting:", line)

        # send ping every second
        for i in range(5):
            f.write(json.dumps({"cmd": "ping"}).encode() + b"\n")
            f.flush()
            line = f.readline()
            if not line:
                break
            print("resp:", line)
            time.sleep(1)
        self.stop()

    # This Method is essential. You can modify it but don't erase it.
    def stop(self):
        try:
            if self.sock:
                self.sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass