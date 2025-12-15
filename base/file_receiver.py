import socket
from pathlib import Path
import struct
import json
import os
import time

class FileReceiver:
    def __init__(self, sock: socket.socket, path: Path):
        self.sock = sock
        self.path = path

    def _recvn(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            part = self.sock.recv(n - len(buf))
            if not part:
                raise ConnectionError("socket closed during _recvn")
            buf += part
        return buf
    
    def receive(self) -> bool:
        """Receive length-prefixed header + optional chunk loop and write to self.path.
        Returns True on success, False on error.
        Protocol: 4-byte big-endian header_len, header=json({"seq":..., "size":...}),
                  then `size` bytes of payload. size==0 => terminator.
        """
        temp_path = self.path.with_suffix(self.path.suffix + ".part")
        try:
            # ensure parent exists
            os.makedirs(self.path.parent, exist_ok=True)
            with temp_path.open("wb") as outf:
                while True:
                    # read 4-byte header length
                    hdr_len_raw = self._recvn(4)
                    hdr_len = struct.unpack("!I", hdr_len_raw)[0]
                    # read header
                    hdr_raw = self._recvn(hdr_len)
                    hdr = json.loads(hdr_raw.decode("utf-8"))
                    print(f"received hdr: {hdr}")
                    size = int(hdr.get("size", 0))
                    # if there's payload, read and write it
                    if size > 0:
                        chunk = self._recvn(size)
                        outf.write(chunk)
                    else:
                        # terminator frame (size == 0)
                        break
                # ensure data hit disk before renaming
                try:
                    outf.flush()
                    os.fsync(outf.fileno())
                except Exception:
                    pass
            # atomic move to final path
            try:
                temp_path.replace(self.path)
            except Exception:
                # fallback to rename
                temp_path.rename(self.path)
            return True
        except Exception as e:
            print(f"Exception in FileReceiver.receive: {e}")
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass
            return False

    # def receive(self) -> bool:
    #     """Receive length-prefixed header + optional chunk loop and write to self.path.
    #     Returns True on success, False on error.
    #     Protocol: 4-byte big-endian header_len, header=json({"seq":..., "size":...}),
    #               then `size` bytes of payload. size==0 => terminator.
    #     """
    #     try:
    #         # ensure parent exists
    #         os.makedirs(self.path.parent, exist_ok=True)
    #         with self.path.open("wb") as outf:
    #             while True:
    #                 # read 4-byte header length
    #                 hdr_len_raw = self._recvn(4)
    #                 hdr_len = struct.unpack("!I", hdr_len_raw)[0]
    #                 # read header
    #                 hdr_raw = self._recvn(hdr_len)
    #                 hdr = json.loads(hdr_raw.decode("utf-8"))
    #                 print(f"received hdr: {hdr}")
    #                 size = int(hdr.get("size", 0))
    #                 # if there's payload, read and write it
    #                 if size > 0:
    #                     # remaining = size
    #                     # while remaining > 0:
    #                     #     chunk = self.sock.recv(min(65536, remaining))
    #                     #     if not chunk:
    #                     #         raise ConnectionError("socket closed during chunk receive")
    #                     chunk = self._recvn(size)
    #                     outf.write(chunk)
    #                     # remaining -= len(chunk)
    #                 else:
    #                     # terminator frame (size == 0)
    #                     break
    #         return True
    #     except Exception as e:
    #         print(f"Exception in FileReceiver.receive: {e}")
    #         try:
    #             # best-effort cleanup
    #             if self.path.exists() and self.path.stat().st_size == 0:
    #                 self.path.unlink()
    #         except Exception:
    #             pass
    #         return False
        
    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass