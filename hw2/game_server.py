from message_format_passer import MessageFormatPasser
from protocols import Protocols, Words
from game import Game
from queue import Queue
from queue import Full
from queue import Empty
import socket
import threading
import time
import random


class GameServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 22345) -> None:
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.settimeout(1.0)  # 1 second timeout for accept
        self.game_thread: threading.Thread | None = None
        self.handle_player1_thread: threading.Thread | None = None
        self.handle_player2_thread: threading.Thread | None = None
        self.handle_player1_out_thread: threading.Thread | None = None
        self.handle_player2_out_thread: threading.Thread | None = None
        self.player1_passer: MessageFormatPasser | None = None
        self.player2_passer: MessageFormatPasser | None = None
        self.player1_queue: Queue = Queue(maxsize=100)
        self.player2_queue: Queue = Queue(maxsize=100)
        self.spectator_ptq_list: list[tuple[MessageFormatPasser, threading.Thread, Queue]] = []
        self.player1_username: str | None = None
        self.player2_username: str | None = None
        self.room_id: str | None = None
        self.lock = threading.Lock()
        self.seed = random.randint(0, 1000000)
        self.game = Game(seed=self.seed)
        self.action_queue: Queue = Queue()
        self.running = threading.Event()
        self.running.set()
        self.start_accepted_event = threading.Event()
        self.player1_ready = threading.Event()
        self.player2_ready = threading.Event()
        self.player1_disconnected = threading.Event()
        self.player2_disconnected = threading.Event()
        

    def wait_until_started(self) -> None:
        self.start_accepted_event.wait()

    def start(self) -> None:
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        print(f"Game server listening on {self.host}:{self.port}")
        while self.running.is_set():
            try:
                self.start_accepted_event.set()
                client_socket, addr = self.server_socket.accept()
                print(f"Accepted connection from {addr}")
                passer = MessageFormatPasser(client_socket)
                arg_list = passer.receive_args(Protocols.ClientToGameServer.CONNECT)
                if not arg_list:
                    print("Failed to receive connection message")
                    client_socket.close()
                    continue
                connection_type = arg_list[2]
                if self.room_id is None:
                    self.room_id = arg_list[1]
                elif self.room_id != arg_list[1]:
                    print("Mismatched room ID, rejecting connection")
                    passer.send_args(Protocols.GameServerToPlayer.CONNECT_RESPONSE, Words.Result.FAILURE, {'message': 'Mismatched room ID'})
                    client_socket.close()
                    continue

                if connection_type == 'player':
                    with self.lock:
                        if self.player1_passer is not None and self.player2_passer is not None:
                            print("Maximum players connected, rejecting new connection")
                            passer.send_args(Protocols.GameServerToPlayer.CONNECT_RESPONSE, Words.Result.FAILURE, {'message': 'Game is full'})
                            client_socket.close()
                            continue
                        if self.player1_passer is None:
                            self.player1_passer = passer
                            self.player1_username = arg_list[0]
                            passer.send_args(Protocols.GameServerToPlayer.CONNECT_RESPONSE, Words.Result.SUCCESS, 'player1', self.seed, "random-uniform", {"drop_speed": 1.0})
                        else:
                            self.player2_passer = passer
                            self.player2_username = arg_list[0]
                            passer.send_args(Protocols.GameServerToPlayer.CONNECT_RESPONSE, Words.Result.SUCCESS, 'player2', self.seed, "random-uniform", {"drop_speed": 1.0})
                    print(f"Player connected: {addr}")
                    # Since this is 2-player game, after accepting 2 players, stop accepting more
                    if self.player1_passer is not None and self.player2_passer is not None:
                        print("Two players connected, starting game session")

                        self.game_thread = threading.Thread(target=self.handle_game_session)
                        self.game_thread.start()

                        self.handle_player1_thread = threading.Thread(target=self.handle_player, args=(self.player1_passer, "player1"))
                        self.handle_player1_thread.start()

                        self.handle_player2_thread = threading.Thread(target=self.handle_player, args=(self.player2_passer, "player2"))
                        self.handle_player2_thread.start()

                        self.handle_player1_out_thread = threading.Thread(target=self.handle_player_out, args=(self.player1_passer, "player1", self.player1_queue))
                        self.handle_player1_out_thread.start()

                        self.handle_player2_out_thread = threading.Thread(target=self.handle_player_out, args=(self.player2_passer, "player2", self.player2_queue))
                        self.handle_player2_out_thread.start()
                elif connection_type == 'spectator':
                    with self.lock:
                        spectator_queue = Queue(maxsize=100)
                        thr = threading.Thread(target=self.handle_spectator, args=(passer, spectator_queue))
                        thr.start()
                        self.spectator_ptq_list.append((passer, thr, spectator_queue))
                    passer.send_args(Protocols.GameServerToPlayer.CONNECT_RESPONSE, Words.Result.SUCCESS, 'spectator', self.seed, "random-uniform", {"drop_speed": 1.0})
                    print(f"Spectator connected: {addr}")
                else:
                    print("Unknown connection type, rejecting connection")
                    passer.send_args(Protocols.GameServerToPlayer.CONNECT_RESPONSE, Words.Result.FAILURE, {'message': 'Unknown connection type'})
                    client_socket.close()
                
            except TimeoutError:
                continue
            except Exception as e:
                print(f"Error accepting connections: {e}")
        print("Game server stopping acceptance of new connections.")
        self.stop()

    def handle_spectator(self, passer: MessageFormatPasser, spectator_queue: Queue) -> None:
        try:
            while not (self.player1_ready.is_set() and self.player2_ready.is_set()):
                if not self.running.is_set():
                    passer.close()
                    return
                time.sleep(0.1)
            passer.send_args(Protocols.GameServerToPlayer.GAME_START_RESULT, 
                                    Words.Result.SUCCESS,
                                    "Game started successfully",
                                    self.player1_username,
                                    self.player2_username,
                                    self.game.player1.health,
                                    self.game.tetris1.now_piece.type_name if self.game.tetris1.now_piece else None,
                                    [piece.type_name for piece in self.game.tetris1.next_piece_list],
                                    self.game.goal_score)
            while self.running.is_set():
                try:
                    state1, state2, data = spectator_queue.get(timeout=1.0)
                    passer.send_args(Protocols.GameServerToPlayer.GAME_UPDATE, state1, state2, data)
                except Empty:
                    continue
                except TimeoutError:
                    continue
                except ConnectionResetError:
                    print("Spectator disconnected unexpectedly")
                    with self.lock:
                        self.spectator_ptq_list.remove((passer, threading.current_thread(), spectator_queue))
                    passer.close()
                    return
                except Exception as e:
                    print(f"Error handling spectator queue: {e}")
            passer.close()

        except Exception as e:
            print(f"Error handling spectator: {e}")
        print("Exiting handler for spectator")


    def handle_player(self, passer: MessageFormatPasser, player_id: str) -> None:
        try:
            while self.running.is_set():
                arg_list = passer.receive_args(Protocols.PlayerToGameServer.GAME_ACTION)
                if not arg_list:
                    print("Player disconnected")
                    with self.lock:
                        if player_id == "player1":
                            self.player1_passer = None
                        else:
                            self.player2_passer = None
                    self.action_queue.put((player_id, Words.GameAction.DISCONNECT, {}))
                    break
                action, data = arg_list
                # Process player action
                self.action_queue.put((player_id, action, data))

                print(f"Received action from {player_id}: {action} with data: {data}")
                # Here you would update the game state based on the action
        except ConnectionResetError:
            print(f"{player_id} disconnected unexpectedly")
            with self.lock:
                if player_id == "player1":
                    if self.player1_passer is not None:
                        self.player1_passer.close()
                    self.player1_passer = None
                else:
                    if self.player2_passer is not None:
                        self.player2_passer.close()
                    self.player2_passer = None
            self.action_queue.put((player_id, Words.GameAction.DISCONNECT, {}))
        except Exception as e:
            print(f"Error handling {player_id}: {e}")
            with self.lock:
                if player_id == "player1":
                    if self.player1_passer is not None:
                        self.player1_passer.close()
                    self.player1_passer = None
                else:
                    if self.player2_passer is not None:
                        self.player2_passer.close()
                    self.player2_passer = None
            self.action_queue.put((player_id, Words.GameAction.DISCONNECT, {}))
        print(f"Exiting handler for {player_id}")

    def handle_player_out(self, passer: MessageFormatPasser, player_id: str, player_queue: Queue) -> None:
        try:
            while self.running.is_set():
                try:
                    state1, state2, data = player_queue.get(timeout=1.0)
                    passer.send_args(Protocols.GameServerToPlayer.GAME_UPDATE, state1, state2, data)
                except Empty:
                    continue
                except TimeoutError:
                    continue
                except ConnectionResetError:
                    print(f"{player_id} disconnected unexpectedly")
                    with self.lock:
                        if player_id == "player1":
                            self.player1_passer = None
                        else:
                            self.player2_passer = None
                    self.action_queue.put((player_id, Words.GameAction.DISCONNECT, {}))
                    passer.close()
                    return
                except Exception as e:
                    print(f"Error handling {player_id} output queue: {e}")

        except Exception as e:
            print(f"Error in handle_player_out for {player_id}: {e}")
        print(f"Exiting output handler for {player_id}")

    def handle_game_session(self) -> None:
        now = time.time()
        prev = now
        try:
            while not (self.player1_ready.is_set() and self.player2_ready.is_set()):
                player_id, action, data = self.action_queue.get()
                if action == Words.GameAction.READY:
                    if player_id == "player1":
                        self.player1_ready.set()
                        print("Player 1 is ready")
                    else:
                        self.player2_ready.set()
                        print("Player 2 is ready")
                elif action == Words.GameAction.DISCONNECT:
                    print(f"{player_id} disconnected before game start, aborting game session.")
                    if player_id == "player1":
                        if self.player2_passer is not None:
                            self.player2_passer.send_args(Protocols.GameServerToPlayer.GAME_START_RESULT, 
                                                    Words.Result.FAILURE,
                                                    "Player 1 disconnected before game start", 
                                                    "", "", 0, "", [], 0)
                        self.game.gameover = True
                        self.running.clear()
                    else:
                        if self.player1_passer is not None:
                            self.player1_passer.send_args(Protocols.GameServerToPlayer.GAME_START_RESULT, 
                                                    Words.Result.FAILURE,
                                                    "Player 2 disconnected before game start", 
                                                    "", "", 0, "", [], 0)
                        self.game.gameover = True
                        self.running.clear()
                    return
                        
                else:
                    print(f"Received non-ready action {action} from {player_id} before both players were ready, ignoring.")
                # time.sleep(0.1)
            if self.player1_passer is None or self.player2_passer is None:
                print("One of the players disconnected before game start, aborting game session.")
                return
            self.player1_passer.send_args(Protocols.GameServerToPlayer.GAME_START_RESULT, 
                                          Words.Result.SUCCESS,
                                          "Game started successfully",
                                          self.player1_username,
                                          self.player2_username,
                                          self.game.player1.health,
                                          self.game.tetris1.now_piece.type_name if self.game.tetris1.now_piece else None,
                                          [piece.type_name for piece in self.game.tetris1.next_piece_list],
                                          self.game.goal_score)
            self.player2_passer.send_args(Protocols.GameServerToPlayer.GAME_START_RESULT, 
                                          Words.Result.SUCCESS,
                                          "Game started successfully",
                                          self.player1_username,
                                          self.player2_username,
                                          self.game.player2.health,
                                          self.game.tetris2.now_piece.type_name if self.game.tetris2.now_piece else None,
                                          [piece.type_name for piece in self.game.tetris2.next_piece_list],
                                          self.game.goal_score)
            # for spectator in self.spectator_passers:
            #     spectator.send_args(Protocols.GameServerToPlayer.GAME_START_RESULT, 
            #                         Words.Result.SUCCESS,
            #                         "Game started successfully",
            #                         self.player1_username,
            #                         self.player2_username,
            #                         self.game.player1.health,
            #                         self.game.tetris1.now_piece.type_name if self.game.tetris1.now_piece else None,
            #                         [piece.type_name for piece in self.game.tetris1.next_piece_list],
            #                         self.game.goal_score)
            
            print("Both players are ready. Starting the game loop.")

            while self.running.is_set():
                # Process all queued actions
                while not self.action_queue.empty():
                    player_id, action, data = self.action_queue.get()
                    if action == Words.GameAction.DISCONNECT:
                        print(f"{player_id} disconnected, ending game session.")
                        if player_id == "player1":
                            self.game.winner = "player2"
                            self.game.gameover = True
                            self.player1_disconnected.set()
                        else:
                            self.game.winner = "player1"
                            self.game.gameover = True
                            self.player2_disconnected.set()
                        continue
                    self.game.handle_player_action(player_id, action, data)

                now = time.time()
                delta_time = now - prev
                self.game.update(delta_time)
                prev = now
                # Send updated game state to both players
                state1 = {
                    'board': self.game.get_board_string("player1"),
                    'now_piece': self.game.tetris1.now_piece.shape if self.game.tetris1.now_piece else None,
                    'color': self.game.tetris1.now_piece.color if self.game.tetris1.now_piece else None,
                    'position': self.game.tetris1.now_piece.position if self.game.tetris1.now_piece else None,
                    'next_pieces': [piece.type_name for piece in self.game.tetris1.next_piece_list],
                    'score': self.game.player1.score,
                    'health': self.game.player1.health,
                    'revive_time': self.game.player1.revive_time,
                }
                state2 = {
                    'board': self.game.get_board_string("player2"),
                    'now_piece': self.game.tetris2.now_piece.shape if self.game.tetris2.now_piece else None,
                    'color': self.game.tetris2.now_piece.color if self.game.tetris2.now_piece else None,
                    'position': self.game.tetris2.now_piece.position if self.game.tetris2.now_piece else None,
                    'next_pieces': [piece.type_name for piece in self.game.tetris2.next_piece_list],
                    'score': self.game.player2.score,
                    'health': self.game.player2.health,
                    'revive_time': self.game.player2.revive_time,
                }
                data = {}
                if self.game.gameover:
                    data["game_over"] = True
                    data["winner"] = self.game.winner
                    if self.player1_disconnected.is_set():
                        data["message"] = "Player 1 disconnected"
                    elif self.player2_disconnected.is_set():
                        data["message"] = "Player 2 disconnected"
                    
                with self.lock:
                    if self.player1_passer is not None:
                        #self.player1_passer.send_args(Protocols.GameServerToPlayer.GAME_UPDATE, state1, state2, data)
                        try:
                            self.player1_queue.put_nowait((state1, state2, data))
                        except Full:
                            try:
                                self.player1_queue.get_nowait()  # Remove oldest
                                self.player1_queue.put_nowait((state1, state2, data))
                            except Empty:
                                pass
                    if self.player2_passer is not None:
                        try:
                            self.player2_queue.put_nowait((state1, state2, data))
                        except Full:
                            try:
                                self.player2_queue.get_nowait()  # Remove oldest
                                self.player2_queue.put_nowait((state1, state2, data))
                            except Empty:
                                pass
                    for _, _, spectator_queue in self.spectator_ptq_list:
                        try:
                            spectator_queue.put_nowait((state1, state2, data))
                        except Full:
                            try:
                                spectator_queue.get_nowait()  # Remove oldest
                                spectator_queue.put_nowait((state1, state2, data))
                            except Empty:
                                pass
                            print("Spectator queue is full")
                    # for spectator in self.spectator_passers:
                    #     try:
                    #         spectator.send_args(Protocols.GameServerToPlayer.GAME_UPDATE, state1, state2, data)
                    #     except ConnectionError:
                    #         print("A spectator disconnected.")
                    #         self.spectator_passers.remove(spectator)
                    #     except Exception as e:
                    #         print(f"Error sending update to spectator: {e}")
                if self.game.gameover:
                    print(f"Game over! Winner: {self.game.winner}")
                    time.sleep(5.0) # wait before ending the session
                    self.stop()  # Stop the game loop
                time.sleep(0.1)  # Sleep to limit update rate
        except Exception as e:
            print(f"Error in game session: {e}")
        print("Game session ended.")

    def stop(self) -> None:
        self.running.clear()
        try:
            self.server_socket.close()
        except Exception as e:
            pass
        if self.game_thread is not None and self.game_thread.is_alive() and threading.current_thread() != self.game_thread:
            self.game_thread.join()
        if self.handle_player1_thread is not None and self.handle_player1_thread.is_alive() and threading.current_thread() != self.handle_player1_thread:
            self.handle_player1_thread.join()
        if self.handle_player2_thread is not None and self.handle_player2_thread.is_alive() and threading.current_thread() != self.handle_player2_thread:
            self.handle_player2_thread.join()
        with self.lock:
            if self.player1_passer is not None:
                try:
                    self.player1_passer.close()
                except Exception as e:
                    pass
            if self.player2_passer is not None:
                try:
                    self.player2_passer.close()
                except Exception as e:
                    pass
        print("Server shut down.")
