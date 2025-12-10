# next: add heartbeat patience

import customtkinter
import tkinter
import threading
# import time
from typing import Optional, Callable
# from .player_client import PlayerClient
from clients.client_base import ClientBase
from protocols.protocols import Words

NORMAL_LABEL_COLOR = "#5882ff"
HOVER_LABEL_COLOR = "#295fff"
CLICK_LABEL_COLOR = "#1f4fcc"

class ClientWindowBase:
    # LOGIN_TIMEOUT = 5.0
    def __init__(self, host: str, port: int, client: ClientBase) -> None:
        # GUI 與 client 分離：建立 PlayerClient 實例
        # self.client = PlayerClient(host=host, port=port, 
        #                            on_connection_done=self._on_client_connection_done, 
        #                            on_connection_fail=self._on_client_connection_fail, 
        #                            on_connection_lost=self._on_client_connection_lost)
        self.client = client
        
        self.window_thread: Optional[threading.Thread] = None
        self.window_stop_event = threading.Event()

        customtkinter.set_appearance_mode("System")
        customtkinter.set_default_color_theme("blue")
        self.app = customtkinter.CTk()
        self.app.title("Client")
        self.app.geometry("800x600")
        self.app.resizable(False, False)
        self.app.protocol("WM_DELETE_WINDOW", self.on_close)

        self._window_state = "login"

        self.frame_dict: dict[str, tkinter.Widget] = {}

        # frame for login
        self.login_frame = customtkinter.CTkFrame(master=self.app, width=400, height=400)
        self.login_text = customtkinter.CTkLabel(master=self.login_frame, text="Login", font=("Arial", 25, "bold"))
        self.login_text.place(relx=0.5, rely=0.2, anchor=tkinter.CENTER)
        self.login_username_inputbox = customtkinter.CTkEntry(master=self.login_frame, placeholder_text="Username", width=200, height=40)
        self.login_username_inputbox.bind("<Return>", lambda e: self.login_password_inputbox.focus())
        self.login_username_inputbox.bind("<Down>", lambda e: self.login_password_inputbox.focus())
        self.login_username_inputbox.place(relx=0.5, rely=0.4, anchor=tkinter.CENTER)
        self.login_password_inputbox = customtkinter.CTkEntry(master=self.login_frame, placeholder_text="Password", show=u"\u2022", width=200, height=40)
        self.login_password_inputbox.bind("<Return>", lambda e: self.login())
        self.login_password_inputbox.bind("<Up>", lambda e: self.login_username_inputbox.focus())
        self.login_password_inputbox.place(relx=0.5, rely=0.6, anchor=tkinter.CENTER)
        self.login_error_label = customtkinter.CTkLabel(master=self.login_frame, text="", font=("Arial", 15), text_color="red")
        self.login_error_label.place(relx=0.5, rely=0.7, anchor=tkinter.CENTER)
        self.login_btn = customtkinter.CTkButton(self.login_frame, text="Login", width=100, height=40, command=self.login)
        self.login_btn.place(relx=0.5, rely=0.8, anchor=tkinter.CENTER)
        self.reg_prompt_text = customtkinter.CTkLabel(master=self.login_frame, text="Don't have an account?", font=("Arial", 11))
        self.reg_prompt_text.place(relx=0.65, rely=0.95, anchor=tkinter.CENTER)

        self.go_to_reg_label = customtkinter.CTkLabel(
            master=self.login_frame,
            text="Register",
            font=("Arial", 11),
            text_color=NORMAL_LABEL_COLOR
        )
        self.bind_func_on_label(self.go_to_reg_label, self.go_to_register)
        self.go_to_reg_label.place(relx=0.9, rely=0.95, anchor=tkinter.CENTER)

        # frame for register
        self.reg_frame = customtkinter.CTkFrame(master=self.app, width=400, height=400)
        self.reg_text = customtkinter.CTkLabel(master=self.reg_frame, text="Register", font=("Arial", 25, "bold"))
        self.reg_text.place(relx=0.5, rely=0.2, anchor=tkinter.CENTER)
        self.reg_username_inputbox = customtkinter.CTkEntry(master=self.reg_frame, placeholder_text="Username", width=200, height=40)
        self.reg_username_inputbox.bind("<Return>", lambda e: self.reg_password_inputbox.focus())
        self.reg_username_inputbox.bind("<Down>", lambda e: self.reg_password_inputbox.focus())
        self.reg_username_inputbox.place(relx=0.5, rely=0.35, anchor=tkinter.CENTER)
        self.reg_password_inputbox = customtkinter.CTkEntry(master=self.reg_frame, placeholder_text="Password", show=u"\u2022", width=200, height=40)
        self.reg_password_inputbox.bind("<Return>", lambda e: self.reg_confirm_password_inputbox.focus())
        self.reg_password_inputbox.bind("<Up>", lambda e: self.reg_username_inputbox.focus())
        self.reg_password_inputbox.bind("<Down>", lambda e: self.reg_confirm_password_inputbox.focus())
        self.reg_password_inputbox.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)
        self.reg_confirm_password_inputbox = customtkinter.CTkEntry(master=self.reg_frame, placeholder_text="Confirm password", show=u"\u2022", width=200, height=40)
        self.reg_confirm_password_inputbox.bind("<Return>", lambda e: self.register())
        self.reg_confirm_password_inputbox.bind("<Up>", lambda e: self.reg_password_inputbox.focus())
        self.reg_confirm_password_inputbox.place(relx=0.5, rely=0.65, anchor=tkinter.CENTER)
        self.reg_error_label = customtkinter.CTkLabel(master=self.reg_frame, text="", font=("Arial", 15), text_color="red")
        self.reg_error_label.place(relx=0.5, rely=0.75, anchor=tkinter.CENTER)
        self.reg_btn = customtkinter.CTkButton(self.reg_frame, text="Register", width=100, height=40, command=self.register)
        self.reg_btn.place(relx=0.5, rely=0.85, anchor=tkinter.CENTER)
        self.reg_prompt_text = customtkinter.CTkLabel(master=self.reg_frame, text="Already have an account?", font=("Arial", 11))
        self.reg_prompt_text.place(relx=0.65, rely=0.95, anchor=tkinter.CENTER)
        self.go_to_login_label = customtkinter.CTkLabel(
            master=self.reg_frame,
            text="Login",
            font=("Arial", 11),
            text_color=NORMAL_LABEL_COLOR
        )
        self.bind_func_on_label(self.go_to_login_label, self.go_to_login)
        self.go_to_login_label.place(relx=0.9, rely=0.95, anchor=tkinter.CENTER)

        # frame of register success
        self.reg_success_frame = customtkinter.CTkFrame(master=self.app, width=300, height=200)
        self.reg_success_text = customtkinter.CTkLabel(master=self.reg_success_frame, text="Register success!", font=("Arial", 20))
        self.reg_success_text.place(relx=0.5, rely=0.4, anchor=tkinter.CENTER)
        self.go_to_login_btn = customtkinter.CTkButton(master=self.reg_success_frame, text="Back to Login page", command=self.go_to_login)
        self.go_to_login_btn.place(relx=0.5, rely=0.6, anchor=tkinter.CENTER)

        # frame of waiting for connection
        self.waiting_connect_frame = customtkinter.CTkFrame(master=self.app, width=200, height=100)
        self.connect_state_text = customtkinter.CTkLabel(master=self.waiting_connect_frame, text="Connecting...")
        self.connect_state_text.place(relx=0.5, rely=0.35, anchor=tkinter.CENTER)
        self.reconnect_button = customtkinter.CTkButton(master=self.waiting_connect_frame, text="Reconnect", width=70, command=self.reconnect)
        
        # frame of homepage
        self.home_frame = customtkinter.CTkFrame(master=self.app)
        self.logout_btn = customtkinter.CTkButton(master=self.home_frame, text="Logout", command=self.logout)
        self.logout_btn.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)

        # self.frame_dict["waiting"] = self.waiting_connect_frame
        self.frame_dict["home"] = self.home_frame
        self.frame_dict["login"] = self.login_frame
        self.frame_dict["reg_success"] = self.reg_success_frame
        self.frame_dict["register"] = self.reg_frame

        self.waiting_connect_frame.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)

    def bind_func_on_label(self, label: customtkinter.CTkLabel, func: Callable[[], None]):
        # Change cursor on hover
        label.bind("<Enter>", lambda e: label.configure(cursor="hand2", text_color=HOVER_LABEL_COLOR))
        label.bind("<Leave>", lambda e: label.configure(cursor="", text_color=NORMAL_LABEL_COLOR))
        # Change color on press it
        label.bind("<ButtonPress-1>", lambda e: label.configure(text_color=CLICK_LABEL_COLOR))
        label.bind("<ButtonRelease-1>", lambda e: label.configure(text_color=HOVER_LABEL_COLOR))
        label.bind("<Button-1>", lambda e: func())

    
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
        if state == "home":
            f.place(relx=0, rely=0, relwidth=1, relheight=1)
        else:
            f.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)

    def clear_inputbox(self):
        if self.login_username_inputbox.get():
            self.login_username_inputbox.delete(0, "end")
        if self.login_password_inputbox.get():
            self.login_password_inputbox.delete(0, "end")
        if self.reg_username_inputbox.get():
            self.reg_username_inputbox.delete(0, "end")
        if self.reg_password_inputbox.get():
            self.reg_password_inputbox.delete(0, "end")
        if self.reg_confirm_password_inputbox.get():
            self.reg_confirm_password_inputbox.delete(0, "end")

    def go_to_register(self):
        self.clear_inputbox()
        self.login_error_label.configure(text="")
        self.reg_error_label.configure(text="")
        try:
            self.reg_username_inputbox.focus()  # move focus to root
        except Exception:
            pass
        self.update_window_state("register")

    def go_to_login(self):
        self.clear_inputbox()
        self.login_error_label.configure(text="")
        self.reg_error_label.configure(text="")
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

    def logout(self):
        self.logout_btn.configure(state="disabled")
        threading.Thread(target=self.logout_thread).start()

    def logout_thread(self):
        success, params = self.client.try_logout()
        try:
            self.app.after(0, self._on_logout_result_ui, success, params)
        except Exception as e:
            print(f"[ClientWindow] Exception occurred in login_thread: {e}")

    def _on_logout_result_ui(self, success: bool, params: dict):
        if success:
            self.login_username_inputbox.focus()
            self.update_window_state("login")
        else:
            print(f"logout failed. params: {params}")
        self.logout_btn.configure(state="normal")

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
        #     print(f"[ClientWindow] Exception occurred in login: {e}")
        # self.login_btn.configure(state="normal")

    def login_thread(self, username: str, password: str):
        success, params = self.client.try_login(username, password)
        try:
            self.app.after(0, self._on_login_result_ui, success, params)
        except Exception as e:
            print(f"[ClientWindow] Exception occurred in login_thread: {e}")

    def _on_login_result_ui(self, success: bool, params: dict):
        if success:
            self.clear_inputbox()
            self.login_error_label.configure(text="")
            self.app.focus()
            self.update_window_state("home")
        else:
            reason = params.get(Words.ParamKeys.Failure.REASON)
            self.login_error_label.configure(text=reason if reason else "")
            # display message to client
        self.login_btn.configure(state="normal")

    def register(self):
        self.reg_btn.configure(state="disabled")
        username = self.reg_username_inputbox.get()
        password = self.reg_password_inputbox.get()
        confirm_password = self.reg_confirm_password_inputbox.get()
        if password != confirm_password:
            self.reg_error_label.configure(text="Confirm password and password are different.")
            self.reg_btn.configure(state="normal")
            return
        threading.Thread(target=self.reg_thread, args=(username, password)).start()

    def reg_thread(self, username: str, password: str):
        success, params = self.client.try_register(username, password)
        try:
            self.app.after(0, self._on_reg_result_ui, success, params)
        except Exception as e:
            print(f"[ClientWindow] Exception occurred in login_thread: {e}")

    def _on_reg_result_ui(self, success: bool, params: dict):
        if success:
            self.clear_inputbox()
            self.login_username_inputbox.focus()
            self.reg_error_label.configure(text="")
            self.update_window_state("reg_success")
        else:
            reason = params.get(Words.ParamKeys.Failure.REASON)
            self.reg_error_label.configure(text=reason if reason else "")
            # display message to client
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
        
