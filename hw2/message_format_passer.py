import socket
import struct
import threading
from message_format import MessageFormat

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

    def settimeout(self, timeout: float) -> None:
        if timeout <= 0:
            raise ValueError("Timeout must be positive")
        self.timeout = timeout
        self.sock.settimeout(timeout)

    def send_args(self, msgfmt: MessageFormat, *args) -> None:
        json_data = msgfmt.to_json(*args)
        # Prefix the JSON data with its length (4 bytes, network byte order)
        sending_data = struct.pack('!I', len(json_data)) + json_data.encode('utf-8')
        print(f"Sending message: {sending_data}")
        with self.send_lock:
            self.sock.sendall(sending_data)

    def read_exactly(self, num_bytes: int) -> bytes:
        """Read exactly num_bytes from self.sock."""
        data = b""
        with self.receive_lock:
            data = self.sock.recv(num_bytes)
            self.sock.settimeout(None)
            while len(data) < num_bytes:
                chunk = self.sock.recv(num_bytes - len(data))
                if not chunk:
                    raise ConnectionError("Connection closed")
                data += chunk
            self.sock.settimeout(self.timeout)
        return data

    def receive_args(self, msgfmt: MessageFormat) -> list:
        # Read the prefix (exactly 4 bytes) to determine the length of the incoming message
        length_prefix = self.read_exactly(4)
        #print(f"Received length prefix: {length_prefix}")
        if not length_prefix:
            raise ConnectionError("Connection closed")
        message_length = struct.unpack('!I', length_prefix)[0]
        #print(f"Message length: {message_length}")
        if message_length <= 0:
            raise ValueError("Received message with non-positive length")
        elif message_length > LENGTH_LIMIT:
            raise ValueError("Received message exceeds length limit")
        
        # Now read the actual message data
        self.sock.settimeout(None)
        json_data = self.read_exactly(message_length).decode("utf-8")
        print(f"Received message: {json_data}")
        return msgfmt.to_arg_list(json_data)
    
    def close(self) -> None:
        self.sock.close()

