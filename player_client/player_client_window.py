import customtkinter
import tkinter
import threading
import time
from typing import Optional
from .player_client import PlayerClient

class PlayerClientWindow:
    def __init__(self, host = "127.0.0.1", port = 21354, max_connect_try_count = 5, max_handshake_try_count = 5, 
                 connect_timeout = 2.0, handshake_timeout = 2.0, receive_timeout = 1.0) -> None:
        # GUI 與 client 分離：建立 PlayerClient 實例
        self.client = PlayerClient(host=host, port=port, max_connect_try_count=max_connect_try_count, max_handshake_try_count=max_handshake_try_count, 
                                   connect_timeout=connect_timeout, handshake_timeout=handshake_timeout, receive_timeout=receive_timeout, 
                                   on_connection_done=self._on_client_connection_done, 
                                   on_connection_fail=self._on_client_connection_fail)
        self.window_thread: Optional[threading.Thread] = None
        self.window_stop_event = threading.Event()

        customtkinter.set_appearance_mode("System")
        customtkinter.set_default_color_theme("blue")
        self.app = customtkinter.CTk()
        self.app.title("Player Client")
        self.app.geometry("800x600")
        self.app.protocol("WM_DELETE_WINDOW", self.on_close)

        # frame for login
        self.login_frame = customtkinter.CTkFrame(master=self.app, width=400, height=400)
        self.login_text = customtkinter.CTkLabel(master=self.login_frame, text="Login Account", font=("Arial", 20))
        self.login_text.place(relx=0.5, rely=0.2, anchor=tkinter.CENTER)
        self.username_inputbox = customtkinter.CTkEntry(master=self.login_frame, placeholder_text="Username", width=200, height=40)
        self.username_inputbox.place(relx=0.5, rely=0.4, anchor=tkinter.CENTER)
        self.password_inputbox = customtkinter.CTkEntry(master=self.login_frame, placeholder_text="Password", width=200, height=40)
        self.password_inputbox.place(relx=0.5, rely=0.6, anchor=tkinter.CENTER)
        self.login_btn = customtkinter.CTkButton(self.login_frame, text="Login", width=100, height=40)
        self.login_btn.place(relx=0.5, rely=0.8, anchor=tkinter.CENTER)

        # frame of waiting for connection
        self.waiting_connect_frame = customtkinter.CTkFrame(master=self.app, width=200, height=100)
        self.connect_state_text = customtkinter.CTkLabel(master=self.waiting_connect_frame, text="Connecting...")
        self.connect_state_text.place(relx=0.5, rely=0.35, anchor=tkinter.CENTER)
        self.reconnect_button = customtkinter.CTkButton(master=self.waiting_connect_frame, text="Reconnect", width=70, command=self.reconnect)
        # self.reconnect_button.place(relx=0.5, rely=0.65, anchor=tkinter.CENTER)


        self.waiting_connect_frame.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)

    
    def _on_client_connection_fail(self):
        try:
            self.app.after(0, self._on_client_connection_fail_ui)
        except Exception:
            pass

    def _on_client_connection_fail_ui(self):
        self.connect_state_text.configure(text="Failed to connect to lobby server.")
        self.reconnect_button.place(relx=0.5, rely=0.65, anchor=tkinter.CENTER)

    def _on_client_connection_done(self):
        try:
            self.app.after(0, self._on_client_connection_done_ui)
        except Exception:
            pass

    def _on_client_connection_done_ui(self):
        self.waiting_connect_frame.place_forget()
        self.login_frame.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)

    def set_lobby_connection(self, host: str, port: int, max_connect_try_count: int, max_handshake_try_count: int):
        # 若在運行中改變連線參數，需重新建立 client 或在 client 中支援動態更新
        self.client.host = host
        self.client.port = port
        self.client.max_connect_try_count = max_connect_try_count
        self.client.max_handshake_try_count = max_handshake_try_count

    def reconnect(self):
        self.reconnect_button.place_forget()
        self.connect_state_text.configure(text="Connecting...")
        self.start_client()

    def start_client(self):
        self.client.start()

    def stop_client(self):
        self.client.stop()

    def on_close(self):
        self.window_stop_event.set()
        try:
            self.stop_client()
        except Exception:
            pass
        self.app.destroy()

    def window_loop(self):
        # 最簡 GUI 範例
        # customtkinter.set_appearance_mode("System")
        # customtkinter.set_default_color_theme("blue")
        # app = customtkinter.CTk()
        # app.title("Player Client")
        # app.geometry("400x200")
        # self.app = app

        # def on_close():
        #     self.window_stop_event.set()
        #     try:
        #         self.stop_client()
        #     except Exception:
        #         pass
        #     app.destroy()

        # app.protocol("WM_DELETE_WINDOW", on_close)

        # start_btn = customtkinter.CTkButton(app, text="Start Client", command=self.start_client)
        # start_btn.pack(pady=12)
        # stop_btn = customtkinter.CTkButton(app, text="Stop Client", command=self.stop_client)
        # stop_btn.pack(pady=12)

        self.app.mainloop()

    # def run(self):
    #     # 啟動 GUI 執行緒（或可直接在 main thread 執行）
    #     if self.window_thread and self.window_thread.is_alive():
    #         return
    #     self.window_stop_event.clear()
    #     self.window_thread = threading.Thread(target=self.window_loop, daemon=True)
    #     self.window_thread.start()

    def start(self):
        self.start_client()
        self.window_loop()

# class PlayerClientWindow:
#     def __init__(self, host = "127.0.0.1", port = 21354, max_connect_try_count = 5, max_handshake_try_count = 5) -> None:
#         self.lobby_passer = MessageFormatPasser()
#         self.client_thread = threading.Thread()
#         self.client_thread_stop_event = threading.Event()
#         self.window_thread = threading.Thread()
#         self.window_thread_stop_event = threading.Event()

#         self.lobby_host = host
#         self.lobby_port = port
#         self.lobby_max_connect_try_count = max_connect_try_count
#         self.lobby_max_handshake_try_count = max_handshake_try_count

#     def set_lobby_connection(self, host: str, port: int, max_connect_try_count: int, max_handshake_try_count: int):
#         self.lobby_host = host
#         self.lobby_port = port
#         self.lobby_max_connect_try_count = max_connect_try_count
#         self.lobby_max_handshake_try_count = max_handshake_try_count

#     def connect_to_lobby_server(self):
#         connect_try_count = 1
#         connect_success = False
#         while connect_try_count <= self.lobby_max_connect_try_count and not connect_success:
#             try:
#                 print(f"Attempt {connect_try_count} for connecting to lobby server")
#                 self.lobby_passer.connect(self.lobby_host, self.lobby_port)
#                 connect_success = True
#             except Exception:
#                 print("Failed to connect to lobby server. Retrying...")
#                 time.sleep(2)
#         if not connect_success:

                
#         handshake_try_count = 1
#         while handshake_try_count <= self.lobby_max_handshake_try_count:
#             try:
#                 print(f"")
#         self.lobby_passer.send_args()

#     def client_loop(self):
#         self.connect_to_lobby_server(self.host, port, max_connect_try_count, max_handshake_try_count)

#     def window_loop(self):
#         pass

#     def run(self):
#         self.client_thread = threading.Thread(target=self.client_loop)
#         self.window_thread = threading.Thread(target=self.window_loop)
        
