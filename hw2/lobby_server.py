from message_format_passer import MessageFormatPasser
from protocols import Protocols, Words
import threading
import socket
import time
import uuid
import random
from game_server import GameServer

class LobbyServer:
    def __init__(self) -> None:
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = ""
        self.port = 0
        #self.server_sock.bind((host, port))
        #self.server_sock.listen()
        #print(f"Lobby server listening on {host}:{port}")
        # self.clients: list[MessageFormatPasser] = []
        self.connections: list[MessageFormatPasser] = []
        #self.user_infos: dict[MessageFormatPasser, UserInfo] = {}
        self.mfpassers_username: dict[MessageFormatPasser, str | None] = {}
        self.db_server_passer: MessageFormatPasser | None = None
        self.shutdown_event = threading.Event()
        self.pending_db_response_dict: dict[str, tuple[bool, str, dict]] = {}
        """The dict contains all sent db_requests, after processing, received responses will be popped. {request_id: (response_received, result, data)}"""
        self.pending_db_response_lock = threading.Lock()
        self.invitee_inviter_set_pair: set[tuple] = set()  # {(invitee_username, inviter_username)}
        self.invitation_lock = threading.Lock()
        self.game_servers: dict[str, GameServer] = {}  # {room_id: GameServer}
        self.game_server_threads: dict[str, threading.Thread] = {}  # {room_id: Thread}
        self.game_server_win_recorded: dict[str, bool] = {}  # {room_id: bool}
        self.game_server_lock = threading.Lock()
        
        #self.send_to_DB_queue = queue.Queue()
        #self.accept_thread = threading.Thread(target=self.accept_connections, daemon=True)
        #self.accept_thread.start()

    def accept_connections(self) -> None:
        while not self.shutdown_event.is_set():
            try:
                connection_sock, addr = self.server_sock.accept()
                print(f"Accepted connection from {addr}")
                msgfmt_passer = MessageFormatPasser(connection_sock)
                #self.clients.append(msgfmt_passer)
                #self.user_infos[msgfmt_passer] = UserInfo()
                self.connections.append(msgfmt_passer)
                print(f"Active connections: {len(self.connections)}")
                # Since connection may be client, db, or game server, start a thread to handle initial handshake
                threading.Thread(target=self.handle_connections, args=(msgfmt_passer,)).start()
            except socket.timeout:
                continue

    def handle_connections(self, msgfmt_passer: MessageFormatPasser) -> None:
        """Check handshake and pass to corresponding methods."""
        try:
            connection_type, = msgfmt_passer.receive_args(Protocols.ConnectionToLobby.HANDSHAKE)
            if connection_type == Words.ConnectionType.CLIENT:
                self.handle_client(msgfmt_passer)
            elif connection_type == Words.ConnectionType.DATABASE_SERVER:
                self.handle_database_server(msgfmt_passer)
            else:
                print(f"Unknown connection type: {connection_type}")
        except Exception as e:
            print(f"Error during handshake: {e}")

        self.connections.remove(msgfmt_passer)
        print(f"Connection closed. Active connections: {len(self.connections)}")
        msgfmt_passer.close()

    def handle_database_server(self, msgfmt_passer: MessageFormatPasser) -> None:
        if self.db_server_passer is not None:
            print("A database server is already connected. Rejecting new connection.")
            msgfmt_passer.send_args(Protocols.LobbyToConnection.HANDSHAKE_RESPONSE, Words.Result.ERROR, "Database server already connected.")
            return
        self.db_server_passer = msgfmt_passer
        self.db_server_passer.settimeout(2.0)
        print("Database server connected.")
        msgfmt_passer.send_args(Protocols.LobbyToConnection.HANDSHAKE_RESPONSE, Words.Result.CONFIRMED, "Database server connected successfully.")
        while not self.shutdown_event.is_set():
            try:
                response = msgfmt_passer.receive_args(Protocols.DBToLobby.RESPONSE)
                responding_request_id = response[0]
                with self.pending_db_response_lock:
                    self.pending_db_response_dict[responding_request_id] = (True, response[1], response[2])
            except TimeoutError:
                continue
            except Exception as e:
                print(f"Error receiving response from database server: {e}")
                break
        self.db_server_passer = None
        print("Database server disconnected.")

    def manage_game_servers(self) -> None:
        while not self.shutdown_event.is_set():
            cleanup_room_ids = []
            with self.game_server_lock:
                for room_id, game_server in self.game_servers.items():
                    if game_server.game.winner is not None and not self.game_server_win_recorded.get(room_id, False):
                        # Game over, record winner to database
                        winner_username = ""
                        loser_username = ""
                        winner = game_server.game.winner
                        if winner == "player1":
                            winner_username = game_server.player1_username
                            loser_username = game_server.player2_username
                        elif winner == "player2":
                            winner_username = game_server.player2_username
                            loser_username = game_server.player1_username

                        print(f"Game over in room {room_id}. Winner: {winner} ({winner_username})")

                        # record win
                        request_id = str(uuid.uuid4())
                        with self.pending_db_response_lock:
                            self.pending_db_response_dict[request_id] = (False, "", {})
                        self.send_to_database(request_id, Words.Collection.USER, Words.Action.ADD_WIN, {Words.DataParamKey.USERNAME: winner_username})
                        # Wait for response
                        result, _ = self.receive_from_database(request_id)
                        if result == Words.Result.SUCCESS:
                            print(f"Recorded win for winner {winner_username} successfully.")
                        else:
                            print(f"Failed to record win for winner {winner_username}.")

                        # record game played for loser
                        request_id = str(uuid.uuid4())
                        with self.pending_db_response_lock:
                            self.pending_db_response_dict[request_id] = (False, "", {})
                        self.send_to_database(request_id, Words.Collection.USER, Words.Action.ADD_GAME_PLAYED, {Words.DataParamKey.USERNAME: loser_username})
                        # Wait for response
                        result, _ = self.receive_from_database(request_id)
                        if result == Words.Result.SUCCESS:
                            print(f"Recorded game result for {loser_username} successfully.")
                        else:
                            print(f"Failed to record game result for {loser_username}.")

                        
                        

                        self.game_server_win_recorded[room_id] = True
                    
                    if not game_server.running.is_set():
                        # set is_playing to False for room
                        request_id = str(uuid.uuid4())
                        with self.pending_db_response_lock:
                            self.pending_db_response_dict[request_id] = (False, "", {})
                        self.send_to_database(request_id, Words.Collection.ROOM, Words.Action.UPDATE, {Words.DataParamKey.ROOM_ID: room_id, Words.DataParamKey.IS_PLAYING: False})
                        # wait for response
                        result, _ = self.receive_from_database(request_id)
                        if result == Words.Result.SUCCESS:
                            print(f"Set is_playing to False for room {room_id} successfully.")
                        # Game server has stopped, clean up
                        print(f"Cleaning up game server for room {room_id}.")
                        if room_id in self.game_server_threads:
                            self.game_server_threads[room_id].join()
                            del self.game_server_threads[room_id]
                        #del self.game_servers[room_id]
                        cleanup_room_ids.append(room_id)
                        if room_id in self.game_server_win_recorded:
                            del self.game_server_win_recorded[room_id]
                        print(f"Game server for room {room_id} cleaned up.")
                for room_id in cleanup_room_ids:
                    if room_id in self.game_servers:
                        del self.game_servers[room_id]
                    
            time.sleep(1)

    def handle_client(self, msgfmt_passer: MessageFormatPasser) -> None:
        #self.user_infos[msgfmt_passer] = UserInfo()
        self.mfpassers_username[msgfmt_passer] = None
        msgfmt_passer.send_args(Protocols.LobbyToConnection.HANDSHAKE_RESPONSE, Words.Result.CONFIRMED, Words.Message.WELCOME_USER)
        msgfmt_passer.settimeout(2.0)
        while not self.shutdown_event.is_set():
            try:
                msg = msgfmt_passer.receive_args(Protocols.ClientToLobby.COMMAND)
                result = self.process_message(msg, msgfmt_passer)
                if result == -1:
                    break
            except TimeoutError:
                continue
            except Exception as e:
                print(f"Error handling client {msgfmt_passer}: {e}")
                self.db_set_offline_by_mfpasser(msgfmt_passer)
                break

        if self.shutdown_event.is_set():
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.EVENT, "", Words.EventType.SERVER_SHUTDOWN, "", {})
            exit_msg = msgfmt_passer.receive_args(Protocols.ClientToLobby.COMMAND)[0]
            if exit_msg != Words.Command.EXIT:
                print(f"Expected EXIT command, got: {exit_msg}")

        del self.mfpassers_username[msgfmt_passer]
            
        #self.remove_client(msgfmt_passer)

    def process_message(self, msg: list, msgfmt_passer: MessageFormatPasser) -> int:
        command, params = msg
        print(f"Received command: {command} with params: {params}")
        # Here you would add logic to process different commands
        match command:
            case Words.Command.EXIT:
                self.help_exit(msgfmt_passer)
                return -1
            case Words.Command.LOGIN:
                self.help_login(params, msgfmt_passer)
            case Words.Command.LOGOUT:
                self.help_logout(msgfmt_passer)
            case Words.Command.CHECK_USERNAME:
                self.help_check_username(params, msgfmt_passer)
            case Words.Command.CHECK_JOINABLE_ROOMS:
                self.help_check_joinable_rooms(params, msgfmt_passer)
            case Words.Command.CHECK_SPECTATABLE_ROOMS:
                self.help_check_spectatable_rooms(params, msgfmt_passer)
            case Words.Command.CHECK_ONLINE_USERS:
                self.help_check_online_users(params, msgfmt_passer)
            case Words.Command.REGISTER:
                self.help_register(params, msgfmt_passer)
            case Words.Command.CREATE_ROOM:
                self.help_create_room(params, msgfmt_passer)
            case Words.Command.DISBAND_ROOM:
                self.help_disband_room(params, msgfmt_passer)
            case Words.Command.LEAVE_ROOM:
                self.help_leave_room(params, msgfmt_passer)
            case Words.Command.JOIN_ROOM:
                self.help_join_room(params, msgfmt_passer)
            case Words.Command.SPECTATE_ROOM:
                self.help_spectate_room(params, msgfmt_passer)
            case Words.Command.INVITE_USER:
                self.help_invite_user(params, msgfmt_passer)
            case Words.Command.ACCEPT_INVITE:
                self.help_accept_invite(params, msgfmt_passer)
            case Words.Command.START_GAME:
                self.help_start_game(params, msgfmt_passer)
            case _:
                msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, command, "", Words.Result.INVALID, {})
        return 0
    
    def db_set_offline_by_mfpasser(self, msgfmt_passer: MessageFormatPasser) -> None:
        username = self.mfpassers_username.get(msgfmt_passer)
        if username is not None:
            # Query user info from database to see if in a room
            request_id = str(uuid.uuid4())
            with self.pending_db_response_lock:
                self.pending_db_response_dict[request_id] = (False, "", {})
            self.send_to_database(request_id, Words.Collection.USER, Words.Action.QUERY, {Words.DataParamKey.USERNAME: username})
            # If user is in a room, leave the room first
            query_result, query_data = self.receive_from_database(request_id)
            if query_result == Words.Result.FOUND:
                current_room_id = query_data.get("current_room_id")
                if current_room_id is not None:
                    # Leave room
                    request_id = str(uuid.uuid4())
                    with self.pending_db_response_lock:
                        self.pending_db_response_dict[request_id] = (False, "", {})
                    self.send_to_database(request_id, Words.Collection.ROOM, Words.Action.REMOVE_USER, {Words.DataParamKey.ROOM_ID: current_room_id, Words.DataParamKey.USERNAME: username})
                    # wait for response
                    result, data = self.receive_from_database(request_id)
                    # notify other users in the room
                    if result == Words.Result.SUCCESS:
                        now_room_info = data.get(Words.DataParamKey.NOW_ROOM_INFO, {})
                        for user in now_room_info.get("users", []):
                            for passer, usname in self.mfpassers_username.items():
                                if usname == user and passer != msgfmt_passer:
                                    passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.EVENT, "", Words.EventType.USER_LEFT, "", {Words.DataParamKey.USERNAME: self.mfpassers_username[msgfmt_passer], Words.DataParamKey.NOW_ROOM_INFO: now_room_info})
                    # also notify spectators
                    for spectator in now_room_info.get("spectators", []):
                        for passer, usname in self.mfpassers_username.items():
                            if usname == spectator and passer != msgfmt_passer:
                                passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.EVENT, "", Words.EventType.USER_LEFT, "", {Words.DataParamKey.USERNAME: self.mfpassers_username[msgfmt_passer], Words.DataParamKey.NOW_ROOM_INFO: now_room_info})
                            

            request_id = str(uuid.uuid4())
            with self.pending_db_response_lock:
                self.pending_db_response_dict[request_id] = (False, "", {})
            self.send_to_database(request_id, Words.Collection.USER, Words.Action.UPDATE, {Words.DataParamKey.USERNAME: username, "online": False, "current_room_id": None})
            # wait for response
            self.receive_from_database(request_id)
        # username = self.mfpassers_username.get(msgfmt_passer)
        # # if user is logged in, set offline in database
        # if username is not None:
        #     request_id = str(uuid.uuid4())
        #     with self.pending_db_response_lock:
        #         self.pending_db_response_dict[request_id] = (False, "", {})
        #     self.send_to_database(request_id, Words.Collection.USER, Words.Action.UPDATE, {Words.DataParamKey.USERNAME: username, "online": False})
        #     # Wait for update response
        #     update_result, _ = self.receive_from_database(request_id)
        #     if update_result != Words.Result.SUCCESS:
        #         print(f"Warning: Failed to update user online status for {username}")
    
    def help_exit(self, msgfmt_passer: MessageFormatPasser) -> None:
        self.db_set_offline_by_mfpasser(msgfmt_passer)

    def help_login(self, params: dict, msgfmt_passer: MessageFormatPasser) -> None:
        if self.db_server_passer is None:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.LOGIN, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "No database server connected."})
            return
        
        username = params.get(Words.DataParamKey.USERNAME)
        password = params.get(Words.DataParamKey.PASSWORD)
        # Send request to database server to verify user
        
        # Wait for response from database server
        try:
            request_id = str(uuid.uuid4())
            with self.pending_db_response_lock:
                self.pending_db_response_dict[request_id] = (False, "", {})
            self.send_to_database(request_id, Words.Collection.USER, Words.Action.QUERY, {Words.DataParamKey.USERNAME: username})
            # Wait for response
            query_result, query_data = self.receive_from_database(request_id)

            if query_result != Words.Result.FOUND:
                print(f"User {username} not found in database.")
                msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.LOGIN, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "Incorrect username or password."})
                return

            user_info = query_data

            if user_info.get(Words.DataParamKey.PASSWORD) != password:
                print(f"Incorrect password for user {username}.")
                msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.LOGIN, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "Incorrect username or password."})
                return
            
            if user_info.get("online") == True:
                print(f"User {username} is already logged in elsewhere.")
                msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.LOGIN, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "User already logged in elsewhere."})
                return

            request_id = str(uuid.uuid4())
            with self.pending_db_response_lock:
                self.pending_db_response_dict[request_id] = (False, "", {})
            self.send_to_database(request_id, Words.Collection.USER, Words.Action.UPDATE, {Words.DataParamKey.USERNAME: username, "online": True})
            # Wait for update response
            update_result, _ = self.receive_from_database(request_id)
            if update_result != Words.Result.SUCCESS:
                print(f"Warning: Failed to update user online status for {username}")
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.LOGIN, "", Words.Result.SUCCESS, {Words.DataParamKey.MESSAGE: "Login successful."})
            self.mfpassers_username[msgfmt_passer] = username
            #self.user_infos[msgfmt_passer].name = username
                            
        except Exception as e:
            print(f"Error receiving response from database server: {e}")
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.LOGIN, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "Database error."})
    
    def help_check_username(self, params: dict, msgfmt_passer: MessageFormatPasser) -> None:
        username = params.get(Words.DataParamKey.USERNAME)
        # Wait for response from database server
        if self.db_server_passer is not None:
            try:
                request_id = str(uuid.uuid4())
                with self.pending_db_response_lock:
                    self.pending_db_response_dict[request_id] = (False, "", {})
                self.send_to_database(request_id, Words.Collection.USER, Words.Action.QUERY, {Words.DataParamKey.USERNAME: username})
                # Wait for response
                result, _ = self.receive_from_database(request_id)
                if result == Words.Result.FOUND:
                    msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.CHECK_USERNAME, "", Words.Result.INVALID, {Words.DataParamKey.MESSAGE: "Username already taken."})
                elif result == Words.Result.NOT_FOUND:
                    msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.CHECK_USERNAME, "", Words.Result.VALID, {Words.DataParamKey.MESSAGE: "Username is available."})
                else:
                    msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.CHECK_USERNAME, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "Database error."})
            except Exception as e:
                print(f"Error receiving response from database server: {e}")
                msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.CHECK_USERNAME, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "Database error."})
        else:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.CHECK_USERNAME, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "No database server connected."})
    
    def help_check_online_users(self, params: dict, msgfmt_passer: MessageFormatPasser) -> None:
        if self.db_server_passer is None:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.CHECK_ONLINE_USERS, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "No database server connected."})
            return
        request_id = str(uuid.uuid4())
        with self.pending_db_response_lock:
            self.pending_db_response_dict[request_id] = (False, "", {})
        self.send_to_database(request_id, Words.Collection.USER, Words.Action.QUERY, {"online": True, "current_room_id": None})
        # Wait for response
        result, data = self.receive_from_database(request_id)
        if result == Words.Result.FOUND:
            online_users = list(data.keys())
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.CHECK_ONLINE_USERS, "", Words.Result.SUCCESS, {Words.DataParamKey.USERS: online_users})
        elif result == Words.Result.NOT_FOUND:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.CHECK_ONLINE_USERS, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "No online users found."})
        else:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.CHECK_ONLINE_USERS, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "Database error."})
    
    def help_register(self, params: dict, msgfmt_passer: MessageFormatPasser) -> None:
        username = params.get(Words.DataParamKey.USERNAME)
        password = params.get(Words.DataParamKey.PASSWORD)    

        # Wait for response from database server
        if self.db_server_passer is not None:
            try:
                request_id = str(uuid.uuid4())
                with self.pending_db_response_lock:
                    self.pending_db_response_dict[request_id] = (False, "", {})
                self.send_to_database(request_id, Words.Collection.USER, Words.Action.CREATE, {Words.DataParamKey.USERNAME: username, Words.DataParamKey.PASSWORD: password})
                # Wait for response
                result, _ = self.receive_from_database(request_id)
                if result == Words.Result.SUCCESS:
                    msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.REGISTER, "", Words.Result.SUCCESS, {Words.DataParamKey.MESSAGE: "Registration successful."})
                elif result == Words.Result.FAILURE:
                    msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.REGISTER, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "Username already taken."})
                else:
                    msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.REGISTER, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "Database error."})
            except Exception as e:
                print(f"Error receiving response from database server: {e}")
                msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.REGISTER, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "Database error."})
        else:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.REGISTER, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "No database server connected."})

    def help_logout(self, msgfmt_passer: MessageFormatPasser) -> None:
        if self.db_server_passer is None:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.LOGOUT, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "No database server connected."})
            return
        self.db_set_offline_by_mfpasser(msgfmt_passer)
        self.mfpassers_username[msgfmt_passer] = None
        msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.LOGOUT, "", Words.Result.SUCCESS, {Words.DataParamKey.MESSAGE: "Logout successful."})

    def help_create_room(self, params: dict, msgfmt_passer: MessageFormatPasser) -> None:
        if self.db_server_passer is None:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.CREATE_ROOM, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "No database server connected."})
            return
        if self.mfpassers_username.get(msgfmt_passer) is None:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.CREATE_ROOM, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "User not logged in."})
            return
        request_id = str(uuid.uuid4())
        with self.pending_db_response_lock:
            self.pending_db_response_dict[request_id] = (False, "", {})
        self.send_to_database(request_id, Words.Collection.ROOM, Words.Action.CREATE, {"owner": self.mfpassers_username[msgfmt_passer], "settings": params})
        # Wait for response
        result, data = self.receive_from_database(request_id)
        if result == Words.Result.SUCCESS:
            room_id = data.get(Words.DataParamKey.ROOM_ID)
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.CREATE_ROOM, "", Words.Result.SUCCESS, {Words.DataParamKey.MESSAGE: "Room created successfully.", Words.DataParamKey.ROOM_ID: room_id})
        elif result == Words.Result.FAILURE:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.CREATE_ROOM, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "Failed to create room."})
        else:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.CREATE_ROOM, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "Database error."})

    def help_leave_room(self, params: dict, msgfmt_passer: MessageFormatPasser) -> None:
        if self.db_server_passer is None:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.LEAVE_ROOM, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "No database server connected."})
            return
        if self.mfpassers_username.get(msgfmt_passer) is None:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.LEAVE_ROOM, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "User not logged in."})
            return
        request_id = str(uuid.uuid4())
        with self.pending_db_response_lock:
            self.pending_db_response_dict[request_id] = (False, "", {})
        self.send_to_database(request_id, Words.Collection.ROOM, Words.Action.REMOVE_USER, {Words.DataParamKey.ROOM_ID: params.get(Words.DataParamKey.ROOM_ID), Words.DataParamKey.USERNAME: self.mfpassers_username[msgfmt_passer]})
        # Wait for response
        result, data = self.receive_from_database(request_id)
        now_room_info = data.get(Words.DataParamKey.NOW_ROOM_INFO, {})
        # if user was room owner, send to other users about new owner as an event
        if result == Words.Result.SUCCESS:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.LEAVE_ROOM, "", Words.Result.SUCCESS, {Words.DataParamKey.MESSAGE: "Left room successfully."})
            for user in now_room_info.get("users", []):
                for passer, username in self.mfpassers_username.items():
                    if username == user and passer != msgfmt_passer:
                        passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.EVENT, "", Words.EventType.USER_LEFT, "", {Words.DataParamKey.USERNAME: self.mfpassers_username[msgfmt_passer], Words.DataParamKey.NOW_ROOM_INFO: now_room_info})
            for spectator in now_room_info.get("spectators", []):
                for passer, username in self.mfpassers_username.items():
                    if username == spectator and passer != msgfmt_passer:
                        passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.EVENT, "", Words.EventType.USER_LEFT, "", {Words.DataParamKey.USERNAME: self.mfpassers_username[msgfmt_passer], Words.DataParamKey.NOW_ROOM_INFO: now_room_info})
        elif result == Words.Result.FAILURE:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.LEAVE_ROOM, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "Failed to leave room."})
        else:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.LEAVE_ROOM, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "Database error."})

    def help_disband_room(self, params: dict, msgfmt_passer: MessageFormatPasser) -> None:
        pass

    def help_invite_user(self, params: dict, msgfmt_passer: MessageFormatPasser) -> None:
        if self.db_server_passer is None:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.INVITE_USER, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "No database server connected."})
            return
        request_id = str(uuid.uuid4())
        with self.pending_db_response_lock:
            self.pending_db_response_dict[request_id] = (False, "", {})
        self.send_to_database(request_id, Words.Collection.USER, Words.Action.QUERY, {Words.DataParamKey.USERNAME: params.get(Words.DataParamKey.USERNAME)})
        # Wait for response
        result, data = self.receive_from_database(request_id)
        if result == Words.Result.FOUND:
            if data.get("online") == True and data.get("current_room_id") is None:
                # Find the corresponding msgfmt_passer
                invited_username = params.get(Words.DataParamKey.USERNAME)
                for passer, username in self.mfpassers_username.items():
                    if username == invited_username:
                        passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.EVENT, "", Words.EventType.INVITATION_RECEIVED, "", {Words.DataParamKey.USERNAME: self.mfpassers_username[msgfmt_passer]})
                        with self.invitation_lock:
                            self.invitee_inviter_set_pair.add((invited_username, self.mfpassers_username[msgfmt_passer]))
                        msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.INVITE_USER, "", Words.Result.SUCCESS, {Words.DataParamKey.MESSAGE: "Invitation sent successfully."})
                        return
                msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.INVITE_USER, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "Invited user not found among connected clients."})
        
    def help_accept_invite(self, params: dict, msgfmt_passer: MessageFormatPasser) -> None:
        if self.db_server_passer is None:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.ACCEPT_INVITE, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "No database server connected."})
            return
        inviter_username = params.get(Words.DataParamKey.USERNAME)
        invitee_username = self.mfpassers_username.get(msgfmt_passer)
        if invitee_username is None:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.ACCEPT_INVITE, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "User not logged in."})
            return
        with self.invitation_lock:
            if (invitee_username, inviter_username) not in self.invitee_inviter_set_pair:
                msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.ACCEPT_INVITE, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "No invitation found from this user."})
                return
            self.invitee_inviter_set_pair.remove((invitee_username, inviter_username))
        # Send join room request on behalf of invitee
        request_id = str(uuid.uuid4())
        with self.pending_db_response_lock:
            self.pending_db_response_dict[request_id] = (False, "", {})
        self.send_to_database(request_id, Words.Collection.ROOM, Words.Action.ADD_USER, {Words.DataParamKey.INVITEE_USERNAME: invitee_username, Words.DataParamKey.INVITER_USERNAME: inviter_username})
        # Wait for response
        result, data = self.receive_from_database(request_id)
        now_room_info = data.get(Words.DataParamKey.NOW_ROOM_INFO, {})
        room_id = data.get(Words.DataParamKey.ROOM_ID, None)
        if result == Words.Result.SUCCESS:
            with self.invitation_lock:
                for invitee, inviter in list(self.invitee_inviter_set_pair):
                    if invitee == invitee_username:
                        self.invitee_inviter_set_pair.remove((invitee, inviter))
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.ACCEPT_INVITE, "", Words.Result.SUCCESS, {Words.DataParamKey.MESSAGE: "Joined room successfully.", Words.DataParamKey.ROOM_ID: room_id, Words.DataParamKey.NOW_ROOM_INFO: now_room_info})
            for user in now_room_info.get("users", []):
                for passer, username in self.mfpassers_username.items():
                    if username == user and passer != msgfmt_passer:
                        passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.EVENT, "", Words.EventType.USER_JOINED, "", {Words.DataParamKey.USERNAME: invitee_username, Words.DataParamKey.NOW_ROOM_INFO: now_room_info})
        elif result == Words.Result.FAILURE:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.ACCEPT_INVITE, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: data.get(Words.DataParamKey.MESSAGE, "Failed to join room.")})
        else:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.ACCEPT_INVITE, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "Database error."})

    def help_check_joinable_rooms(self, params: dict, msgfmt_passer: MessageFormatPasser) -> None:
        if self.db_server_passer is None:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.CHECK_JOINABLE_ROOMS, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "No database server connected."})
            return
        request_id = str(uuid.uuid4())
        with self.pending_db_response_lock:
            self.pending_db_response_dict[request_id] = (False, "", {})
        self.send_to_database(request_id, Words.Collection.ROOM, Words.Action.QUERY, {})
        # Wait for response
        result, data = self.receive_from_database(request_id)
        if result == Words.Result.FOUND:
            joinable_rooms = {room_id: room_info for room_id, room_info in data.items() if len(room_info.get("users", [])) < 2 and room_info.get("settings", {}).get(Words.DataParamKey.PRIVACY) == "public"}
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.CHECK_JOINABLE_ROOMS, "", Words.Result.SUCCESS, joinable_rooms)
        elif result == Words.Result.NOT_FOUND:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.CHECK_JOINABLE_ROOMS, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "Failed to retrieve joinable rooms."})
        else:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.CHECK_JOINABLE_ROOMS, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "Database error."})

    def help_check_spectatable_rooms(self, params: dict, msgfmt_passer: MessageFormatPasser) -> None:
        if self.db_server_passer is None:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.CHECK_SPECTATABLE_ROOMS, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "No database server connected."})
            return
        request_id = str(uuid.uuid4())
        with self.pending_db_response_lock:
            self.pending_db_response_dict[request_id] = (False, "", {})
        self.send_to_database(request_id, Words.Collection.ROOM, Words.Action.QUERY, {})
        # Wait for response
        result, data = self.receive_from_database(request_id)
        if result == Words.Result.FOUND:
            spectatable_rooms = {room_id: room_info for room_id, room_info in data.items() if room_info.get("settings", {}).get(Words.DataParamKey.PRIVACY) == "public" and room_info.get("is_playing") == False}
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.CHECK_SPECTATABLE_ROOMS, "", Words.Result.SUCCESS, spectatable_rooms)
        elif result == Words.Result.NOT_FOUND:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.CHECK_SPECTATABLE_ROOMS, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "Failed to retrieve spectatable rooms."})
        else:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.CHECK_SPECTATABLE_ROOMS, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "Database error."})

    def help_join_room(self, params: dict, msgfmt_passer: MessageFormatPasser) -> None:
        if self.db_server_passer is None:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.JOIN_ROOM, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "No database server connected."})
            return
        if self.mfpassers_username.get(msgfmt_passer) is None:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.JOIN_ROOM, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "User not logged in."})
            return
        request_id = str(uuid.uuid4())
        with self.pending_db_response_lock:
            self.pending_db_response_dict[request_id] = (False, "", {})
        self.send_to_database(request_id, Words.Collection.ROOM, Words.Action.ADD_USER, {Words.DataParamKey.ROOM_ID: params.get(Words.DataParamKey.ROOM_ID), Words.DataParamKey.USERNAME: self.mfpassers_username[msgfmt_passer]})
        # Wait for response
        result, data = self.receive_from_database(request_id)
        now_room_info = data.get(Words.DataParamKey.NOW_ROOM_INFO, {})
        if result == Words.Result.SUCCESS:
            with self.invitation_lock:
                for invitee, inviter in list(self.invitee_inviter_set_pair):
                    if invitee == self.mfpassers_username[msgfmt_passer]:
                        self.invitee_inviter_set_pair.remove((invitee, inviter))
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.JOIN_ROOM, "", Words.Result.SUCCESS, {Words.DataParamKey.MESSAGE: "Joined room successfully.", Words.DataParamKey.NOW_ROOM_INFO: now_room_info})
            for user in now_room_info.get("users", []):
                for passer, username in self.mfpassers_username.items():
                    if username == user and passer != msgfmt_passer:
                        passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.EVENT, "", Words.EventType.USER_JOINED, "", {Words.DataParamKey.USERNAME: self.mfpassers_username[msgfmt_passer], Words.DataParamKey.NOW_ROOM_INFO: now_room_info})
            for spectator in now_room_info.get("spectators", []):
                for passer, username in self.mfpassers_username.items():
                    if username == spectator and passer != msgfmt_passer:
                        passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.EVENT, "", Words.EventType.USER_JOINED, "", {Words.DataParamKey.USERNAME: self.mfpassers_username[msgfmt_passer], Words.DataParamKey.NOW_ROOM_INFO: now_room_info})
        elif result == Words.Result.FAILURE:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.JOIN_ROOM, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "Failed to join room."})
        else:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.JOIN_ROOM, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "Database error."})

    def help_spectate_room(self, params: dict, msgfmt_passer: MessageFormatPasser) -> None:
        if self.db_server_passer is None:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.SPECTATE_ROOM, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "No database server connected."})
            return
        if self.mfpassers_username.get(msgfmt_passer) is None:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.SPECTATE_ROOM, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "User not logged in."})
            return
        request_id = str(uuid.uuid4())
        with self.pending_db_response_lock:
            self.pending_db_response_dict[request_id] = (False, "", {})
        self.send_to_database(request_id, Words.Collection.ROOM, Words.Action.ADD_SPECTATOR, {Words.DataParamKey.ROOM_ID: params.get(Words.DataParamKey.ROOM_ID), Words.DataParamKey.USERNAME: self.mfpassers_username[msgfmt_passer]})
        # Wait for response
        result, data = self.receive_from_database(request_id)
        now_room_info = data.get(Words.DataParamKey.NOW_ROOM_INFO, {})
        if result == Words.Result.SUCCESS:
            with self.invitation_lock:
                for invitee, inviter in list(self.invitee_inviter_set_pair):
                    if invitee == self.mfpassers_username[msgfmt_passer]:
                        self.invitee_inviter_set_pair.remove((invitee, inviter))
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.SPECTATE_ROOM, "", Words.Result.SUCCESS, {Words.DataParamKey.MESSAGE: "Spectating room successfully.", Words.DataParamKey.NOW_ROOM_INFO: now_room_info})
            for user in now_room_info.get("users", []):
                for passer, username in self.mfpassers_username.items():
                    if username == user and passer != msgfmt_passer:
                        passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.EVENT, "", Words.EventType.USER_JOINED, "", {Words.DataParamKey.USERNAME: self.mfpassers_username[msgfmt_passer], Words.DataParamKey.NOW_ROOM_INFO: now_room_info})
            for spectator in now_room_info.get("spectators", []):
                for passer, username in self.mfpassers_username.items():
                    if username == spectator and passer != msgfmt_passer:
                        passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.EVENT, "", Words.EventType.USER_JOINED, "", {Words.DataParamKey.USERNAME: self.mfpassers_username[msgfmt_passer], Words.DataParamKey.NOW_ROOM_INFO: now_room_info})
        elif result == Words.Result.FAILURE:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.SPECTATE_ROOM, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "Failed to spectate room."})
        else:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.SPECTATE_ROOM, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "Database error."})

    def help_start_game(self, params: dict, msgfmt_passer: MessageFormatPasser) -> None:
        if self.db_server_passer is None:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.START_GAME, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "No database server connected."})
            return
        if self.mfpassers_username.get(msgfmt_passer) is None:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.START_GAME, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "User not logged in."})
            return
        request_id = str(uuid.uuid4())
        with self.pending_db_response_lock:
            self.pending_db_response_dict[request_id] = (False, "", {})
        self.send_to_database(request_id, Words.Collection.USER, Words.Action.QUERY, {Words.DataParamKey.USERNAME: self.mfpassers_username[msgfmt_passer]})
        # Wait for response
        result, data = self.receive_from_database(request_id)
        if result == Words.Result.FOUND:
            current_room_id = data.get("current_room_id")
            if current_room_id is None:
                msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.START_GAME, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "User not in a room."})
                return
            
            

            
            # Notify game server to start game
            request_id = str(uuid.uuid4())
            with self.pending_db_response_lock:
                self.pending_db_response_dict[request_id] = (False, "", {})
            self.send_to_database(request_id, Words.Collection.ROOM, Words.Action.QUERY, {Words.DataParamKey.ROOM_ID: current_room_id})
            # Wait for response
            result, data = self.receive_from_database(request_id)
            if result != Words.Result.FOUND:
                msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.START_GAME, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "Room not found."})
                return
            owner = data.get(Words.DataParamKey.OWNER)
            if owner != self.mfpassers_username[msgfmt_passer]:
                msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.START_GAME, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "Only the room owner can start the game."})
                return
            
            # if player < 2, cannot start game
            users = data.get(Words.DataParamKey.USERS, [])
            if len(users) < 2:
                msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.START_GAME, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "Not enough players to start the game."})
                return
            # Here you would add logic to notify the game server to start the game
            # attempt to start a new game server for the room by tuning port numbers
            offset = 0
            started = False
            while True:
                try:
                    with self.game_server_lock:
                        self.game_servers[current_room_id] = GameServer("0.0.0.0", 30000 + offset)
                        #self.game_servers[current_room_id].start()
                        self.game_server_threads[current_room_id] = threading.Thread(target=self.game_servers[current_room_id].start)
                        self.game_server_threads[current_room_id].start()
                        started = True
                        self.game_server_win_recorded[current_room_id] = False
                        self.game_servers[current_room_id].wait_until_started()
                    time.sleep(0.5)  # Give some time for the server to start
                    break
                except OSError as e:
                    print(f"Port {30000 + offset} in use, trying next port.")
                    offset += 1
                except Exception as e:
                    print(f"Error starting game server for room {current_room_id}: {e}")
                    break

            if not started:
                msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.START_GAME, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "Failed to start game server."})
                return

            request_id = str(uuid.uuid4())
            with self.pending_db_response_lock:
                self.pending_db_response_dict[request_id] = (False, "", {})
            self.send_to_database(request_id, Words.Collection.ROOM, Words.Action.UPDATE, {Words.DataParamKey.ROOM_ID: current_room_id, Words.DataParamKey.IS_PLAYING: True})
            # Wait for response
            result, _ = self.receive_from_database(request_id)
            if result != Words.Result.SUCCESS:
                print(f"Warning: Failed to update room playing status for room {current_room_id}")

            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.START_GAME, "", Words.Result.SUCCESS, {Words.DataParamKey.MESSAGE: "Game started successfully."})
            
            for user in data.get(Words.DataParamKey.USERS, []):
                for passer, username in self.mfpassers_username.items():
                    if username == user:
                        with self.game_server_lock:
                            passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.EVENT, "", Words.EventType.CONNECT_TO_GAME_SERVER, "", {Words.DataParamKey.PORT: self.game_servers[current_room_id].port})
            for spectator in data.get(Words.DataParamKey.SPECTATORS, []):
                for passer, username in self.mfpassers_username.items():
                    if username == spectator:
                        with self.game_server_lock:
                            passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.EVENT, "", Words.EventType.CONNECT_TO_GAME_SERVER_AS_SPECTATOR, "", {Words.DataParamKey.PORT: self.game_servers[current_room_id].port})
        elif result == Words.Result.NOT_FOUND:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.START_GAME, "", Words.Result.FAILURE, {Words.DataParamKey.MESSAGE: "User not found."})
        else:
            msgfmt_passer.send_args(Protocols.LobbyToClient.MESSAGE, Words.MessageType.RESPONSE, Words.Command.START_GAME, "", Words.Result.ERROR, {Words.DataParamKey.MESSAGE: "Database error."})
    #def remove_client(self, msgfmt_passer: MessageFormatPasser) -> None:
        #self.clients.remove(msgfmt_passer)
        #del self.user_infos[msgfmt_passer]

    def send_to_database(self, request_id: str, collection: str, action: str, data: dict) -> None:
        if self.db_server_passer is not None:
            self.db_server_passer.send_args(Protocols.LobbyToDB.REQUEST, request_id, collection, action, data)

    def receive_from_database(self, request_id: str) -> tuple[str, dict]:
        while True:
            time.sleep(random.uniform(0.1, 0.3))  # Avoid busy waiting
            with self.pending_db_response_lock:
                if request_id in self.pending_db_response_dict:
                    response_received, result, data = self.pending_db_response_dict[request_id]
                    if response_received:
                        del self.pending_db_response_dict[request_id]
                        print(f"Received response from database for request_id {request_id}: {result}, {data}")
                        return (result, data)



    def start_server(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.server_sock.bind((host, port))
        self.server_sock.listen(5)
        self.server_sock.settimeout(1.0)
        print(f"Lobby server listening on {host}:{port}")
        self.accept_connections()
        self.server_sock.close()

    def start(self, host = "0.0.0.0", port = 21354) -> None:
        server_thread = threading.Thread(target=self.start_server, args=(host, port,))
        server_thread.start()
        game_servers_manager_thread = threading.Thread(target=self.manage_game_servers)
        game_servers_manager_thread.start()
        time.sleep(0.2)
        try:
            while True:
                cmd = input("Enter 'stop' to stop the server: ")
                if cmd == 'stop':
                    self.shutdown_event.set()
                    with self.game_server_lock:
                        for game_server in self.game_servers.values():
                            game_server.stop()
                    break
                else:
                    print("invalid command.")
        except KeyboardInterrupt:
            self.shutdown_event.set()
            with self.game_server_lock:
                for game_server in self.game_servers.values():
                    game_server.stop()

        server_thread.join()
        game_servers_manager_thread.join()