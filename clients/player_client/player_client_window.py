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
from ui.object_list import ObjectList

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
                            on_connection_lost=self._on_client_connection_lost, 
                            on_recv_message=self._on_recv_message))
        
        self.app.title("Play 2 Win")
        
        self.store_frame = customtkinter.CTkFrame(master=self.home_frame, corner_radius=0, width=800, height=560)
        customtkinter.CTkLabel(master=self.store_frame, text="store!").place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)

        self.my_games_frame = customtkinter.CTkFrame(master=self.home_frame, corner_radius=0, width=800, height=560)
        customtkinter.CTkLabel(master=self.my_games_frame, text="my games!").place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)

        self.lobby_frame = customtkinter.CTkFrame(master=self.home_frame, corner_radius=0, width=800, height=560)
        customtkinter.CTkLabel(master=self.lobby_frame, text="lobby!").place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)
        # self.players_button = customtkinter.CTkButton(master=self.lobby_frame, text="Players", )
        # self.players_button.place(relx=0, rely=0)

        self.players_frame = customtkinter.CTkFrame(master=self.lobby_frame, width=800, height=520)
        self.players_list = ObjectList(self.players_frame, width=780, height=520)
        self.players_list.place(relx=0, rely=0)
        # self.players_text = customtkinter.CTkLabel(master=self.players_frame, text="players: ")
        # self.players_text.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)

        self.rooms_frame = customtkinter.CTkFrame(master=self.lobby_frame, width=800, height=520)
        customtkinter.CTkLabel(master=self.rooms_frame, text="rooms!").place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)

        self.invitations_frame = customtkinter.CTkFrame(master=self.lobby_frame, width=800, height=520)
        self.invitations_text = customtkinter.CTkLabel(master=self.invitations_frame, text="invitations: ")
        self.invitations_text.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)
        self.lobby_tabbar = TabBar(self.lobby_frame, self.show_tab)
        self.lobby_tabbar.add_tab("Players", self.players_frame, default=True)
        self.lobby_tabbar.add_tab("Rooms", self.rooms_frame)
        self.lobby_tabbar.add_tab("Invitations", self.invitations_frame)
        self.lobby_tabbar.show("Players")

        self.my_room_frame = customtkinter.CTkFrame(master=self.home_frame, corner_radius=0, width=800, height=560)
        customtkinter.CTkLabel(master=self.my_room_frame, text="my room!").place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)

        self.account_frame = customtkinter.CTkFrame(master=self.home_frame, corner_radius=0, width=800, height=560)
        self.account_name_label = customtkinter.CTkLabel(master=self.account_frame, text="", font=("Arial", 25, "bold"))
        self.account_name_label.place(relx=0.1, rely=0.1, anchor=tkinter.CENTER)
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
        self.update_users_and_rooms()

    def _on_login_result_ui(self, success, params):
        super()._on_login_result_ui(success, params)
        if success:
            self.account_name_label.configure(text=self._username)

    def _on_recv_message(self, msg_tuple: tuple[str, str, dict]):
        _, msg_type, data = msg_tuple
        try:
            match msg_type:
                case Words.MessageType.EVENT:
                    event_name = data.get(Words.DataKeys.Event.EVENT_NAME)
                    match event_name:
                        case Words.EventName.PLAYER_ONLINE:
                            param = data.get(Words.DataKeys.PARAMS)
                            assert isinstance(param, dict)
                            player_name = param.get(Words.ParamKeys.PlayerOnline.PLAYER_NAME)
                            self.players_list.add_item(player_name, player_name, [("Invite", lambda: self._invite_user(player_name), True)])
                            print(f"{player_name} just jumped in the lobby server!")
                        case Words.EventName.PLAYER_OFFLINE:
                            param = data.get(Words.DataKeys.PARAMS)
                            assert isinstance(param, dict)
                            player_name = param.get(Words.ParamKeys.PlayerOnline.PLAYER_NAME)
                            self.players_list.remove_item(player_name)
                            print(f"{player_name} left the lobby server.")
        except Exception as e:
            print(f"[PlayerClientWindow] Exception in _on_recv_message: {e}")

    def update_users_and_rooms(self):
        threading.Thread(target=self.update_users_and_rooms_thread).start()

    def update_users_and_rooms_thread(self):
        # if hasattr(self.client, "try_sync_lobby_status"):
        #     success, params = self.client.try_sync_lobby_status()
        # else:
        #     success, params = (False, {"error": "Client does not support try_sync_lobby_status"})
        try:
            assert isinstance(self.client, PlayerClient)
            success, params = self.client.try_sync_lobby_status()
            self.app.after(0, self._on_update_users_and_rooms_result_ui, success, params)
        except Exception as e:
            print(f"[PlayerClientWindow] Exception in update_users_and_rooms_thread: {e}")
        # self.app.after(0, self._on_update_users_and_rooms_result_ui, success, params)

    # def _on_update_users_and_rooms_result_ui(self, success: bool, params: dict):
    #     if success:
    #         players = params.get(Words.ParamKeys.LobbyStatus.ONLINE_PLAYERS)
    #         self.players_text.configure(text=str(players))
    #     else:
    #         print(f"update failed. Params: {params}")

    def _on_update_users_and_rooms_result_ui(self, success: bool, params: dict):
        if success:
            players = params.get(Words.ParamKeys.LobbyStatus.ONLINE_PLAYERS) or []
            # Build rows: key=text=username; disable invite on yourself
            def make_actions(u: str):
                enabled = (u != self._username)
                return [("Invite", (lambda uu=u: self._invite_user(uu)), enabled)]
            self.players_list.set_items([(u, u) for u in players], make_actions)
        else:
            print(f"update failed. Params: {params}")

    def _invite_user(self, target_username: str):
        try:
            assert isinstance(self.client, PlayerClient)
            resp = self.client.worker.pend_and_wait(
                Words.MessageType.REQUEST,
                {
                    Words.DataKeys.Request.COMMAND: Words.Command.INVITE,
                    Words.DataKeys.PARAMS: {
                        Words.ParamKeys.Invite.TARGET_USERNAME: target_username
                    }
                },
                self.client.server_response_timeout
            )
            if resp.get(Words.DataKeys.Response.RESULT) == Words.Result.SUCCESS:
                print(f"Invite sent to {target_username}")
            else:
                print(f"Invite failed: {resp.get(Words.DataKeys.PARAMS)}")
        except Exception as e:
            print(f"[PlayerClientWindow] invite error: {e}")

    def show_tab(self, name: str):
        print(f"now tab: {name}")
        if name == "Lobby":
            self.update_users_and_rooms()
        