import customtkinter
import tkinter
import threading
import time
from typing import Optional
from .player_client import PlayerClient



class PlayerClientWindow:
    LOGIN_TIMEOUT = 5.0
    def __init__(self, host = "127.0.0.1", port = 21354, max_connect_try_count = 5, max_handshake_try_count = 5, 
                 connect_timeout = 2.0, handshake_timeout = 2.0, receive_timeout = 1.0) -> None:
        # GUI 與 client 分離：建立 PlayerClient 實例
        self.client = PlayerClient(host=host, port=port, max_connect_try_count=max_connect_try_count, max_handshake_try_count=max_handshake_try_count, 
                                   connect_timeout=connect_timeout, handshake_timeout=handshake_timeout, receive_timeout=receive_timeout, 
                                   on_connection_done=self._on_client_connection_done, 
                                   on_connection_fail=self._on_client_connection_fail, 
                                   on_connection_loss=self._on_client_connection_loss)
        
        self.window_thread: Optional[threading.Thread] = None
        self.window_stop_event = threading.Event()

        customtkinter.set_appearance_mode("System")
        customtkinter.set_default_color_theme("blue")
        self.app = customtkinter.CTk()
        self.app.title("Player Client")
        self.app.geometry("800x600")
        self.app.protocol("WM_DELETE_WINDOW", self.on_close)

        self._window_state = "login"

        self.frame_dict: dict[str, tkinter.Widget] = {}

        # frame for login
        self.login_frame = customtkinter.CTkFrame(master=self.app, width=400, height=400)
        self.login_text = customtkinter.CTkLabel(master=self.login_frame, text="Login Account", font=("Arial", 20))
        self.login_text.place(relx=0.5, rely=0.2, anchor=tkinter.CENTER)
        self.username_inputbox = customtkinter.CTkEntry(master=self.login_frame, placeholder_text="Username", width=200, height=40)
        self.username_inputbox.place(relx=0.5, rely=0.4, anchor=tkinter.CENTER)
        self.password_inputbox = customtkinter.CTkEntry(master=self.login_frame, placeholder_text="Password", width=200, height=40)
        self.password_inputbox.place(relx=0.5, rely=0.6, anchor=tkinter.CENTER)
        self.login_btn = customtkinter.CTkButton(self.login_frame, text="Login", width=100, height=40, command=self.login)
        # print(self.login_frame.children)
        self.login_btn.place(relx=0.5, rely=0.8, anchor=tkinter.CENTER)
        

        # frame of waiting for connection
        self.waiting_connect_frame = customtkinter.CTkFrame(master=self.app, width=200, height=100)
        self.connect_state_text = customtkinter.CTkLabel(master=self.waiting_connect_frame, text="Connecting...")
        self.connect_state_text.place(relx=0.5, rely=0.35, anchor=tkinter.CENTER)
        self.reconnect_button = customtkinter.CTkButton(master=self.waiting_connect_frame, text="Reconnect", width=70, command=self.reconnect)
        # self.reconnect_button.place(relx=0.5, rely=0.65, anchor=tkinter.CENTER)

        # self.frame_dict["waiting"] = self.waiting_connect_frame
        self.frame_dict["login"] = self.login_frame


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
        f = self.frame_dict[self._window_state]
        f.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)

    def _on_client_connection_loss(self):
        try:
            self.app.after(0, self._on_client_connection_loss_ui)
        except Exception:
            pass
    
    def _on_client_connection_loss_ui(self):
        f = self.frame_dict[self._window_state]
        f.place_forget()
        self.waiting_connect_frame.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)

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

    def login(self):
        self.login_btn.configure(state="disabled")
        username = self.username_inputbox.get()
        password = self.password_inputbox.get()
        threading.Thread(target=self.login_thread, args=(username, password)).start()
        # try:
        #     login_success, params = self.client.try_login(self.username_inputbox.get(), self.password_inputbox.get(), LOGIN_TIMEOUT)
        #     if not login_success:
        #         print(f"login failed. params: {params}")
        # except Exception as e:
        #     print(f"[PLAYERCLIENTWINDOW] Exception occurred in login: {e}")
        # self.login_btn.configure(state="normal")

    def login_thread(self, username: str, password: str):
        try:
            success, params = self.client.try_login(username, password, self.LOGIN_TIMEOUT)
        except Exception as e:
            success, params = False, {'error': str(e)}
        try:
            self.app.after(0, self._on_login_result_ui, success, params)
        except Exception as e:
            print(f"[PlayerClientWindow] Exception occurred in login_thread: {e}")

    def _on_login_result_ui(self, success: bool, params: dict):
        if success:
            self.login_frame.place_forget()
            # after success (not implemented)
        else:
            print(f"login failed. params: {params}")
            # display message to player
        self.login_btn.configure(state="normal")

    def start_client(self):
        self.client.start()

    def stop_client(self):
        self.client.exit_server()
        self.client.stop()

    def on_close(self):
        self.window_stop_event.set()
        try:
            self.stop_client()
        except Exception:
            pass
        self.app.destroy()

    def window_loop(self):
        self.app.mainloop()

    def start(self):
        self.start_client()
        self.window_loop()
        
