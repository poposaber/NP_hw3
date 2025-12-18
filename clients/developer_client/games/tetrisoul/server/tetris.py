from piece import Piece, Pieces
import random

class Tetris:
    SIZE = [20, 10] # height, width
    PIECE_LIST = [Pieces.T, Pieces.I, Pieces.O, Pieces.L, Pieces.J, Pieces.S, Pieces.Z]
    def __init__(self, gravity_time: float, seed: int) -> None:
        self.board = [[0 for _ in range(Tetris.SIZE[1])] for _ in range(Tetris.SIZE[0])] # self.board[<row>][<col>]; 0 means empty cell, 1 means score cell, 2 means heal cell, 3 means attack cell
        self.seed = seed
        self.rng = random.Random(seed)
        self.now_piece: Piece = self.rng.choice(Tetris.PIECE_LIST).copy()
        self.next_piece_list: list[Piece] = [self.rng.choice(Tetris.PIECE_LIST).copy() for _ in range(3)]
        self.gravity_time: float = gravity_time
        self.gravity_timer: float = 0.0
        self.paused: bool = False
        self.recent_cleared_cells: list[int] = [0, 0, 0, 0] # index 0: empty, 1: score, 2: heal, 3: attack
        self.board_dead: bool = False


    def clear_board(self) -> None:
        for row in range(Tetris.SIZE[0]):
            for col in range(Tetris.SIZE[1]):
                self.board[row][col] = 0

    def hard_drop_piece(self) -> None:
        if self.now_piece is not None:
            while self.now_piece_can_move("down"):
                self.now_piece.move("down")
            self.lock_piece()

    def drop_piece_one_step(self) -> None:
        if self.now_piece is not None and self.now_piece_can_move("down"):
            self.now_piece.move("down")
            #print("Dropped piece one step down")
        else:
            self.lock_piece()

    def change_now_piece_color(self, color: int) -> None:
        if self.now_piece is not None:
            self.now_piece.color = color

    def check_collide(self, piece: Piece) -> bool:
        if piece is None:
            return False
        for r in range(len(piece.shape)):
            for c in range(len(piece.shape[0])):
                if piece.shape[r][c] != 0:
                    board_row = piece.position[0] + r
                    board_col = piece.position[1] + c
                    if (board_row < 0 or board_row >= Tetris.SIZE[0] or
                        board_col < 0 or board_col >= Tetris.SIZE[1] or
                        self.board[board_row][board_col] != 0):
                        return True
        return False

    def now_piece_can_rotate(self) -> bool:
        temp_piece = Piece([row[:] for row in self.now_piece.shape], self.now_piece.position, self.now_piece.type_name) # fix here
        temp_piece.rotate()
        return not self.check_collide(temp_piece)
    
    def try_rotate_now_piece(self) -> None:
        temp_piece = Piece([row[:] for row in self.now_piece.shape], self.now_piece.position, self.now_piece.type_name)
        temp_piece.rotate()
        if not self.check_collide(temp_piece):
            self.now_piece.rotate()
        else:
            # Try wall kicks
            temp_pos = temp_piece.position
            for shift in [-1, 1, -2, 2]:
                temp_piece.position = (temp_pos[0], temp_pos[1] + shift)
                if not self.check_collide(temp_piece):
                    self.now_piece.position = (self.now_piece.position[0], self.now_piece.position[1] + shift)
                    self.now_piece.rotate()
                    break


    def now_piece_can_move(self, direction: str) -> bool:
        temp_piece = Piece([row[:] for row in self.now_piece.shape], self.now_piece.position, self.now_piece.type_name)
        temp_piece.move(direction)
        return not self.check_collide(temp_piece)

    def try_move_now_piece(self, direction: str) -> None:
        if self.now_piece is not None and self.now_piece_can_move(direction):
            self.now_piece.move(direction)

    def lock_piece(self) -> None:
        if self.now_piece is not None:
            pre_color = self.now_piece.color
            for r in range(len(self.now_piece.shape)):
                for c in range(len(self.now_piece.shape[0])):
                    if self.now_piece.shape[r][c] != 0:
                        board_row = self.now_piece.position[0] + r
                        board_col = self.now_piece.position[1] + c
                        if 0 <= board_row < Tetris.SIZE[0] and 0 <= board_col < Tetris.SIZE[1]:
                            self.board[board_row][board_col] = self.now_piece.shape[r][c] * pre_color
            self.now_piece = self.next_piece_list.pop(0)
            self.now_piece.color = pre_color
            self.next_piece_list.append(self.rng.choice(Tetris.PIECE_LIST).copy())
            if self.check_collide(self.now_piece):
                self.board_dead = True
            self.gravity_timer = 0.0

    def clear_full_lines(self) -> None:
        """Clears full lines from the board and updates the recent cleared cells."""
        each_total_cells_cleared = [0, 0, 0, 0] # index 0: empty, 1: score, 2: heal, 3: attack
        row_index = Tetris.SIZE[0] - 1 # start from bottom row, go up, to avoid skipping rows after deletion
        for row in range(Tetris.SIZE[0] - 1, -1, -1):
            temp_cell_list = [0, 0, 0, 0] # index 0: empty, 1: score, 2: heal, 3: attack
            is_full_line = True
            for cell in self.board[row]:
                if cell == 0:
                    is_full_line = False
                    break
                else:
                    temp_cell_list[cell] += 1
            if is_full_line:
                for i in range(1, 4): # only count score, heal, attack cells
                    each_total_cells_cleared[i] += temp_cell_list[i]
                self.board[row] = [0 for _ in range(Tetris.SIZE[1])]
            else:
                self.board[row_index] = self.board[row].copy() # move down non-full line, use copy to avoid reference issue
                row_index -= 1
        for r in range(row_index, -1, -1):
            self.board[r] = [0 for _ in range(Tetris.SIZE[1])] # fill the top empty rows
        self.recent_cleared_cells = each_total_cells_cleared
    
    def update(self, delta_time: float) -> None:
        if self.paused:
            return
        self.gravity_timer += delta_time
        if self.gravity_timer >= self.gravity_time:
            self.drop_piece_one_step()
            self.gravity_timer = 0.0
        self.clear_full_lines()

    def get_recent_cleared_cells(self) -> list[int]:
        return self.recent_cleared_cells
    
    def clear_recent_cleared_cells(self) -> None:
        self.recent_cleared_cells = [0, 0, 0, 0]

    @staticmethod
    def to_board_string(board: list[list[int]]) -> str:
        """Convert the board to a string representation."""
        board_str = ""
        for row in board:
            for cell in row:
                board_str += str(cell)
            board_str += "\n"
        return board_str

    @staticmethod
    def from_board_string(board_str: str) -> list[list[int]]:
        """Convert a string representation of the board back to a 2D list."""
        board = []
        for row in board_str.splitlines():
            board.append([int(cell) for cell in row])
        return board
