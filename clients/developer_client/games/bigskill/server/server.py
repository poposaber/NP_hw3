import socket
import threading
import time

class GameServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 12359) -> None:
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients: list[socket.socket] = []
        self.stop_event = threading.Event()

    def start(self):
        self.sock.bind((self.host, self.port))
        self.sock.listen(2)
        self.sock.settimeout(1.0)
        self.port = self.sock.getsockname()[1]
        print(f"[GameServer] listening on {self.host}:{self.port}")
        # accept two clients
        while len(self.clients) < 2 and not self.stop_event.is_set():
            try:
                conn, addr = self.sock.accept()
                print(f"accepted: {addr}")
                # set a short timeout so recv won't block forever
                try:
                    conn.settimeout(1.0)
                except Exception:
                    pass
                self.clients.append(conn)
            except socket.timeout:
                continue

        # assign roles
        try:
            if len(self.clients) >= 2:
                self.clients[0].send(b"ROLE|A")
                self.clients[1].send(b"ROLE|B")
        except Exception:
            pass

        # start forwarding threads
        t1 = threading.Thread(target=self._forward_loop, args=(self.clients[0], self.clients[1]), daemon=True)
        t2 = threading.Thread(target=self._forward_loop, args=(self.clients[1], self.clients[0]), daemon=True)
        t1.start()
        t2.start()

        # wait until both forwarding threads finish or stop_event is set
        try:
            while (t1.is_alive() or t2.is_alive()) and not self.stop_event.is_set():
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        self.stop()

    def stop(self):
        self.stop_event.set()
        for c in list(self.clients):
            try:
                c.close()
            except Exception:
                pass
        try:
            self.sock.close()
        except Exception:
            pass

    def _forward_loop(self, src: socket.socket, dst: socket.socket):
        try:
            while not self.stop_event.is_set():
                try:
                    data = src.recv(1024)
                except socket.timeout:
                    # no data received within timeout; continue waiting
                    continue
                except Exception as e:
                    print(f"[GameServer] recv error: {e}")
                    break

                if not data:
                    # remote closed connection
                    break

                try:
                    dst.sendall(data)
                except Exception as e:
                    print(f"[GameServer] failed to send data to dst: {e}")
                    break
        finally:
            try:
                src.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                dst.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                src.close()
            except Exception:
                pass
            try:
                dst.close()
            except Exception:
                pass
# import json
# import socket
# import threading
# from typing import Callable, Any


# class GameServer:
#     # host and port fields are essential. You can modify it but don't erase it.
#     def __init__(self, host: str = "0.0.0.0", port: int = 12345) -> None:
#         self.host = host
#         self.port = port
#         self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#         self.clients: set[socket.socket] = set()
#         self.on_close: Callable[[], None] | None = None
#         self.stop_event = threading.Event()

#     # This Method is essential. You can modify it but don't erase it.
#     def start(self):
#         self.sock.bind((self.host, self.port))
#         self.sock.listen(16)
#         self.sock.settimeout(1.0)
#         self.port = self.sock.getsockname()[1]
#         threading.Thread(target=self._accept_loop).start()
#         print(f"[GameServer] listening on {self.host}:{self.port}")
#         while True:
#             cmd = input("Enter 'stop' to stop: ")
#             if cmd == 'stop':
#                 self.stop()
#                 break

#     # This Method is essential. You can modify it but don't erase it.
#     def stop(self):
#         self.stop_event.set()
#         try:
#             for c in list(self.clients):
#                 try:
#                     c.shutdown(socket.SHUT_RDWR)
#                 except Exception:
#                     pass
#                 try:
#                     c.close()
#                 except Exception:
#                     pass
#             try:
#                 self.sock.shutdown(socket.SHUT_RDWR)
#             except Exception:
#                 pass
#             self.sock.close()
#         finally:
#             if self.on_close:
#                 try:
#                     self.on_close()
#                 except Exception:
#                     pass

#     def _accept_loop(self):
#         while not self.stop_event.is_set():
#             try:
#                 conn, addr = self.sock.accept()
#                 print(f"accepted: {addr}")
#                 self.clients.add(conn)
#                 threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()
#             except socket.timeout:
#                 continue
#             except OSError:
#                 break

#     def _handle_client(self, conn: socket.socket, addr: tuple[str, int]) -> None:
#         # This is where you handle the behaviour of client
#         user = f"user@{addr[1]}"
#         try:
#             # Do something here.
#             f = conn.makefile("rwb")
#             f.write(json.dumps({"hello": user}).encode() + b"\n")
#             f.flush()
#             for line in f:
#                 msg = json.loads(line.decode())
#                 resp = self._process(user, msg)
#                 f.write(json.dumps(resp).encode() + b"\n")
#                 f.flush()
#         except Exception:
#             pass
#         finally:
#             try:
#                 self.clients.discard(conn)
#             except Exception:
#                 pass
#             try:
#                 conn.close()
#             except Exception:
#                 pass
#             print("connection closed")

#     def _process(self, user: str, msg: dict) -> dict:
#         cmd = msg.get("cmd")
#         if cmd == "ping":
#             return {"ok": True, "pong": True}
#         return {"ok": False, "error": f"unknown cmd: {cmd}"}