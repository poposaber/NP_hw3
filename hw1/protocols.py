from message_format import MessageFormat

class Protocols:
    class Command:
        REG_USERNAME = MessageFormat("REG_USERNAME", [str]) # REG_USERNAME|<username>
        REG_PASSWORD = MessageFormat("REG_PASSWORD", [str]) # REG_PASSWORD|<password>
        REG_CANCEL = MessageFormat("REG_CANCEL")
        LOGIN = MessageFormat("LOGIN", [str, str]) # LOGIN|<username>|<password>
        EXIT = MessageFormat("EXIT")
        LOGOUT = MessageFormat("LOGOUT")
        RECORD_WIN = MessageFormat("RECORD_WIN")
        RECORD_PLAY = MessageFormat("RECORD_PLAY")
        STATUS = MessageFormat("STATUS")
    class Response:
        WELCOME = MessageFormat("WELCOME") # "Welcome to the server. Please login or register.\n"
        REG_USERNAME_RESULT = MessageFormat("REG_USERNAME_RESULT", [int]) # 0: success, go on with password; -1: username already exists
        REG_SUCCESS = MessageFormat("REG_SUCCESS")
        REG_CANCELLED = MessageFormat("REG_CANCELLED")
        LOGIN_RESULT = MessageFormat("LOGIN_RESULT", [int]) # 0: success; -1: invalid credential; -2: other client using this account
        UNKNOWN_COMMAND = MessageFormat("UNKNOWN_COMMAND")
        GOODBYE = MessageFormat("GOODBYE")
        LOGOUT_SUCCESS = MessageFormat("LOGOUT_SUCCESS")
        WIN_RECORD_DONE = MessageFormat("WIN_RECORD_DONE")
        PLAY_RECORD_DONE = MessageFormat("PLAY_RECORD_DONE")
        STATUS_RESULT = MessageFormat("STATUS_RESULT", [int, int]) # STATUS_RESULT|<games_played>|<games_won>
    class P2P:
        SCAN = MessageFormat("SCAN")
        PLAYER_HERE = MessageFormat("PLAYER_HERE", [str]) # PLAYER_HERE|<username>
        INVITE = MessageFormat("INVITE", [str]) # INVITE|<inviter>
        CONNECT = MessageFormat("CONNECT", [str, int]) # CONNECT|<ip>|<port>
        ACCEPT = MessageFormat("ACCEPT", [str]) # ACCEPT|<accepter>
        DECLINE = MessageFormat("DECLINE", [str]) # DECLINE|<decliner>
        ALREADY_IN_GAME = MessageFormat("ALREADY_IN_GAME", [str]) # ALREADY_IN_GAME|<username>
    class Ingame:
        READY = MessageFormat("READY")
        ROUND = MessageFormat("ROUND", [int]) # ROUND|<round_num>
        OK = MessageFormat("OK")
        GAMEOVER = MessageFormat("GAMEOVER")
        PLAYCARD_DONE = MessageFormat("PLAYCARD_DONE")
        PLAYSKILLCARD_DONE = MessageFormat("PLAYSKILLCARD_DONE")
        PLAYSKILLCARD = MessageFormat("PLAYSKILLCARD", [int]) # 1 for quantity seer and so on
        SKILLCARDRESULT = MessageFormat("SKILLCARDRESULT", [int]) # SKILLCARDRESULT|<status>
        ROUNDCOMPLETED = MessageFormat("ROUNDCOMPLETED") 
        ROUND_WINNER = MessageFormat("ROUND_WINNER", [str]) # ROUND_WINNER|A or ROUND_WINNER|B
        NOW_POINTS = MessageFormat("NOW_POINTS", [int, int]) # NOW_POINTS|<point_a>|<point_b>
        GAME_WINNER = MessageFormat("GAME_WINNER", [str]) # GAME_WINNER|A or GAME_WINNER|B
        GAME_FIRST = MessageFormat("GAME_FIRST", [str]) # GAME_FIRST|A or GAME_FIRST|B
        ROUND_FIRST = MessageFormat("ROUND_FIRST", [str]) # ROUND_FIRST|A or ROUND_FIRST|B
        REPORTCARD = MessageFormat("REPORTCARD", [int, int, int]) # REPORTCARD|4|2|-1 means opponent played 4 and 2
        FORFEIT = MessageFormat("FORFEIT")