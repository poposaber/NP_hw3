from player import Player
from tetris import Tetris
from protocols import Words

class Game:
    def __init__(self, seed: int) -> None:
        self.player1: Player = Player("player1")
        self.player2: Player = Player("player2")
        self.tetris1: Tetris = Tetris(gravity_time=1.0, seed=seed)
        self.tetris2: Tetris = Tetris(gravity_time=1.0, seed=seed)
        self.goal_score: int = 50
        self.seed: int = seed
        self.gameover: bool = False
        self.winner: str | None = None


    def handle_player_action(self, player_id: str, action: str, data: dict) -> None:
        print(f"Handling action from {player_id}: {action} with data {data}")
        if player_id == "player1":
            if not self.player1.is_alive():
                print("Player 1 is dead, action ignored.")
                return
            tetris = self.tetris1
        else:
            if not self.player2.is_alive():
                print("Player 2 is dead, action ignored.")
                return
            tetris = self.tetris2
        match action:
            case Words.GameAction.MOVE_LEFT:
                if tetris.now_piece_can_move("left"):
                    tetris.now_piece.move("left")
            case Words.GameAction.MOVE_RIGHT:
                if tetris.now_piece_can_move("right"):
                    tetris.now_piece.move("right")
            case Words.GameAction.ROTATE:
                tetris.try_rotate_now_piece()
            case Words.GameAction.SOFT_DROP:
                tetris.drop_piece_one_step()
            case Words.GameAction.HARD_DROP:
                tetris.hard_drop_piece()
            case Words.GameAction.CHANGE_COLOR:
                tetris.change_now_piece_color(data.get("color", 1))

    def update(self, delta_time: float) -> None:
        if self.gameover:
            return
        
        self.tetris1.update(delta_time)
        self.tetris2.update(delta_time)

        cleared_cells1 = self.tetris1.get_recent_cleared_cells()
        cleared_cells2 = self.tetris2.get_recent_cleared_cells()

        if sum(cleared_cells1) > 0:
            self.player1.process_cleared_cells(cleared_cells1, self.player2)
            self.tetris1.clear_recent_cleared_cells()
        if sum(cleared_cells2) > 0:
            self.player2.process_cleared_cells(cleared_cells2, self.player1)
            self.tetris2.clear_recent_cleared_cells()

        if self.tetris1.board_dead and not self.tetris1.paused:
            self.player1.die()

        if self.tetris2.board_dead and not self.tetris2.paused:
            self.player2.die()

        self.player1.update(delta_time)
        self.player2.update(delta_time)

        if not self.player1.is_alive() and not self.tetris1.paused:
            self.tetris1.paused = True
        elif self.player1.is_alive() and self.tetris1.paused:
            if self.tetris1.board_dead:
                self.tetris1.clear_board()
                self.tetris1.board_dead = False
            self.tetris1.paused = False
        if not self.player2.is_alive() and not self.tetris2.paused:
            self.tetris2.paused = True
        elif self.player2.is_alive() and self.tetris2.paused:
            if self.tetris2.board_dead:
                self.tetris2.clear_board()
                self.tetris2.board_dead = False
            self.tetris2.paused = False

        if self.player1.score >= self.goal_score and not self.gameover:
            self.gameover = True
            self.winner = "player1"
        elif self.player2.score >= self.goal_score and not self.gameover:
            self.gameover = True
            self.winner = "player2"

    def get_board_string(self, player_id: str) -> str:
        if player_id == "player1":
            tetris = self.tetris1
        else:
            tetris = self.tetris2
        return Tetris.to_board_string(tetris.board)

        