from player import Player
import socket
import random
from protocols import Protocols
import time
from interactable import Interactable
from message_format import MessageFormat

class Game(Interactable):
    TOTAL_ROUNDS = 9

    def __init__(self, game_client_tcp_sock: socket.socket, lobby_tcp_sock: socket.socket, is_player_a: bool):
        self.game_client_tcp_sock = game_client_tcp_sock
        self.lobby_tcp_sock = lobby_tcp_sock
        self.player = Player()
        self.player.is_player_a = is_player_a
        self.opponent = Player()
        self.opponent.is_player_a = not is_player_a
        self.current_round = 1
        self.this_game_a_goes_first = None  # None, True (A first), False (B first)
        self.this_round_a_goes_first = None  # None, True (A first), False (B first)
        self.this_round_winner = None # 'A', 'B'. No draws allowed.
        self.this_game_winner = None # 'A', 'B'. No draws allowed.
        self.each_player_won_rounds = [0, 0]  # [A's wins, B's wins]
        self.game_over = False
        self.opponent_disconnected = False
        self.player_forfeit = False
        self.opponent_forfeit = False


    def play_game(self):
        try:
            print("Waiting for opponent to connect...")
            if (self.player.is_player_a):
                self.send_msgfmt_args_using_game_clt(Protocols.Ingame.READY)
                if self.receive_and_check_is_msgfmt_name_using_game_clt(Protocols.Ingame.READY):
                    print("Both players are ready. Starting the game...")
            else:
                if self.receive_and_check_is_msgfmt_name_using_game_clt(Protocols.Ingame.READY):
                    print("Both players are ready. Starting the game...")
                    self.send_msgfmt_args_using_game_clt(Protocols.Ingame.READY)

            time.sleep(1)
            print("Game started! You are Player " + ("A" if self.player.is_player_a else "B"))
            time.sleep(3)
            print(f"First to win {Game.TOTAL_ROUNDS // 2 + 1} rounds wins the game.") 
            time.sleep(3)
            print("First round will be decided by a coin toss.")

            if self.player.is_player_a:
                self.this_game_a_goes_first = random.choice([True, False])
                self.send_msgfmt_args_using_game_clt(Protocols.Ingame.GAME_FIRST, "A" if self.this_game_a_goes_first else "B")
                if not self.receive_and_check_is_msgfmt_name_using_game_clt(Protocols.Ingame.OK):
                    print("Error: Did not receive OK from opponent.")
                    return
            else:
                self.this_game_a_goes_first = self.receive_msgfmt_and_parse_using_game_clt(Protocols.Ingame.GAME_FIRST)[0] == "A"
                self.send_msgfmt_args_using_game_clt(Protocols.Ingame.OK)
            time.sleep(2)
            print(f"Player {'A' if self.this_game_a_goes_first else 'B'} will go first in the first round.")
            self.this_round_a_goes_first = self.this_game_a_goes_first
            time.sleep(3)

            while not self.game_over:
                print()
                print()
                print(f"============================== Round {self.current_round} ==============================")
                print()
                print()

                if self.player.is_player_a:
                    self.send_msgfmt_args_using_game_clt(Protocols.Ingame.ROUND, self.current_round)
                    if not self.receive_and_check_is_msgfmt_name_using_game_clt(Protocols.Ingame.OK):
                        print("Error: Did not receive OK from opponent.")
                        return
                    
                    self.send_msgfmt_args_using_game_clt(Protocols.Ingame.ROUND_FIRST, "A" if self.this_round_a_goes_first else "B")
                    if self.this_round_a_goes_first:
                        if not self.receive_and_check_is_msgfmt_name_using_game_clt(Protocols.Ingame.OK):
                            print("Error: Did not receive OK from opponent.")
                            return
                else:
                    round_number, = self.receive_msgfmt_and_parse_using_game_clt(Protocols.Ingame.ROUND)
                    if round_number != self.current_round:
                        print("Error: Round number mismatch.")
                        return
                    self.send_msgfmt_args_using_game_clt(Protocols.Ingame.OK)

                    first_player, = self.receive_msgfmt_and_parse_using_game_clt(Protocols.Ingame.ROUND_FIRST)
                    if self.this_round_a_goes_first != (first_player == 'A'):
                        print("Error: First player mismatch.")
                        return
                    if self.this_round_a_goes_first:
                        self.send_msgfmt_args_using_game_clt(Protocols.Ingame.OK)
                    
                time.sleep(2)
                    
                self.play_round()
                self.current_round += 1
                if self.current_round > Game.TOTAL_ROUNDS or max(self.each_player_won_rounds) >= Game.TOTAL_ROUNDS // 2 + 1:
                    self.game_over = True
        except ConnectionResetError as e:
            print("Opponent disconnected in game.")
            self.opponent_disconnected = True
        except Exception as e:
            print(f"Error in game: {e}")

        self.conclude_game()

        

    def play_round(self):
        try:
            if self.this_round_a_goes_first == self.player.is_player_a:
                print("You go first this round.")
                time.sleep(2)
                self.player_turn(second = False)

                if self.player_forfeit or self.opponent_forfeit:
                    return

                self.opponent_turn(second = True)
            else:
                print("Opponent goes first this round.")
                time.sleep(2)
                self.opponent_turn(second = False)

                if self.player_forfeit or self.opponent_forfeit:
                    return
                
                self.player_turn(second = True)

            if self.player_forfeit or self.opponent_forfeit:
                return

            self.evaluate_round()
            self.this_round_a_goes_first = not self.this_round_a_goes_first
        except ConnectionResetError as e:
            print(f"Opponent disconnected in round: {e}")
            raise e
        except Exception as e:
            print(f"Error playing round: {e}")
            raise e

    # player playing second move can use skill cards.
    def player_turn(self, second):
        try:
            print()
            print("Your turn to play cards.")
            print()
            time.sleep(2)

            if second:
                print()
                print("Skill cards introduction: ")
                print("a. Quantity Seer: Know how many cards opponent's played.")
                print("b. Minimum Seer: Know the minimum number of cards opponent's played.")
                print("c. Minimum Destroyer: Destroy one minimum card opponent's played.")
                print("You can use multiple skill cards in one turn, but you can only use each type of skill card once per turn.")
                print()

                time.sleep(1.5)
                
                self.use_skill_card()
                print("You can now play your cards.")
            else:
                print("You go first this round, so you cannot use skill cards.")
            print()

            time.sleep(1.5)

            self.play_card()
        except ConnectionResetError as e:
            print(f"Opponent disconnected in their turn: {e}")
            raise e
        except Exception as e:
            print(f"Error in player turn: {e}")
            raise e
    
    def opponent_turn(self, second):
        print()
        print("Opponent's turn to play cards.")
        time.sleep(2)
        try:
            if second:
                print("Waiting for opponent to play skill cards (if any)...")
                self.take_skill_card_effects()
            print("Opponent is now playing their cards...")

            _, fname = self.receive_and_get_msgfmt_name_using_game_clt()
            if fname == Protocols.Ingame.FORFEIT.name:
                print("Opponent forfeited.")
                if not self.player.is_player_a:
                    self.send_msgfmt_using_game_clt(Protocols.Ingame.OK)
                self.opponent_forfeit = True
                self.game_over = True
                self.this_game_winner = 'A' if self.player.is_player_a else 'B'
                # for debug
                # print(f"self.this_game_winner={self.this_game_winner}")
                return
            elif fname != Protocols.Ingame.PLAYCARD_DONE.name:
                print("Error: Did not receive PLAYCARD_DONE from opponent.")
                return
            
            print("Opponent has played their cards.")
            if not self.player.is_player_a and second: # I am player B and opponent (player A) plays second
                self.send_msgfmt_args_using_game_clt(Protocols.Ingame.OK)
        except ConnectionResetError as e:
            print(f"Opponent disconnected in their turn: {e}")
            raise e
        except Exception as e:
            print(f"Error receiving message: {e}")
            raise e

    def use_skill_card(self):
        use_skill_card_count = [0, 0, 0, 0] # [not used, Quantity Seer: Know how many cards opponent's played, Minimum Seer: Know the minimum number of cards opponent's played, Minimum Destroyer: Destroy one minimum card opponent's played]
        
        print()
        print("Skill cards available: ")
        print(f"{self.player.each_skill_card_count[1]} Quantity Seer, ")
        print(f"{self.player.each_skill_card_count[2]} Minimum Seer, ")
        print(f"{self.player.each_skill_card_count[3]} Minimum Destroyer. ")
        print()

        time.sleep(1)
        
        while True:
            try:
                print()
                print("Enter the skill cards you want to use one-by-one (e.g., 'a' to use Quantity Seer, or press Enter to skip): ")
                skill_card = input().strip()
                if skill_card == "":
                    self.send_msgfmt_args_using_game_clt(Protocols.Ingame.PLAYSKILLCARD_DONE)
                    if not self.receive_and_check_is_msgfmt_name_using_game_clt(Protocols.Ingame.OK):
                        print(f"Error: Did not receive OK")
                    break

                try:
                    skill_card_value = ord(skill_card) - ord('`') # 1 for a, 2 for b and so on
                    if not (1 <= skill_card_value <= 3):
                        print("Invalid input. Please enter \'a\', \'b\', or \'c\'.")
                        continue
                except TypeError:
                    print("Invalid input. Please enter \'a\', \'b\', or \'c\'.")
                    continue

                if skill_card_value < 1 or skill_card_value > 3:
                    print("Invalid skill card value. Try again.")
                    continue

                if use_skill_card_count[skill_card_value] >= 1:
                    print(f"You can only use each type of skill card once per turn. You have already chosen to use skill card {skill_card}.")
                    continue

                if self.player.each_skill_card_count[skill_card_value] <= 0:
                    print(f"You don't have enough of skill card {skill_card}. Try again.")
                    continue

                use_skill_card_count[skill_card_value] += 1
                self.player.each_skill_card_count[skill_card_value] -= 1
                print(f"You have chosen to use skill card {skill_card}.")
                print()

                self.send_msgfmt_args_using_game_clt(Protocols.Ingame.PLAYSKILLCARD, skill_card_value)
                result, = self.receive_msgfmt_and_parse_using_game_clt(Protocols.Ingame.SKILLCARDRESULT)

                time.sleep(2)

                print()
                match skill_card_value:
                    case 1:
                        # result = <number_of_cards>
                        
                        print(f"Opponent played {result} cards.")
                        
                    case 2:
                        # result = <minimum_card_value> and -1 if none
                        if result == -1:
                            print("Opponent has no cards played.")
                        else:
                            print(f"Minimum card value opponent played: {result}.")
                    case 3:
                        # result = 0 if done and -1 if none
                        if result == -1:
                            print("Opponent has no cards to destroy.")
                        elif result == 0:
                            print(f"Destroyed one of minimum card(s) opponent played.")
                        else:
                            print("Unexpected response from opponent.")
                    case _:
                        print("Invalid skill card value.")
                print()

                time.sleep(2)

                if use_skill_card_count == [0, 1, 1, 1]:
                    print()
                    print("You have chosen to use all available skill cards.")
                    print()
                    self.send_msgfmt_args_using_game_clt(Protocols.Ingame.PLAYSKILLCARD_DONE)
                    if not self.receive_and_check_is_msgfmt_name_using_game_clt(Protocols.Ingame.OK):
                        print("Error: did not received OK")
                    break
            except ConnectionResetError as e:
                print(f"Opponent disconnected when using skill cards: {e}")
                raise e
            except Exception as e:
                print(f"Error using skill card: {e}")
                raise e
            
    def take_skill_card_effects(self):
        while True:
            try:
                msg, fname = self.receive_and_get_msgfmt_name_using_game_clt()
                match fname:
                    case Protocols.Ingame.PLAYSKILLCARD_DONE.name:
                        self.send_msgfmt_args_using_game_clt(Protocols.Ingame.OK)
                        print("Opponent finished playing skill cards.")
                        break
                    case Protocols.Ingame.PLAYSKILLCARD.name:
                        skill_card_value, = self.parse_message(msg, Protocols.Ingame.PLAYSKILLCARD)
                        card_count_sum = len(self.player.this_round_played_card)
                        match skill_card_value:
                            case 1:
                                self.send_msgfmt_args_using_game_clt(Protocols.Ingame.SKILLCARDRESULT, card_count_sum)
                                print(f"Opponent used Quantity Seer, knowing you played {card_count_sum} cards.")
                            case 2:
                                if card_count_sum == 0:
                                    self.send_msgfmt_args_using_game_clt(Protocols.Ingame.SKILLCARDRESULT, -1)
                                    print("Opponent used Minimum Seer, knowing you have no cards played.")
                                else:
                                    card_min = min(self.player.this_round_played_card)
                                    self.send_msgfmt_args_using_game_clt(Protocols.Ingame.SKILLCARDRESULT, card_min)
                                    print(f"Opponent used Minimum Seer, knowing your minimum card value: {card_min}.")
                            case 3:
                                if card_count_sum == 0:
                                    self.send_msgfmt_args_using_game_clt(Protocols.Ingame.SKILLCARDRESULT, -1)
                                    print("Opponent used Minimum Destroyer, knowing you have no cards to destroy.")
                                else:
                                    card_min = min(self.player.this_round_played_card)
                                    self.player.this_round_played_card.remove(card_min)
                                    self.send_msgfmt_args_using_game_clt(Protocols.Ingame.SKILLCARDRESULT, 0)
                                    print(f"Opponent used Minimum Destroyer, destroying one of your minimum card value: {card_min}.")
                            case _:
                                print("Invalid skill card value from opponent.")
                    case _:
                        print("Unexpected message from opponent.")
            except ConnectionResetError as e:
                print(f"Opponent disconnected when using skill cards: {e}")
                raise e
            except Exception as e:
                print(f"Error receiving skill card effect: {e}")
                raise e
            
    def forfeit(self):
        self.send_msgfmt_using_game_clt(Protocols.Ingame.FORFEIT)
        if self.player.is_player_a:
            if not self.receive_and_check_is_msgfmt_name_using_game_clt(Protocols.Ingame.OK):
                print("Did not receive OK from opponent.")
        self.player_forfeit = True
        self.game_over = True
        self.this_game_winner = 'A' if self.opponent.is_player_a else 'B'
        # for debug
        # print(f"self.this_game_winner={self.this_game_winner}")

    def play_card(self):
        print()
        print("cards available: ")
        for i in range(1, 6):
            print(f"{self.player.each_card_count[i]} cards of value {i}")
        print()

        time.sleep(1)

        while True:
            # card_list : ['2', '2', '3'] means play two '2' cards and one '3' card
            # card_count : [0, 0, 2, 1, 0, 0] means play two '2' cards and one '3' card
            try:
                print()
                print("Enter the cards you want to play (e.g., '2 2 3' to play two '2's and one '3')")
                print("or press press Enter to pass (That is risky!).")
                print("Also, you can enter \'ff\' to forfeit the game:")
                card_str_list = input().strip().split()
                if card_str_list == ["ff"]:
                    confirm = input("Are you sure that you want to forfeit? (y/n): ")
                    if confirm.lower() == 'y':
                        self.forfeit()
                        print("You forfeited.")
                        return
                    else:
                        continue
                if len(card_str_list) > 3:
                    print("You cannot play more than 3 cards.")
                    continue

                card_int_list = []

                try:
                    card_int_list = list(map(int, card_str_list))
                    if any((card_value < 1 or card_value > 5) for card_value in card_int_list):
                        print("Card values must be between 1 and 5. Try again.")
                        continue
                    if any(card_int_list.count(i) > self.player.each_card_count[i] for i in range(1, 6)):
                        print("You don't have enough of one or more of those cards. Try again.")
                        continue
                except ValueError:
                    print("Invalid input. Please enter card values between 1 and 5.")
                    continue

                self.player.this_round_played_card = card_int_list.copy()
                self.player.each_card_count = [self.player.each_card_count[i] - card_int_list.count(i) for i in range(6)]
                self.send_msgfmt_args_using_game_clt(Protocols.Ingame.PLAYCARD_DONE) # we don't send the actual cards played to opponent until the round ends

                if self.player.is_player_a and not self.this_round_a_goes_first: # I am player A and I play second
                    if not self.receive_and_check_is_msgfmt_name_using_game_clt(Protocols.Ingame.OK):
                        print("Error: Did not receive OK from opponent.")
                break
            except ConnectionResetError as e:
                print(f"Opponent disconnected when playing cards: {e}")
                raise e
            except Exception as e:
                print(f"Error playing card: {e}")
                raise e

        print(f"You played: {' '.join(card_str_list)}")
        print()
        print("You now have:")
        for i in range(1, 6):
            print(f"{self.player.each_card_count[i]} cards of value {i}")
        print()
        if self.player.is_player_a != self.this_round_a_goes_first: # I play second
            print("Skill cards left:") 
            print(f"{self.player.each_skill_card_count[1]} Quantity Seer, ")
            print(f"{self.player.each_skill_card_count[2]} Minimum Seer, ")
            print(f"{self.player.each_skill_card_count[3]} Minimum Destroyer.")
        
    def run_round_complete_protocol(self):
        played_cards_list_m1 = self.player.this_round_played_card.copy()
        while len(played_cards_list_m1) < 3:
            played_cards_list_m1.append(-1)

        try:
            if self.player.is_player_a:
                self.send_msgfmt_args_using_game_clt(Protocols.Ingame.ROUNDCOMPLETED)
                opponent_card_list = self.receive_msgfmt_and_parse_using_game_clt(Protocols.Ingame.REPORTCARD)
                self.opponent.this_round_played_card = [card for card in opponent_card_list if card != -1]

                self.send_msgfmt_using_game_clt(Protocols.Ingame.REPORTCARD, played_cards_list_m1)
                if not self.receive_and_check_is_msgfmt_name_using_game_clt(Protocols.Ingame.OK):
                    print("Error: Did not receive OK from opponent.")
                    raise Exception("Did not receive OK from opponent.")
            else:
                if not self.receive_and_check_is_msgfmt_name_using_game_clt(Protocols.Ingame.ROUNDCOMPLETED):
                    print("Error: Did not receive ROUNDCOMPLETED from opponent.")
                    raise Exception("Did not receive ROUNDCOMPLETED from opponent.")
                self.send_msgfmt_using_game_clt(Protocols.Ingame.REPORTCARD, played_cards_list_m1)

                opponent_card_list = self.receive_msgfmt_and_parse_using_game_clt(Protocols.Ingame.REPORTCARD)
                self.opponent.this_round_played_card = [card for card in opponent_card_list if card != -1]
                self.send_msgfmt_args_using_game_clt(Protocols.Ingame.OK)
        except ConnectionResetError as e:
            print(f"Opponent disconnected when running round complete protocol: {e}")
            raise e
        except Exception as e:
            print(f"Error during round completion protocol: {e}")
            raise e
        
    def run_broadcast_round_result_protocol(self):
        try:
            if self.player.is_player_a:
                self.send_msgfmt_args_using_game_clt(Protocols.Ingame.ROUND_WINNER, self.this_round_winner)
                if not self.receive_and_check_is_msgfmt_name_using_game_clt(Protocols.Ingame.OK):
                    print("Error: Did not receive OK from opponent.")
                    raise Exception("Did not receive OK from opponent.")
                
                self.send_msgfmt_using_game_clt(Protocols.Ingame.NOW_POINTS, self.each_player_won_rounds)
                if not self.receive_and_check_is_msgfmt_name_using_game_clt(Protocols.Ingame.OK):
                    print("Error: Did not receive OK from opponent.")
                    raise Exception("Did not receive OK from opponent.")
            else:
                winner, = self.receive_msgfmt_and_parse_using_game_clt(Protocols.Ingame.ROUND_WINNER)
                if winner != self.this_round_winner:
                    print("Error: Winner mismatch.")
                    raise Exception("Winner mismatch.")
                self.send_msgfmt_args_using_game_clt(Protocols.Ingame.OK)

                points = self.receive_msgfmt_and_parse_using_game_clt(Protocols.Ingame.NOW_POINTS)

                if points != self.each_player_won_rounds:
                    print("Error: Points mismatch.")
                    raise Exception("Points mismatch.")
                self.send_msgfmt_args_using_game_clt(Protocols.Ingame.OK)
        except ConnectionResetError as e:
            print(f"Opponent disconnected when running round broadcasting: {e}")
            raise e
        except Exception as e:
            print(f"Error running broadcast match result protocol: {e}")
            raise e
            

    def evaluate_round(self):
        try:
            self.run_round_complete_protocol()
        except ConnectionResetError as e:
            print(f"Opponent disconnected when evaluating round: {e}")
            raise e
        except Exception as e:
            print(f"Error evaluating round: {e}")
            raise e
        
        sum_player = sum(self.player.this_round_played_card)
        sum_opponent = sum(self.opponent.this_round_played_card)

        print()
        print(f"You played: {' '.join(map(str, self.player.this_round_played_card))} (Total: {sum_player})")
        time.sleep(2)
        print(f"Opponent played: {' '.join(map(str, self.opponent.this_round_played_card))} (Total: {sum_opponent})")
        time.sleep(2)
        if sum_player > sum_opponent:
            self.this_round_winner = 'A' if self.player.is_player_a else 'B'
            print("You win this round!")
            self.each_player_won_rounds[0 if self.player.is_player_a else 1] += 1
        elif sum_player < sum_opponent:
            self.this_round_winner = 'B' if self.player.is_player_a else 'A'
            print("Opponent wins this round!")
            self.each_player_won_rounds[1 if self.player.is_player_a else 0] += 1
        else:
            if self.this_round_a_goes_first == self.player.is_player_a:
                self.this_round_winner = 'A' if self.player.is_player_a else 'B'
                print("It's a tie! But you went first, so you win this round!")
                self.each_player_won_rounds[0 if self.player.is_player_a else 1] += 1
            else:
                self.this_round_winner = 'B' if self.player.is_player_a else 'A'
                print("It's a tie! But opponent went first, so opponent wins this round!")
                self.each_player_won_rounds[1 if self.player.is_player_a else 0] += 1
        try:
            self.run_broadcast_round_result_protocol()
        except ConnectionResetError as e:
            print(f"Opponent disconnected when evaluating round: {e}")
            raise e
        except Exception as e:
            print(f"Error broadcasting round result: {e}")
            raise e
        print()
        time.sleep(3)
        print("Current round won:")
        time.sleep(2)
        print(f"Player A ({'You' if self.player.is_player_a else 'Opponent'}): {self.each_player_won_rounds[0]} rounds")
        time.sleep(2)
        print(f"Player B ({'You' if not self.player.is_player_a else 'Opponent'}): {self.each_player_won_rounds[1]} rounds")
        time.sleep(2)

        
    def run_broadcast_game_result_protocol(self):
        try:
            if self.player.is_player_a:
                self.send_msgfmt_args_using_game_clt(Protocols.Ingame.GAMEOVER)
                if not self.receive_and_check_is_msgfmt_name_using_game_clt(Protocols.Ingame.OK):
                    print("Error: Did not receive OK from opponent.")
                    raise Exception("Did not receive OK from opponent.")
                
                self.send_msgfmt_args_using_game_clt(Protocols.Ingame.GAME_WINNER, self.this_game_winner)
                if not self.receive_and_check_is_msgfmt_name_using_game_clt(Protocols.Ingame.OK):
                    print("Error: Did not receive OK from opponent.")
                    raise Exception("Did not receive OK from opponent.")
            else:
                if not self.receive_and_check_is_msgfmt_name_using_game_clt(Protocols.Ingame.GAMEOVER):
                    print("Error: Did not receive GAMEOVER from opponent.")
                    raise Exception("Did not receive GAMEOVER from opponent.")
                self.send_msgfmt_args_using_game_clt(Protocols.Ingame.OK)

                winner, = self.receive_msgfmt_and_parse_using_game_clt(Protocols.Ingame.GAME_WINNER)
                #for debug
                #print(f"winner={winner}")
                #print(f"self.this_game_winner={self.this_game_winner}")
                if winner != self.this_game_winner:
                    print("Error: game_winner mismatch.")
                    raise Exception("game_winner mismatch.")
                self.send_msgfmt_args_using_game_clt(Protocols.Ingame.OK)
        except ConnectionResetError as e:
            print(f"Opponent disconnected when running game result broadcasting: {e}")
            raise e
        except Exception as e:
            print(f"Error running game result protocol: {e}")
            raise e

            
    def conclude_game(self):
        if not self.opponent_disconnected and self.game_over: # normal end or someone forfeited
            if not self.player_forfeit and not self.opponent_forfeit: # no one forfeited
                if self.each_player_won_rounds[0] > self.each_player_won_rounds[1]:
                    self.this_game_winner = 'A'
                else:
                    self.this_game_winner = 'B'

            if self.player.is_player_a == (self.this_game_winner == 'A'):
                try:
                    self.send_win_message_and_wait_done()
                except Exception as e:
                    print("Error sending win message to lobby server.")
            try:
                self.run_broadcast_game_result_protocol()
            except Exception as e:
                print("Error broadcasting game result.")

            print()
            print()
            print()
            print("======================================== Game Over ========================================")
            print()
            print()
            print()
            time.sleep(2)
            forfeit_string_a = "(forfeited)" if (self.player_forfeit and self.player.is_player_a) or (self.opponent_forfeit and self.opponent.is_player_a) else ""
            print(f"Player A ({'You' if self.player.is_player_a else 'Opponent'}) won {self.each_player_won_rounds[0]} rounds. {forfeit_string_a}")
            time.sleep(2)
            forfeit_string_b = "(forfeited)" if (self.player_forfeit and not self.player.is_player_a) or (self.opponent_forfeit and not self.opponent.is_player_a) else ""
            print(f"Player B ({'You' if not self.player.is_player_a else 'Opponent'}) won {self.each_player_won_rounds[1]} rounds. {forfeit_string_b}")
            time.sleep(2)
            if self.this_game_winner == ('A' if self.player.is_player_a else 'B'):
                print("Congratulations! You won the game!")
            else:
                print("Sorry, you lost the game.")
            time.sleep(2)
            print("Thank you for playing!")
            time.sleep(1)
        else: #only case: self.opponent_disconnected and not self.game_over
            self.this_game_winner = 'A' if self.player.is_player_a else 'B'

            if self.player.is_player_a == (self.this_game_winner == 'A'):
                try:
                    self.send_win_message_and_wait_done()
                except Exception as e:
                    print("Error sending win message to lobby server.")

            print("Opponent disconnected, treated as forfeit.")
            time.sleep(2)
            print("You won the game!")
            time.sleep(2)
            print("Thank you for playing!")
            time.sleep(1) 



    def send_msgfmt_args_using_game_clt(self, msgfmt: MessageFormat, *args):
        try:
            self.send_message_format_args(self.game_client_tcp_sock, msgfmt, *args)
        except ConnectionResetError as e:
            print(f"Opponent disconnected: {e}")
            raise e
        except Exception as e:
            print(f"Error sending message format: {e}")
            raise e
        
    def send_msgfmt_using_game_clt(self, msgfmt: MessageFormat, arg_list: list = []):
        try:
            self.send_message_format(self.game_client_tcp_sock, msgfmt, arg_list)
        except ConnectionResetError as e:
            print(f"Opponent disconnected: {e}")
            raise e
        except Exception as e:
            print(f"Error sending message format: {e}")
            raise e
        
    def receive_and_get_msgfmt_name_using_game_clt(self) -> tuple[str, str]:
        try:
            msg, fname = self.receive_and_get_format_name(self.game_client_tcp_sock)
            return (msg, fname)
            #data = self.game_client_tcp_sock.recv(buffer_size)
        except ConnectionResetError as e:
            print(f"Opponent disconnected: {e}")
            raise e
        except Exception as e:
            print(f"Error receiving message format: {e}")
            raise e

    def receive_and_check_is_msgfmt_name_using_game_clt(self, msgfmt: MessageFormat) -> bool:
        try:
            return self.receive_and_check_is_message_format_name(self.game_client_tcp_sock, msgfmt)
        except ConnectionResetError as e:
            print(f"Opponent disconnected: {e}")
            raise e
        except Exception as e:
            print(f"Error receiving message format and check: {e}")
            raise e
        
    def receive_msgfmt_and_parse_using_game_clt(self, msgfmt: MessageFormat) -> list:
        try:
            return self.receive_message_format_and_parse(self.game_client_tcp_sock, msgfmt)
        except ConnectionResetError as e:
            print(f"Opponent disconnected: {e}")
            raise e
        except Exception as e:
            print(f"Error receiving message format and check: {e}")
            raise e
    
    def send_win_message_and_wait_done(self):
        try:
            self.send_message_format(self.lobby_tcp_sock, Protocols.Command.RECORD_WIN)
            if not self.receive_and_check_is_message_format_name(self.lobby_tcp_sock, Protocols.Response.WIN_RECORD_DONE):
                raise Exception("Did not receive WIN_RECORD_DONE.")
        except Exception as e:
            print(f"Error sending win message: {e}")
            raise e