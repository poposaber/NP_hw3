import socket
from message_format import MessageFormat
class Interactable:
    def send_message_format(self, sock: socket.socket, msg_format: MessageFormat, arg_list: list = []) -> None:
        try:
            msg = msg_format.build(arg_list)
            #print(f"built msg: \"{msg}\"")
            sock.send(msg.encode())
        except Exception as e:
            print(f"Error sending message format: {e}")
            raise e
        
    def send_message_format_args(self, sock: socket.socket, msg_format: MessageFormat, *args) -> None:
        self.send_message_format(sock, msg_format, list(args))

    def send_message_format_to(self, sock: socket.socket, msg_format: MessageFormat, addr: tuple[str, int], arg_list: list = []) -> None:
        try:
            msg = msg_format.build(arg_list)
            #print(f"built msg: \"{msg}\"")
            sock.sendto(msg.encode(), addr)
        except Exception as e:
            print(f"Error sending message format to {addr}: {e}")
            raise e
        
    def send_message_format_args_to(self, sock: socket.socket, msg_format: MessageFormat, addr: tuple[str, int], *args) -> None:
        self.send_message_format_to(sock, msg_format, addr, list(args))
        
    def receive_message_format_and_parse(self, sock: socket.socket, msg_format: MessageFormat) -> list:
        try:
            msg = self.receive_message_format(sock)
            
            arg_list = msg_format.parse(msg)
            #print(f"parsed arg_list: {arg_list}")
            return arg_list
        except Exception as e:
            print(f"Error receiving message format and parsing: {e}")
            raise e

    def receive_message_format(self, sock: socket.socket) -> str:
        try:
            msg = sock.recv(1024).decode()
            #print(f"received message: \"{msg}\"")
            return msg
        except Exception as e:
            print(f"Error receiving message format: {e}")
            raise e
        
    def receive_message_format_from(self, sock: socket.socket) -> tuple[str, tuple[str, int]]:
        try:
            data, addr = sock.recvfrom(1024)
            msg = data.decode()
            #print(f"received message: \"{msg}\" from {addr}")
            return (msg, addr)
        except socket.timeout as e:
            #print(f"Time out when receiving message format from an address: {e}")
            raise e
        except Exception as e:
            #print(f"Error receiving message format from an address: {e}")
            raise e
        
    def check_message_format_name(self, msg: str) -> str:
        name = msg.split(MessageFormat.SEP)[0]
        #print(f"mf_name: \"{name}\"")
        return name
    
    def receive_and_check_is_message_format_name(self, sock: socket.socket, msg_format: MessageFormat) -> bool:
        return self.check_message_format_name(self.receive_message_format(sock)) == msg_format.name
    
    def receive_and_get_format_name(self, sock: socket.socket) -> tuple[str, str]:
        msg = self.receive_message_format(sock)
        name = self.check_message_format_name(msg)
        return (msg, name)
    
    def receive_and_get_format_name_from(self, sock: socket.socket) -> tuple[str, str, tuple[str, int]]:
        msg, addr = self.receive_message_format_from(sock)
        name = self.check_message_format_name(msg)
        return (msg, name, addr)
    
    def receive_and_check_is_message_format_name_from(self, sock: socket.socket, msg_format: MessageFormat) -> tuple[bool, tuple[str, int]]:
        _, name, addr = self.receive_and_get_format_name_from(sock)
        return (name == msg_format.name, addr)
    
    def parse_message(self, msg: str, msg_format: MessageFormat) -> list:
        return msg_format.parse(msg)
    
    #def check_is_valid(self, text: str) -> bool:
        #return not (MessageFormat.SEP in text)