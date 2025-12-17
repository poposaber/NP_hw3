from game import Game
import socket
import time

def main():
    # connect to game server (assume localhost and default port)
    host = '127.0.0.1'
    port = 12345
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while True:
        try:
            s.connect((host, port))
            break
        except Exception:
            time.sleep(0.5)

    # receive role assignment from server
    try:
        role_msg = s.recv(1024).decode()
        role = None
        if role_msg.startswith('ROLE|'):
            role = role_msg.split('|', 1)[1].strip()
        is_player_a = (role == 'A')
    except Exception:
        is_player_a = True

    # try to connect to lobby server on localhost:21354 (optional)
    lobby_sock = None
    try:
        ls = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ls.settimeout(2.0)
        ls.connect(("127.0.0.1", 21354))
        lobby_sock = ls
    except Exception:
        lobby_sock = None
    assert lobby_sock is not None
    g = Game(s, lobby_sock, is_player_a)
    g.play_game()

if __name__ == '__main__':
    main()
# from client import GameClient

# gc = GameClient()
# gc.start()