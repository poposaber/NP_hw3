import socket
from pathlib import Path
import json
import struct

CHUNK_MAX = 60 * 1024

class FileSender:
    def __init__(self, sock: socket.socket, path: Path):
        self.sock = sock
        self.path = path

    def send(self):
        # passer = self.client.worker.passer
        seq = 0
        with self.path.open("rb") as f:
            while True:
                chunk = f.read(CHUNK_MAX)
                if not chunk:
                    break
                self._send_chunk(seq, chunk)
                seq += 1
            self._send_chunk(seq, None)

    def _send_chunk(self, seq: int, chunk: bytes | None):
        d = {"seq": seq, "size": len(chunk) if chunk else 0}
        print(f"sent dict: {d}")
        header = json.dumps(d).encode("utf-8")
        frame = struct.pack("!I", len(header)) + header + (chunk or b"")
        self.sock.sendall(frame)

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass