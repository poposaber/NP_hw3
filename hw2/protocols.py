from message_format import MessageFormat

class Protocols:
    class ConnectionToLobby:
        HANDSHAKE = MessageFormat({
            "connection_type": str
        })
        """
        connection_type: 'client', 'database_server', or 'game_server'
        """

    class LobbyToConnection:
        HANDSHAKE_RESPONSE = MessageFormat({
            "result": str,
            "message": str
        })
        """
        result: 'confirmed' or 'error' \n
        message: additional information
        """

    class LobbyToDB:
        REQUEST = MessageFormat({
            "request_id": str,
            "collection": str,
            "action": str,
            "data": dict
        })
        """
        request_id: unique identifier for the request \n
        collection: e.g., 'user', 'room', 'gamelog' \n
        action: e.g., 'create', 'read', 'update', 'delete', 'query'\n
        data: additional data as a dictionary
        """

    class DBToLobby:
        RESPONSE = MessageFormat({
            "responding_request_id": str,
            "result": str,
            "data": dict
        })
        """
        responding_request_id: the request_id this response is for \n
        result: 'success' or 'failure' \n
        data: additional data as a dictionary
        """

    class ClientToLobby:
        COMMAND = MessageFormat({
            "command": str,
            "params": dict
        })
        """
        command: e.g., 'login', 'register', 'create_room', etc. \n
        params: additional parameters as a dictionary
        """
    
    class LobbyToClient:
        MESSAGE = MessageFormat({
            "message_type": str,
            "responding_command": str,
            "event_type": str,
            "result": str,
            "data": dict
        })
        """
        message_type: 'response' or 'event' \n
        responding_command: the command this message is responding to (for responses) \n
        event_type: type of event (for events) \n
        result: 'success', 'failure', etc. (for responses) \n
        data: additional data as a dictionary
        """

    class ClientToGameServer:
        CONNECT = MessageFormat({
            "username": str,
            "room_id": str,
            "role": str
        })
        """
        username: player or spectator's username \n
        room_id: ID of the game room \n
        role: "player" or "spectator"
        """

    class GameServerToPlayer:
        CONNECT_RESPONSE = MessageFormat({
            "result": str,
            "role": str,
            "seed": int,
            "bagRule": str,
            "gravityPlan": dict
        })
        """
        result: 'success' or 'failure' \n
        role: 'player1' or 'player2' \n
        seed: random seed for the game session \n
        bagRule: rule for piece bag generation \n
        gravityPlan: plan for gravity changes during the game
        """
        GAME_START_RESULT = MessageFormat({
            "result": str,
            "message": str, 
            "player1_username": str,
            "player2_username": str,
            "player_health": int,
            "now_piece": str,
            "next_pieces": list,
            "goal_score": int
        })
        """
        result: 'success' or 'failure' \n
        message: additional information \n
        player1_username: username of player 1 \n
        player2_username: username of player 2 \n
        player_health: initial health of each player \n
        now_piece: initial piece on the game field, such as "I" \n
        next_pieces: initial next pieces, such as ["J", "L", "O"] \n
        goal_score: score needed to win
        """
        GAME_UPDATE = MessageFormat({
            "player1": dict,
            "player2": dict,
            "data": dict
        })
        """
        player1: game state update for player 1 \n
        player2: game state update for player 2
        the dictionary mainly contains:
            'board': string representing the game board, contains width * height chars \n
            'now_piece': current piece shape (list) \n
            'color': current piece color \n
            'position': current piece position \n
            'next_pieces': list of next piece types (list[str]) \n
            'score': current score \n
            'health': current health \n
            'revive_time': current revive time remaining \n
        data: additional data as a dictionary, such as game over info
        """

    class PlayerToGameServer:
        GAME_ACTION = MessageFormat({
            "action": str,
            "data": dict
        })
        """
        action: e.g., 'move_left', 'rotate', 'drop', 'ready', etc. \n
        data: additional data as a dictionary
        """


class Words:
    class Collection:
        USER = "user"
        ROOM = "room"
        GAMELOG = "gamelog"
    class Action:
        CREATE = "create"
        READ = "read"
        UPDATE = "update"
        DELETE = "delete"
        QUERY = "query"
        ADD_USER = "add_user"
        ADD_SPECTATOR = "add_spectator"
        REMOVE_USER = "remove_user"
        ADD_WIN = "add_win"
        ADD_GAME_PLAYED = "add_game_played"
    class Command:
        EXIT = "exit"
        CHECK_USERNAME = "check_username" # Check if a username is available to register
        CHECK_JOINABLE_ROOMS = "check_joinable_rooms" # Get a list of public joinable rooms
        CHECK_SPECTATABLE_ROOMS = "check_spectatable_rooms" # Get a list of public spectatable rooms
        CHECK_ONLINE_USERS = "check_online_users" # Get a list of online users
        REGISTER = "register"
        LOGIN = "login"
        LOGOUT = "logout"
        CREATE_ROOM = "create_room"
        JOIN_ROOM = "join_room"
        SPECTATE_ROOM = "spectate_room"
        LEAVE_ROOM = "leave_room"
        DISBAND_ROOM = "disband_room"
        INVITE_USER = "invite_user"
        ACCEPT_INVITE = "accept_invite"
        DECLINE_INVITE = "decline_invite"
        START_GAME = "start_game"
    class Result:
        SUCCESS = "success"
        FAILURE = "failure"
        FOUND = "found"
        NOT_FOUND = "not_found"
        ERROR = "error"
        VALID = "valid"
        INVALID = "invalid"
        CONFIRMED = "confirmed"
    class DataParamKey:
        USERNAME = "username"
        INVITER_USERNAME = "inviter_username"
        INVITEE_USERNAME = "invitee_username"
        PASSWORD = "password"
        ROOM_ID = "room_id"
        PLAYERS = "players"
        GAME_STATE = "game_state"
        SCORE = "score"
        MESSAGE = "message"
        TIMESTAMP = "timestamp"
        DETAILS = "details"
        REASON = "reason"
        GAMES_PLAYED = "games_played"
        GAMES_WON = "games_won"
        ONLINE = "online"
        CURRENT_ROOM_ID = "current_room_id"
        PRIVACY = "privacy"
        NOW_ROOM_INFO = "now_room_info"
        OWNER = "owner"
        SETTINGS = "settings"
        USERS = "users"
        IS_PLAYING = "is_playing"
        HOST = "host"
        PORT = "port"
        SPECTATORS = "spectators"
    class Reason:
        INVALID_CREDENTIALS = "invalid_credentials"
        ROOM_FULL = "room_full"
        GAME_ALREADY_STARTED = "game_already_started"
        ACCOUNT_USING = "account_using"
    class Message:
        WELCOME_USER = "welcome_user"
    class MessageType:
        RESPONSE = "response"
        EVENT = "event"
    class EventType:
        USER_JOINED = "user_joined"
        USER_LEFT = "user_left"
        ROOM_DISBANDED = "room_disbanded"
        INVITATION_RECEIVED = "invitation_received"
        CONNECT_TO_GAME_SERVER = "connect_to_game_server"
        CONNECT_TO_GAME_SERVER_AS_SPECTATOR = "connect_to_game_server_as_spectator"
        SERVER_SHUTDOWN = "server_shutdown"
    class ConnectionType:
        CLIENT = "client"
        DATABASE_SERVER = "database_server"
        GAME_SERVER = "game_server"
    class GameAction:
        MOVE_LEFT = "move_left"
        MOVE_RIGHT = "move_right"
        ROTATE = "rotate"
        SOFT_DROP = "soft_drop"
        HARD_DROP = "hard_drop"
        CHANGE_COLOR = "change_color"
        READY = "ready"
        DISCONNECT = "disconnect"
