import socket
import struct
import json
import threading
from .message_format import MessageFormat

LENGTH_LIMIT = 65536
RECEIVE_CHUNK_TIMEOUT = 15.0
RECEIVE_ACTUAL_MESSAGE_TIMEOUT = 20.0


class MessageFormatPasser:
    """This class handles sending and receiving MessageFormat objects over a TCP socket."""
    def __init__(self, sock: socket.socket | None = None, timeout: float | None = None) -> None:
        if sock is None:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.sock = sock
        if timeout is not None:
            if timeout <= 0:
                raise ValueError("Timeout must be positive")
        self.timeout = timeout
        self.sock.settimeout(timeout)
        self.send_lock = threading.Lock()
        self.receive_lock = threading.Lock()

    def connect(self, host: str = "127.0.0.1", port: int = 21354) -> None:
        self.sock.connect((host, port))

    def settimeout(self, timeout: float | None) -> None:
        if timeout is not None and timeout <= 0:
            raise ValueError("Timeout must be positive")
        self.timeout = timeout
        self.sock.settimeout(timeout)

    def send_args(self, msgfmt: MessageFormat, *args) -> None:
        json_data = msgfmt.to_json(*args)
        encoded = json_data.encode('utf-8')
        self.send_raw(encoded)
        # sending_data = struct.pack('!I', len(encoded)) + encoded
        # print(f"Sending message: {sending_data}")
        # with self.send_lock:
        #     self.sock.sendall(sending_data)

    def send_raw(self, data: bytes) -> None:
        """Send raw bytes with 4-byte length prefix"""
        # Prefix the JSON data with its length (4 bytes, network byte order)
        sending_data = struct.pack('!I', len(data)) + data
        print(f"\nSending raw data: {sending_data}")
        with self.send_lock:
            self.sock.sendall(sending_data)

    def send_chunk(self, seq: int, chunk: bytes | None):
        if not chunk:
            header = json.dumps({"seq": seq, "size": 0}).encode("utf-8")
            self.send_raw(header)
            return
        header = json.dumps({"seq": seq, "size": len(chunk)}).encode("utf-8")
        frame = struct.pack("!I", len(header)) + header + chunk
        with self.send_lock:
            self.sock.sendall(frame)

    def recv_chunk(self) -> tuple[int, bytes | None]:
        prefix_dict = json.loads(self.receive_raw())
        print(f"\nreceived prefix_dict: {prefix_dict}")
        size = prefix_dict.get("size")
        seq = prefix_dict.get("seq")
        if size == 0:
            return seq, None
        chunk = self.read_exactly(size)
        return seq, chunk



    def read_exactly(self, num_bytes: int) -> bytes:
        """Read exactly num_bytes from self.sock."""
        data = b""
        with self.receive_lock:
            data = self.sock.recv(num_bytes)
            # temp_timeout = self.timeout
            # self.settimeout(None)
            while len(data) < num_bytes:
                try:
                    chunk = self.sock.recv(num_bytes - len(data))
                except socket.timeout:
                    raise TimeoutError("recv timeout") from None
                if not chunk:
                    raise ConnectionError("Connection closed")
                data += chunk
            # self.settimeout(temp_timeout)
        return data

    def receive_args(self, msgfmt: MessageFormat) -> list:
        json_data = self.receive_raw().decode("utf-8")
        # self.settimeout(temp_timeout)
        # print(f"Received message: {json_data}")
        return msgfmt.to_arg_list(json_data)
    
    def receive_raw(self) -> bytes:
        """Receive 4-byte length-prefixed raw bytes"""
        # print("Entered receive_raw")

        # Read the prefix (exactly 4 bytes) to determine the length of the incoming message
        length_prefix = self.read_exactly(4)
        print(f"\nreceived length_prefix: {length_prefix}")
        if not length_prefix:
            raise ConnectionError("Connection closed")
        message_length = struct.unpack('!I', length_prefix)[0]
        if message_length <= 0:
            raise ValueError("Received message with non-positive length")
        elif message_length > LENGTH_LIMIT:
            raise ValueError("Received message exceeds length limit")
        
        # Now read the actual raw data
        # temp_timeout = self.timeout
        # self.settimeout(None)
        raw_data = self.read_exactly(message_length)
        print(f"received raw_data: {raw_data}")
        # self.settimeout(temp_timeout)
        return raw_data
    
    def close(self) -> None:
        try:
            # Unblock any pending recv/send immediately
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            self.sock.close()
        except Exception:
            pass

