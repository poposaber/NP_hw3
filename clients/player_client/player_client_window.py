# next: add heartbeat patience

import customtkinter
import tkinter
import threading
import time
from typing import Optional, Callable
from .player_client import PlayerClient
from protocols.protocols import Words
from clients.client_window_base import ClientWindowBase
from ui.tabbar import TabBar

NORMAL_LABEL_COLOR = "#5882ff"
HOVER_LABEL_COLOR = "#295fff"
CLICK_LABEL_COLOR = "#1f4fcc"

class PlayerClientWindow(ClientWindowBase):
    # LOGIN_TIMEOUT = 5.0
    def __init__(self, host = "127.0.0.1", port = 21354) -> None:
        # GUI 與 client 分離：建立 PlayerClient 實例
        # self.client = PlayerClient(host=host, port=port, 
        #                            on_connection_done=self._on_client_connection_done, 
        #                            on_connection_fail=self._on_client_connection_fail, 
        #                            on_connection_lost=self._on_client_connection_lost)
        super().__init__(host, port, 
                         PlayerClient(host=host, port=port, 
                            on_connection_done=self._on_client_connection_done, 
                            on_connection_fail=self._on_client_connection_fail, 
                            on_connection_lost=self._on_client_connection_lost))
        
        self.app.title("Play 2 Win")
        
        self.store_frame = customtkinter.CTkFrame(master=self.home_frame, corner_radius=0)
        customtkinter.CTkLabel(master=self.store_frame, text="store!").place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)
        self.my_games_frame = customtkinter.CTkFrame(master=self.home_frame, corner_radius=0)
        customtkinter.CTkLabel(master=self.my_games_frame, text="my games!").place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)
        self.lobby_frame = customtkinter.CTkFrame(master=self.home_frame, corner_radius=0)
        customtkinter.CTkLabel(master=self.lobby_frame, text="lobby!").place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)
        self.my_room_frame = customtkinter.CTkFrame(master=self.home_frame, corner_radius=0)
        customtkinter.CTkLabel(master=self.my_room_frame, text="my room!").place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)
        self.account_frame = customtkinter.CTkFrame(master=self.home_frame, corner_radius=0)
        customtkinter.CTkLabel(master=self.account_frame, text="account!").place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)
        self.logout_btn = customtkinter.CTkButton(master=self.account_frame, text="Logout", command=self.logout)
        self.logout_btn.place(relx=0.5, rely=0.8, anchor=tkinter.CENTER)
        self.home_tabbar = TabBar(self.home_frame, self.show_tab)
        self.home_tabbar.add_tab("Store", self.store_frame, default=True)
        self.home_tabbar.add_tab("My Games", self.my_games_frame)
        self.home_tabbar.add_tab("Lobby", self.lobby_frame)
        self.home_tabbar.add_tab("My Room", self.my_room_frame)
        self.home_tabbar.add_tab("Account", self.account_frame)
        self.home_tabbar.show("Store")
        
    def login(self):
        super().login()
        self.home_tabbar.show("Store")

    def show_tab(self, name: str):
        print(f"now tab: {name}")
        