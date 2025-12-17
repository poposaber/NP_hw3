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
from pathlib import Path
import json
from tkinter import messagebox, simpledialog
import subprocess
import sys
import os

NORMAL_LABEL_COLOR = "#5882ff"
HOVER_LABEL_COLOR = "#295fff"
CLICK_LABEL_COLOR = "#1f4fcc"

GAME_DIR = Path(__file__).resolve().parent / "games"

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

        self.game_name_to_id: dict = {}
        self.game_id_dict: dict = {}
        self.current_room_name: Optional[str] = None
        
        self.store_frame = customtkinter.CTkFrame(master=self.home_frame, corner_radius=0, width=800, height=560)
        customtkinter.CTkLabel(master=self.store_frame, text="store!").place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)
        self.game_list = ObjectList(self.store_frame, width=780, height=560)
        self.game_list.place(relx=0, rely=0)


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
        # list of rooms with actions
        self.rooms_list = ObjectList(self.rooms_frame, width=780, height=520)
        self.rooms_list.place(relx=0, rely=0)

        

        self.invitations_frame = customtkinter.CTkFrame(master=self.lobby_frame, width=800, height=520)
        self.invitations_text = customtkinter.CTkLabel(master=self.invitations_frame, text="invitations: ")
        self.invitations_text.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)
        self.lobby_tabbar = TabBar(self.lobby_frame, self.show_tab)
        self.lobby_tabbar.add_tab("Players", self.players_frame, default=True)
        self.lobby_tabbar.add_tab("Rooms", self.rooms_frame)
        self.lobby_tabbar.add_tab("Invitations", self.invitations_frame)
        self.lobby_tabbar.show("Players")

        self.my_room_frame = customtkinter.CTkFrame(master=self.home_frame, corner_radius=0, width=800, height=560)
        # customtkinter.CTkLabel(master=self.my_room_frame, text="my room!").place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)
        self.create_room_frame = customtkinter.CTkFrame(master=self.my_room_frame, width=250, height=350)
        self.create_room_frame.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)
        self.choose_game_combobox = customtkinter.CTkComboBox(master=self.create_room_frame, values=[""], state="readonly")
        self.choose_game_combobox.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)
        self.room_name_inputbox = customtkinter.CTkEntry(master=self.create_room_frame, placeholder_text="Enter Room Name: ")
        self.room_name_inputbox.place(relx=0.5, rely=0.3, anchor=tkinter.CENTER)
        self.create_room_btn = customtkinter.CTkButton(master=self.create_room_frame, text="Create A Room", command=self.create_room)
        self.create_room_btn.place(relx=0.5, rely=0.7, anchor=tkinter.CENTER)

        self.room_players_list = ObjectList(master=self.my_room_frame, width=800, height=480)
        self.start_game_btn = customtkinter.CTkButton(master=self.my_room_frame, text="Start Game", command=self.start_game, state="disabled")
        self.leave_room_btn = customtkinter.CTkButton(master=self.my_room_frame, text="Leave Room", command=self.leave_room, state="disabled")
        
        # self.start_game_btn.place(relx=0.5, rely=0.9, anchor=tkinter.CENTER)

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

    def _on_login_result_ui(self, success, params):
        super()._on_login_result_ui(success, params)
        if success:
            if self.client.username is not None:
                user_game_dir = GAME_DIR / self.client.username
                user_game_dir.mkdir(parents=True, exist_ok=True)
            self.account_name_label.configure(text=self.client.username)
            self.home_tabbar.show("Store")
            self.update_users_and_rooms()
            self.update_store()

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
                            assert isinstance(player_name, str)
                            try:
                                self.app.after(0, self._handle_player_online_ui, player_name)
                            except Exception:
                                pass
                        case Words.EventName.PLAYER_OFFLINE:
                            param = data.get(Words.DataKeys.PARAMS)
                            assert isinstance(param, dict)
                            player_name = param.get(Words.ParamKeys.PlayerOnline.PLAYER_NAME)
                            assert isinstance(player_name, str)
                            try:
                                self.app.after(0, self._handle_player_offline_ui, player_name)
                            except Exception:
                                pass
                        case Words.EventName.GAME_FETCHED:
                            param = data.get(Words.DataKeys.PARAMS)
                            assert isinstance(param, dict)
                            game_id = param.get(Words.ParamKeys.Metadata.GAME_ID)
                            assert isinstance(game_id, str)
                            try:
                                self.app.after(0, self._handle_game_fetched_ui, game_id)
                            except Exception:
                                pass
                        case Words.EventName.GAME_STARTED:
                            param = data.get(Words.DataKeys.PARAMS)
                            assert isinstance(param, dict)
                            game_id = str(param.get(Words.ParamKeys.Metadata.GAME_ID))
                            room_name = param.get(Words.ParamKeys.Room.ROOM_NAME)
                            try:
                                self.app.after(0, self._handle_game_started_ui, game_id, room_name)
                            except Exception:
                                pass
                        case Words.EventName.ROOM_UPDATED:
                            param = data.get(Words.DataKeys.PARAMS)
                            assert isinstance(param, dict)
                            room_name = param.get(Words.ParamKeys.Room.ROOM_NAME)
                            now_room = param.get(Words.ParamKeys.Room.NOW_ROOM_DATA)
                            try:
                                assert isinstance(now_room, dict)
                                if self.current_room_name and isinstance(room_name, str) and room_name == self.current_room_name:
                                    self.app.after(0, self._on_room_updated_ui, now_room)
                                else:
                                    self.app.after(0, self.update_users_and_rooms)
                            except Exception:
                                self.app.after(0, self.update_users_and_rooms)
                case _:
                    pass
        except Exception as e:
            print(f"[PlayerClientWindow] Exception in _on_recv_message: {e}")

    def _on_logout_result_ui(self, success: bool, params: dict):
        super()._on_logout_result_ui(success, params)
        if success:
            try:
                self.room_players_list.clear()
            except Exception:
                pass
            try:
                self.room_players_list.place_forget()
            except Exception:
                pass
            try:
                self.leave_room_btn.place_forget()
            except Exception:
                pass
            try:
                self.start_game_btn.place_forget()
            except Exception:
                pass
            self.current_room_name = None
            # refresh lobby view
            try:
                self.update_users_and_rooms()
            except Exception:
                pass
            self.create_room_frame.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)

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
                enabled = (u != self.client.username)
                return [("Invite", (lambda: self._invite_user(u)), enabled)]
            self.players_list.set_items([(u, u) for u in players], make_actions)
            # rooms
            rooms = params.get(Words.ParamKeys.LobbyStatus.ROOMS) or {}
            def make_room_actions(r: str):
                enabled = True
                return [("Join", (lambda rr=r: self._on_join_room_clicked(rr)), enabled)]
            room_items = []
            for rn, rd in rooms.items():
                pl = rd.get(Words.ParamKeys.Room.PLAYER_LIST) or []
                exp = rd.get(Words.ParamKeys.Room.EXPECTED_PLAYERS) or 0
                label = f"{rn} ({len(pl)}/{exp if exp else '∞'})"
                room_items.append((rn, label))
            self.rooms_list.set_items(room_items, make_room_actions)
        else:
            self._notify_error("Update failed", f"update failed. Params: {params}")

    def create_room(self):
        room_name = self.room_name_inputbox.get()
        game_id = self.game_name_to_id.get(self.choose_game_combobox.get())
        if not room_name or not game_id:
            return
        threading.Thread(target=self._create_room_thread, args=(room_name, game_id)).start()

    def _on_join_room_clicked(self, room_name: str):
        threading.Thread(target=self._join_room_thread, args=(room_name,)).start()

    def _join_room_thread(self, room_name: str):
        try:
            assert isinstance(self.client, PlayerClient)
            success, params = self.client.try_join_room(room_name)
            self.app.after(0, self._on_join_room_result_ui, room_name, success, params)
        except Exception as e:
            print(f"Exception in _join_room_thread: {e}")

    def _on_join_room_result_ui(self, room_name: str, success: bool, params: dict):
        if success:
            self._notify_info("Join Room", f"Joined room {room_name}.")
            now_room = params.get(Words.ParamKeys.Room.NOW_ROOM_DATA) or {}
            # switch to My Room view and populate players
            self.home_tabbar.show("My Room")
            self.current_room_name = room_name
            self.room_players_list.place(relx=0, rely=0)
            self.room_players_list.clear()
            players = now_room.get(Words.ParamKeys.Room.PLAYER_LIST) or []
            for p in players:
                self.room_players_list.add_item(p, p, [])
            self.start_game_btn.place(relx=0.5, rely=0.9, anchor=tkinter.CENTER)
            self.leave_room_btn.place(relx=0.8, rely=0.9, anchor=tkinter.CENTER)
            try:
                self.leave_room_btn.configure(state="normal")
            except Exception:
                pass
        else:
            self._notify_error("Join Room Failed", f"params: {params}")

    def _create_room_thread(self, room_name: str, game_id: str):
        try:
            assert isinstance(self.client, PlayerClient)
            success, params = self.client.try_create_room(room_name, game_id)
            self.app.after(0, self._on_create_room_result_ui, success, params)
        except Exception as e:
            print(f"Exception in _create_room_thread: {e}")

    def _on_create_room_result_ui(self, success: bool, params: dict):
        if success:
            self._notify_info("Create Room", "Room successfully created.")
            self.create_room_frame.place_forget()
            self.room_players_list.place(relx=0, rely=0)
            # set current room
            try:
                # if params contains room name, use it; else use input
                rn = params.get(Words.ParamKeys.Room.ROOM_NAME) if isinstance(params, dict) else None
                if isinstance(rn, str) and rn:
                    self.current_room_name = rn
                else:
                    self.current_room_name = self.room_name_inputbox.get()
            except Exception:
                self.current_room_name = self.room_name_inputbox.get()
            self.start_game_btn.place(relx=0.5, rely=0.9, anchor=tkinter.CENTER)
            self.leave_room_btn.place(relx=0.8, rely=0.9, anchor=tkinter.CENTER)
            try:
                self.leave_room_btn.configure(state="normal")
            except Exception:
                pass
            self.room_players_list.add_item(self.client.username or "unknown", self.client.username or "unknown", [])
        else:
            self._notify_error("Create Room Failed", f"params: {params}")

    def _on_room_updated_ui(self, now_room: dict):
        try:
            if not now_room or not isinstance(now_room, dict):
                return
            # update room player list safely
            players = now_room.get(Words.ParamKeys.Room.PLAYER_LIST) or []
            # clear and repopulate
            try:
                self.room_players_list.clear()
            except Exception:
                pass
            for p in players:
                try:
                    self.room_players_list.add_item(p, p, [])
                except Exception:
                    pass
            # if no players left, hide my room
            if not players:
                try:
                    self.room_players_list.place_forget()
                    self.current_room_name = None
                    try:
                        self.leave_room_btn.place_forget()
                    except Exception:
                        pass
                    try:
                        self.start_game_btn.place_forget()
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception as e:
            print(f"[PlayerClientWindow] _on_room_updated_ui error: {e}")

    def leave_room(self):
        if not self.current_room_name:
            return
        threading.Thread(target=self._leave_room_thread, args=(self.current_room_name,)).start()

    def _leave_room_thread(self, room_name: str):
        try:
            assert isinstance(self.client, PlayerClient)
            success, params = self.client.try_leave_room(room_name)
            self.app.after(0, self._on_leave_room_result_ui, room_name, success, params)
        except Exception as e:
            print(f"[PlayerClientWindow] Exception in _leave_room_thread: {e}")

    def _on_leave_room_result_ui(self, room_name: str, success: bool, params: dict):
        if success:
            self._notify_info("Leave Room", f"Left room {room_name}.")
            try:
                self.room_players_list.clear()
            except Exception:
                pass
            try:
                self.room_players_list.place_forget()
            except Exception:
                pass
            try:
                self.leave_room_btn.place_forget()
            except Exception:
                pass
            try:
                self.start_game_btn.place_forget()
            except Exception:
                pass
            self.current_room_name = None
            # refresh lobby view
            try:
                self.update_users_and_rooms()
            except Exception:
                pass
            self.create_room_frame.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)
        else:
            self._notify_error("Leave Room Failed", f"params: {params}")

    def _invite_user(self, target_username: str):
        print(f"invite {target_username}")
        # try:
        #     assert isinstance(self.client, PlayerClient)
        #     resp = self.client.worker.pend_and_wait(
        #         Words.MessageType.REQUEST,
        #         {
        #             Words.DataKeys.Request.COMMAND: Words.Command.INVITE,
        #             Words.DataKeys.PARAMS: {
        #                 Words.ParamKeys.Invite.TARGET_USERNAME: target_username
        #             }
        #         },
        #         self.client.server_response_timeout
        #     )
        #     if resp.get(Words.DataKeys.Response.RESULT) == Words.Result.SUCCESS:
        #         print(f"Invite sent to {target_username}")
        #     else:
        #         print(f"Invite failed: {resp.get(Words.DataKeys.PARAMS)}")
        # except Exception as e:
        #     print(f"[PlayerClientWindow] invite error: {e}")

    def _handle_player_online_ui(self, player_name: str):
        try:
            self.players_list.add_item(player_name, player_name, [("Invite", lambda: self._invite_user(player_name), True)])
            print(f"{player_name} just jumped in the lobby server!")
        except Exception:
            pass

    def _handle_player_offline_ui(self, player_name: str):
        try:
            self.players_list.remove_item(player_name)
            print(f"{player_name} left the lobby server.")
        except Exception:
            pass

    def _handle_game_fetched_ui(self, game_id: str):
        try:
            print(f"Game {game_id} has been fetched.")
            self.start_game_btn.configure(state="normal")
        except Exception:
            pass

    def _handle_game_started_ui(self, game_id: str, room_name: str | None):
        try:
            if not game_id:
                return
            # launch local client script for this player
            if not self.client or not self.client.username:
                return
            client_main = GAME_DIR / self.client.username / str(game_id) / "client" / "__main__.py"
            if not client_main.exists():
                cdir = GAME_DIR / self.client.username / str(game_id) / "client"
                if cdir.exists() and cdir.is_dir():
                    for f in cdir.iterdir():
                        if f.suffix == ".py":
                            client_main = f
                            break
            if not client_main.exists():
                print(f"client entry not found for game {game_id}")
                return
            cmd = [sys.executable, str(client_main)]
            kwargs = {"cwd": str(client_main.parent)}
            if os.name == 'nt':
                kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
            else:
                kwargs["start_new_session"] = True
            subprocess.Popen(cmd, **kwargs)
        except Exception as e:
            print(f"[PlayerClientWindow] _handle_game_started_ui error: {e}")

    def show_tab(self, name: str):
        print(f"now tab: {name}")
        if name == "Store":
            self.update_store()
        if name == "Lobby":
            self.update_users_and_rooms()
        if name == "My Room":
            self.scan_games_and_update_dict()
            game_name_list = list(self.game_name_to_id.keys())
            if not game_name_list:
                self.choose_game_combobox.configure(values=[""])
                self.create_room_btn.configure(state="disabled")
            else:
                self.choose_game_combobox.configure(values=list(self.game_name_to_id.keys()))
                self.create_room_btn.configure(state="normal")

    def update_store(self):
        threading.Thread(target=self._update_store_thread).start()

    def _update_store_thread(self):
        try:
            assert isinstance(self.client, PlayerClient)
            success, params = self.client.try_update_store()
            self.app.after(0, self._on_update_store_result_ui, success, params)
        except Exception as e:
            print(f"[PlayerClientWindow] Exception in _update_store_thread: {e}")

    def _on_update_store_result_ui(self, success: bool, params: dict):
        if success:
            # Build rows: key=text=username; disable invite on yourself
            def make_actions(u: str):
                enabled = True
                return [("Download", (lambda: self.download_game(u)), enabled)]
            self.game_list.set_items([(u, params[u][Words.ParamKeys.Metadata.GAME_NAME]) for u in params], make_actions)
        else:
            print(f"update failed. Params: {params}")

    def download_game(self, game_id: str):
        threading.Thread(target=self._download_game_thread, args=(game_id, )).start()

    def _download_game_thread(self, game_id: str):
        try:
            assert isinstance(self.client, PlayerClient)
            success, params = self.client.try_download_game(game_id)
            self.app.after(0, self._on_download_game_result_ui, success, params)
        except Exception as e:
            print(f"[PlayerClientWindow] Exception in _update_store_thread: {e}")

    def _on_download_game_result_ui(self, success: bool, params: dict):
        if success:
            self._notify_info("Download Game", "Game successfully downloaded.")


    def scan_games_and_update_dict(self):
        try:
            assert self.client.username is not None
            user_game_dir = GAME_DIR / self.client.username
            for p in user_game_dir.iterdir():
                if not p.is_dir():
                    continue
                game_id = p.name
                display = game_id
                players = 0
                version = "0.1.0"
                manifest = p / "config.json"
                if manifest.exists():
                    try:
                        with manifest.open("r", encoding="utf-8") as f:
                            m = json.load(f)
                        display = m.get("name") or display
                        version = m.get("version") or version
                        players = m.get("players") or players
                    except Exception:
                        display = game_id
                self.game_name_to_id[display] = game_id
                self.game_id_dict[game_id] = {
                    "name": display, 
                    "version": version, 
                    "players": players
                }
        except Exception as e:
            print(f"[scan_games] error: {e}")

    def start_game(self):
        if not self.current_room_name:
            return
        threading.Thread(target=self._start_game_thread, args=(self.current_room_name,)).start()

    def _start_game_thread(self, room_name: str):
        try:
            assert isinstance(self.client, PlayerClient)
            success, params = self.client.try_start_game(room_name)
            self.app.after(0, self._on_start_game_result_ui, room_name, success, params)
        except Exception as e:
            print(f"[PlayerClientWindow] Exception in _start_game_thread: {e}")

    def _on_start_game_result_ui(self, room_name: str, success: bool, params: dict):
        if not success:
            self._notify_error("Start Game Failed", f"params: {params}")
            return
        # Success response: do not launch client here. Wait for server to broadcast GAME_STARTED event,
        # which will trigger _handle_game_started_ui on each client to launch their local client process.
        self._notify_info("Start Game", "Game start requested. Waiting for server to notify players.")

    def _notify_info(self, caption: str, message: str) -> None:
        def _show():
            try:
                messagebox.showinfo(caption, message, parent=self.app)
            except Exception:
                pass
        try:
            self.app.after(0, _show)
        except Exception:
            _show()

    def _notify_error(self, caption: str, message: str) -> None:
        def _show():
            try:
                messagebox.showerror(caption, message, parent=self.app)
            except Exception:
                pass
        try:
            self.app.after(0, _show)
        except Exception:
            _show()
        
        