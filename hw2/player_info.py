class PlayerInfo:
    def __init__(self, username: str, max_health: int, now_piece: str, now_piece_color: int, now_piece_position: tuple[int, int], next_pieces: list[str]) -> None:
        self.username = username
        self.max_health = max_health
        self.health = max_health
        self.revive_time: float = 0.0  # 0.0 means alive, >0.0 means dead
        self.now_piece = now_piece
        self.now_piece_color = now_piece_color
        self.now_piece_position = now_piece_position
        self.next_pieces = next_pieces
        self.score: int = 0
        self.board: list[list[int]] = []  # 2D list representing the Tetris board