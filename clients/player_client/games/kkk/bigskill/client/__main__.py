from game import Game
import socket
import time
import sys

def main():
    # connect to game server (use argv host/port if provided)
    host = "linux1.cs.nycu.edu.tw"
    port = 12359

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while True:
        try:
            print(f"Connecting to game server at {host}:{port}")
            s.connect((host, port))
            print(f"Connected to game server.")
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

    g = Game(s, is_player_a)
    g.play_game()

if __name__ == '__main__':
    main()
# from client import GameClient

# gc = GameClient()
# gc.start()