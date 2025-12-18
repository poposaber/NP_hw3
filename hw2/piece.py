# this class defines a piece in Tetris
from __future__ import annotations

class Piece:
    def __init__(self, shape: list[list[int]], position: tuple[int, int], type_name: str) -> None:
        self.shape = shape  # 2D list representing the piece shape, for example: [[1, 1, 1], [0, 1, 0]] for a T shape
        self.position = position  # (row, col) position on the board, top-left corner of the piece
        self.color = 1  # default color index; can be modified as needed
        self.type_name = type_name

    def rotate(self) -> None:
        # Rotate the piece 90 degrees clockwise
        self.shape = [list(row) for row in zip(*self.shape[::-1])]

    def move(self, direction: str) -> None:
        # Move the piece in the specified direction
        if direction == "left":
            self.position = (self.position[0], self.position[1] - 1)
        elif direction == "right":
            self.position = (self.position[0], self.position[1] + 1)
        elif direction == "down":
            self.position = (self.position[0] + 1, self.position[1])

    def copy(self) -> Piece:
        return Piece([row[:] for row in self.shape], self.position, self.type_name)

class Pieces:
    T = Piece([[0, 1, 0], 
               [1, 1, 1],
               [0, 0, 0]], (0, 4), "T")
    
    I = Piece([[0, 0, 0, 0], 
               [1, 1, 1, 1], 
               [0, 0, 0, 0], 
               [0, 0, 0, 0]], (0, 4), "I")

    O = Piece([[1, 1], 
               [1, 1]], (0, 4), "O")

    L = Piece([[1, 0, 0], 
               [1, 1, 1], 
               [0, 0, 0]], (0, 4), "L")

    J = Piece([[0, 0, 1], 
               [1, 1, 1], 
               [0, 0, 0]], (0, 4), "J")

    S = Piece([[0, 1, 1], 
               [1, 1, 0], 
               [0, 0, 0]], (0, 4), "S")

    Z = Piece([[1, 1, 0], 
               [0, 1, 1], 
               [0, 0, 0]], (0, 4), "Z")