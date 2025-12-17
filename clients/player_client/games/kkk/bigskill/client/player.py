class Player:
    def __init__(self):
        self.is_player_a = True  # True if player A, False if player B
        self.each_card_count = [0, 3, 3, 3, 3, 3]
        self.each_skill_card_count = [0, 2, 2, 2] # [not used, Know how many cards opponent's played, Know the minimum number of cards opponent's played, Throw away one minimum card opponent's played]
        self.this_round_played_card = []
