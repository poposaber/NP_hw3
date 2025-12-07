# next: add heartbeat patience

import customtkinter
import tkinter
import threading
import time
from typing import Optional
from .player_client import PlayerClient

NORMAL_LABEL_COLOR = "#5882ff"
HOVER_LABEL_COLOR = "#295fff"
CLICK_LABEL_COLOR = "#1f4fcc"

class PlayerClientWindow:
    # LOGIN_TIMEOUT = 5.0
    def __init__(self, host = "127.0.0.1", port = 21354) -> None:
        # GUI 與 client 分離：建立 PlayerClient 實例
        self.client = PlayerClient(host=host, port=port, 
                                   on_connection_done=self._on_client_connection_done, 
                                   on_connection_fail=self._on_client_connection_fail, 
                                   on_connection_lost=self._on_client_connection_lost)
        
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
        self.login_username_inputbox = customtkinter.CTkEntry(master=self.login_frame, placeholder_text="Username", width=200, height=40)
        self.login_username_inputbox.place(relx=0.5, rely=0.4, anchor=tkinter.CENTER)
        self.login_password_inputbox = customtkinter.CTkEntry(master=self.login_frame, placeholder_text="Password", width=200, height=40)
        self.login_password_inputbox.place(relx=0.5, rely=0.6, anchor=tkinter.CENTER)
        self.login_btn = customtkinter.CTkButton(self.login_frame, text="Login", width=100, height=40, command=self.login)
        self.login_btn.place(relx=0.5, rely=0.8, anchor=tkinter.CENTER)
        self.reg_prompt_text = customtkinter.CTkLabel(master=self.login_frame, text="Don't have an account?", font=("Arial", 11))
        self.reg_prompt_text.place(relx=0.55, rely=0.95, anchor=tkinter.CENTER)

        self.go_to_reg_label = customtkinter.CTkLabel(
            master=self.login_frame,
            text="Register",
            font=("Arial", 11),
            text_color=NORMAL_LABEL_COLOR
        )
        self.bind_effects_on_label(self.go_to_reg_label)
        self.go_to_reg_label.bind("<Button-1>", lambda e: self.go_to_register())
        self.go_to_reg_label.place(relx=0.8, rely=0.95, anchor=tkinter.CENTER)

        # frame for register
        self.reg_frame = customtkinter.CTkFrame(master=self.app, width=400, height=400)
        self.reg_text = customtkinter.CTkLabel(master=self.reg_frame, text="Register Account", font=("Arial", 20))
        self.reg_text.place(relx=0.5, rely=0.2, anchor=tkinter.CENTER)
        self.reg_username_inputbox = customtkinter.CTkEntry(master=self.reg_frame, placeholder_text="Username", width=200, height=40)
        self.reg_username_inputbox.place(relx=0.5, rely=0.4, anchor=tkinter.CENTER)
        self.reg_password_inputbox = customtkinter.CTkEntry(master=self.reg_frame, placeholder_text="Password", width=200, height=40)
        self.reg_password_inputbox.place(relx=0.5, rely=0.6, anchor=tkinter.CENTER)
        self.reg_btn = customtkinter.CTkButton(self.reg_frame, text="Register", width=100, height=40, command=self.register)
        self.reg_btn.place(relx=0.5, rely=0.8, anchor=tkinter.CENTER)
        self.reg_prompt_text = customtkinter.CTkLabel(master=self.reg_frame, text="Already have an account?", font=("Arial", 11))
        self.reg_prompt_text.place(relx=0.55, rely=0.95, anchor=tkinter.CENTER)
        self.go_to_login_label = customtkinter.CTkLabel(
            master=self.reg_frame,
            text="Login",
            font=("Arial", 11),
            text_color=NORMAL_LABEL_COLOR
        )
        self.bind_effects_on_label(self.go_to_login_label)
        self.go_to_login_label.bind("<Button-1>", lambda e: self.go_to_login())
        self.go_to_login_label.place(relx=0.8, rely=0.95, anchor=tkinter.CENTER)

        # frame of waiting for connection
        self.waiting_connect_frame = customtkinter.CTkFrame(master=self.app, width=200, height=100)
        self.connect_state_text = customtkinter.CTkLabel(master=self.waiting_connect_frame, text="Connecting...")
        self.connect_state_text.place(relx=0.5, rely=0.35, anchor=tkinter.CENTER)
        self.reconnect_button = customtkinter.CTkButton(master=self.waiting_connect_frame, text="Reconnect", width=70, command=self.reconnect)
        # self.reconnect_button.place(relx=0.5, rely=0.65, anchor=tkinter.CENTER)

        # self.frame_dict["waiting"] = self.waiting_connect_frame
        self.frame_dict["login"] = self.login_frame
        self.frame_dict["register"] = self.reg_frame

        self.waiting_connect_frame.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)

    def bind_effects_on_label(self, label: customtkinter.CTkLabel):
        # Change cursor on hover
        label.bind("<Enter>", lambda e: label.configure(cursor="hand2", text_color=HOVER_LABEL_COLOR))
        label.bind("<Leave>", lambda e: label.configure(cursor="", text_color=NORMAL_LABEL_COLOR))
        # Change color on press it
        label.bind("<ButtonPress-1>", lambda e: label.configure(text_color=CLICK_LABEL_COLOR))
        label.bind("<ButtonRelease-1>", lambda e: label.configure(text_color=HOVER_LABEL_COLOR))

    
    def _on_client_connection_fail(self):
        if self.window_stop_event.is_set():
            return
        try:
            self.app.after(0, self._on_client_connection_fail_ui)
        except Exception:
            pass

    def _on_client_connection_fail_ui(self):
        self.connect_state_text.configure(text="Failed to connect to lobby server.")
        self.reconnect_button.place(relx=0.5, rely=0.65, anchor=tkinter.CENTER)

    def _on_client_connection_done(self):
        if self.window_stop_event.is_set():
            return
        try:
            self.app.after(0, self._on_client_connection_done_ui)
        except Exception:
            pass

    def _on_client_connection_done_ui(self):
        self.waiting_connect_frame.place_forget()
        f = self.frame_dict[self._window_state]
        f.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)

    def _on_client_connection_lost(self):
        if self.window_stop_event.is_set():
            return
        try:
            self.app.after(0, self._on_client_connection_lost_ui)
        except Exception:
            pass
    
    def _on_client_connection_lost_ui(self):
        f = self.frame_dict[self._window_state]
        f.place_forget()
        self.waiting_connect_frame.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)

    def update_window_state(self, state: str):
        if state not in self.frame_dict.keys():
            return
        f = self.frame_dict[self._window_state]
        f.place_forget()
        self._window_state = state
        f = self.frame_dict[self._window_state]
        f.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)

    def go_to_register(self):
        self.login_username_inputbox.delete(0, "end")
        self.login_password_inputbox.delete(0, "end")
        self.reg_username_inputbox.delete(0, "end")
        self.reg_password_inputbox.delete(0, "end")
        try:
            self.reg_username_inputbox.focus()  # move focus to root
        except Exception:
            pass
        self.update_window_state("register")

    def go_to_login(self):
        self.login_username_inputbox.delete(0, "end")
        self.login_password_inputbox.delete(0, "end")
        self.reg_username_inputbox.delete(0, "end")
        self.reg_password_inputbox.delete(0, "end")
        try:
            self.login_username_inputbox.focus()  # move focus to root
        except Exception:
            pass
        self.update_window_state("login")

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
        username = self.login_username_inputbox.get()
        password = self.login_password_inputbox.get()
        threading.Thread(target=self.login_thread, args=(username, password)).start()
        # try:
        #     login_success, params = self.client.try_login(self.login_username_inputbox.get(), self.login_password_inputbox.get(), LOGIN_TIMEOUT)
        #     if not login_success:
        #         print(f"login failed. params: {params}")
        # except Exception as e:
        #     print(f"[PLAYERCLIENTWINDOW] Exception occurred in login: {e}")
        # self.login_btn.configure(state="normal")

    def login_thread(self, username: str, password: str):
        success, params = self.client.try_login(username, password)
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

    def register(self):
        self.reg_btn.configure(state="disabled")
        username = self.reg_username_inputbox.get()
        password = self.reg_password_inputbox.get()
        threading.Thread(target=self.reg_thread, args=(username, password)).start()

    def reg_thread(self, username: str, password: str):
        success, params = self.client.try_register(username, password)
        try:
            self.app.after(0, self._on_reg_result_ui, success, params)
        except Exception as e:
            print(f"[PlayerClientWindow] Exception occurred in login_thread: {e}")

    def _on_reg_result_ui(self, success: bool, params: dict):
        if success:
            self.update_window_state("login")
            # after success (not implemented)
        else:
            print(f"Register failed. params: {params}")
            # display message to player
        self.reg_btn.configure(state="normal")


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
        
