import threading
import socket
from base.message_format_passer import MessageFormatPasser
from protocols.protocols import Formats, Words
from typing import Optional
import time
import uuid

DEFAULT_ACCEPT_TIMEOUT = 1.0
DEFAULT_RECEIVE_TIMEOUT = 1.0
DEFAULT_HANDSHAKE_TIMEOUT = 5.0

class ServerBase:
    def __init__(self, host: str = "0.0.0.0", port: int = 21354, 
                 accept_timeout = DEFAULT_ACCEPT_TIMEOUT, 
                 receive_timeout = DEFAULT_RECEIVE_TIMEOUT, 
                 handshake_timeout = DEFAULT_HANDSHAKE_TIMEOUT) -> None:
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = host
        self.port = port
        self.accept_timeout = accept_timeout
        self.receive_timeout = receive_timeout
        self.handshake_timeout = handshake_timeout

        # self.connections: list[MessageFormatPasser] = []
        # self.passer_player_dict: dict[MessageFormatPasser, str | None] = {}
        # self.db_server_passer: MessageFormatPasser | None = None
        self.stop_event = threading.Event()
        # self.pending_db_response_dict: dict[str, tuple[bool, str, dict]] = {}
        """The dict contains all sent db_requests, after processing, received responses will be popped. {request_id: (response_received, result, data)}"""
        # self.pending_db_response_lock = threading.Lock()
        # self.invitee_inviter_set_pair: set[tuple] = set()  # {(invitee_username, inviter_username)}
        # self.invitation_lock = threading.Lock()
        #self.game_servers: dict[str, GameServer] = {}  # {room_id: GameServer}
        # self.game_server_threads: dict[str, threading.Thread] = {}  # {room_id: Thread}
        # self.game_server_win_recorded: dict[str, bool] = {}  # {room_id: bool}
        # self.game_server_lock = threading.Lock()