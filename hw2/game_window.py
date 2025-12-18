import pygame
import pygame.freetype
from message_format_passer import MessageFormatPasser
from protocols import Protocols, Words
from player_info import PlayerInfo
from tetris import Tetris
from piece import Pieces
import threading
import time

class GameWindow:
    def __init__(self, width=800, height=600, title="Game Window", game_server_passer: MessageFormatPasser | None = None, player_id: str | None = None):
        pygame.init()
        self.screen = pygame.display.set_mode((width, height))
        self.game_update_lock = threading.Lock()
        self.game_update_temp: dict = {}
        pygame.display.set_caption(title)
        self.font = pygame.freetype.SysFont("Consolas", 20)
        self.small_font = pygame.freetype.SysFont("Consolas", 15)
        self.game_server_passer = game_server_passer
        self.game_started = True
        self.game_playing = False
        self.game_over = False
        self.game_over_time_remaining = 5.0  # seconds
        self.time_stamp: float = time.time()
        self.player_id = player_id
        #self.is_spectator = is_spectator
        self.running = True

        self.player1_info: PlayerInfo | None = None
        self.player2_info: PlayerInfo | None = None

        self.goal_score: int | None = None

        # rendering parameters
        self.CELL_SIZE = 20
        self.CELL_PADDING = 1
        self.PREVIEW_SCALE = 0.6

    def init_player_info(self, player1_username, player2_username, player_health, now_piece, next_pieces, goal_score):
        self.player1_info = PlayerInfo(player1_username, player_health, now_piece, 1, (0, 4), next_pieces)
        self.player2_info = PlayerInfo(player2_username, player_health, now_piece, 1, (0, 4), next_pieces)

        self.goal_score = goal_score

    def draw_text(self, text, position, color=(255, 255, 255)):
        self.font.render_to(self.screen, position, text, color)

    def draw_small_text(self, text, position, color=(255, 255, 255)):
        self.small_font.render_to(self.screen, position, text, color)

    def _color_from_index(self, idx: int):
        # map numeric color/index to an RGB tuple; extend as needed
        palette = {
            0: (20, 20, 20),      # empty background
            1: (255, 200, 100),   # score / light orange
            2: (120, 255, 140),   # heal / green
            3: (255, 120, 120),   # attack / red
        }
        if idx in palette:
            return palette[idx]
        r = (idx * 47) % 200 + 30
        g = (idx * 97) % 200 + 30
        b = (idx * 151) % 200 + 30
        return (r, g, b)
    
    def draw_board(self, board: str, topleft: tuple[int, int], is_my_board: bool | None = None):
        if board is None:
            return
        
        board_int_list = Tetris.from_board_string(board)
        rows = len(board_int_list)
        cols = len(board_int_list[0]) if rows > 0 else 0
        cx, cy = topleft
        cell = self.CELL_SIZE
        pad = self.CELL_PADDING

        border_color = (0, 0, 0)
        empty_cell_color = (0, 0, 0)
        if is_my_board is not None:
            if is_my_board:
                border_color = (40, 40, 60) # a little blueish
                empty_cell_color = (20, 20, 30) # dark blueish
            else:
                border_color = (60, 40, 40) # a little reddish
                empty_cell_color = (30, 20, 20) # dark reddish
        else:
            border_color = (50, 50, 50) # neutral gray
            empty_cell_color = (20, 20, 20) # neutral dark
        pygame.draw.rect(self.screen, border_color, (cx - 2, cy - 2, cols * cell + 4, rows * cell + 4)) # board border

        for r in range(rows):
            for c in range(cols):
                val = board_int_list[r][c]
                if val == 0:
                    color = empty_cell_color
                else:
                    color_idx = val if isinstance(val, int) else 1
                    color = self._color_from_index(color_idx)
                rect = (cx + c * cell + pad, cy + r * cell + pad, cell - 2*pad, cell - 2*pad)
                pygame.draw.rect(self.screen, color, rect) # draw cell
                pygame.draw.rect(self.screen, (15, 15, 15), rect, 1) # cell border

    def draw_piece(self, shape: list[list[int]], position: tuple[int, int], color_idx: int, topleft: tuple[int, int]):
        if shape is None or position is None:
            return
        board_cx, board_cy = topleft
        cell = self.CELL_SIZE
        pad = self.CELL_PADDING
        color = self._color_from_index(color_idx or 1)
        for r in range(len(shape)):
            for c in range(len(shape[0])):
                if shape[r][c]:
                    br = position[0] + r
                    bc = position[1] + c
                    rect = (board_cx + bc * cell + pad, board_cy + br * cell + pad, cell - 2*pad, cell - 2*pad)
                    pygame.draw.rect(self.screen, color, rect)
                    pygame.draw.rect(self.screen, (15, 15, 15), rect, 1)

    def draw_next_pieces(self, next_pieces: list[str], topleft: tuple[int, int]):
        if not next_pieces:
            return
        px, py = topleft
        cell = int(self.CELL_SIZE * self.PREVIEW_SCALE)
        pad = 2
        for i, p in enumerate(next_pieces): # next pieces: ["O", "I", ...]
            shape = None
            match p:
                case "T":
                    shape = Pieces.T.shape
                case "I":
                    shape = Pieces.I.shape
                case "O":
                    shape = Pieces.O.shape
                case "L":
                    shape = Pieces.L.shape
                case "J":
                    shape = Pieces.J.shape
                case "S":
                    shape = Pieces.S.shape
                case "Z":
                    shape = Pieces.Z.shape
            sx = px
            sy = py + i * (cell * 3 + 8)
            if shape is not None:
                for r in range(len(shape)):
                    for c in range(len(shape[0])):
                        if shape[r][c]:
                            rect = (sx + c * cell + pad, sy + r * cell + pad, cell - 2*pad, cell - 2*pad)
                            pygame.draw.rect(self.screen, (200, 200, 200), rect) # next piece color can be fixed
                            pygame.draw.rect(self.screen, (15, 15, 15), rect, 1)

    def draw_health_bar(self, x, y, health, max_health=40, width=160, height=14, is_my_health: bool | None = None):
        if health is None:
            health = 0
        ratio = max(0.0, min(1.0, health / max_health))
        pygame.draw.rect(self.screen, (60, 60, 60), (x, y, width, height)) # dark background
        health_color = (0, 0, 0)
        if is_my_health is not None:
            health_color = (50, 180, 50) if is_my_health else (180, 50, 50)
        else:
            health_color = (180, 180, 50) # neutral yellowish
        pygame.draw.rect(self.screen, health_color, (x + 2, y + 2, int((width - 4) * ratio), height - 4)) # health color
        pygame.draw.rect(self.screen, (180, 180, 180), (x, y, width, height), 1) # border
        # Draw health text
        health_text = f"Health: {health}/{max_health}"
        self.draw_small_text(health_text, (x + 2, y + height + 2))

    def draw_score_bar(self, x, y, score, goal_score=300, width=160, height=14):
        if score is None:
            score = 0
        ratio = max(0.0, min(1.0, score / goal_score))
        pygame.draw.rect(self.screen, (60, 60, 60), (x, y, width, height))
        pygame.draw.rect(self.screen, (255, 200, 100), (x + 2, y + 2, int((width - 4) * ratio), height - 4)) # orange color
        pygame.draw.rect(self.screen, (180, 180, 180), (x, y, width, height), 1)
        # Draw score text
        score_text = f"Score: {score}/{goal_score}"
        self.draw_small_text(score_text, (x + 2, y + height + 2))

    def update(self):
        now_time = time.time()
        delta_time = now_time - self.time_stamp
        self.time_stamp = now_time
        # clear background
        self.screen.fill((10, 10, 10))

        p1_name = self.player1_info.username if self.player1_info else ""
        p2_name = self.player2_info.username if self.player2_info else ""
        p1_text = f"{p1_name}"
        p2_text = f"{p2_name}"
        if self.player_id == "player1":
            p1_text += " (You)"
            p2_text += " (Opponent)"
        elif self.player_id == "player2":
            p1_text += " (Opponent)"
            p2_text += " (You)"
        else:
            self.draw_text("Spectator Mode", (350, 570), color=(200, 200, 50))
        self.draw_text(f"Player 1: {p1_text}", (20, 8))
        self.draw_text(f"Player 2: {p2_text}", (420, 8))

        # fetch latest network update (one-shot)
        update = None
        with self.game_update_lock:
            if self.game_update_temp:
                update = self.game_update_temp.copy()

        if update:
            if not self.game_playing:
                self.game_playing = True

            state1 = update.get('state1')
            state2 = update.get('state2')
            data = update.get('data', {})

            board_left = (20, 50)
            board_right = (420, 50)

            if state1:
                p1_board = state1.get('board', "")
                self.draw_board(p1_board, board_left, is_my_board=None if self.player_id == 'spectator' else (self.player_id == "player1"))
                now_piece1 = state1.get('now_piece')
                now_piece1_color = state1.get('color', 1)
                now_piece1_pos = state1.get('position')
                # now_piece1 is just a list like [[0,1,0],[1,1,1],[0,0,0]]
                self.draw_piece(now_piece1, now_piece1_pos, now_piece1_color, board_left)
                self.draw_next_pieces(state1.get('next_pieces'), (20 + 10 * self.CELL_SIZE, 50))

                board_rows = len(p1_board.splitlines())
                p1_score = state1.get('score', 0)
                self.draw_score_bar(20, 50 + board_rows * self.CELL_SIZE + 75, p1_score, self.goal_score or 300)
                p1_health = state1.get('health', 100)
                self.draw_health_bar(20, 50 + board_rows * self.CELL_SIZE + 36, p1_health, is_my_health=None if self.player_id == 'spectator' else (self.player_id == "player1"))
                
                p1_revive_time = state1.get('revive_time', 0)
                if p1_revive_time > 0:
                    text_color = (255, 100, 100) if self.player_id == "player1" else (200, 200, 200)
                    if self.player_id == 'spectator':
                        text_color = (200, 200, 50)
                    self.draw_text(f"Reviving in: {p1_revive_time:.1f}s", (20, 50 + board_rows * self.CELL_SIZE // 2), color=text_color) # center of board

                

            if state2:
                p2_board = state2.get('board', "")
                self.draw_board(p2_board, board_right, is_my_board=None if self.player_id == 'spectator' else (self.player_id == "player2"))
                now_piece2 = state2.get('now_piece')
                now_piece2_color = state2.get('color', 1)
                now_piece2_pos = state2.get('position')
                self.draw_piece(now_piece2, now_piece2_pos, now_piece2_color, board_right)
                self.draw_next_pieces(state2.get('next_pieces'), (420 + 10 * self.CELL_SIZE, 50))

                board_rows = len(p2_board.splitlines())
                p2_score = state2.get('score', 0)
                self.draw_score_bar(420, 50 + board_rows * self.CELL_SIZE + 75, p2_score, self.goal_score or 300)
                p2_health = state2.get('health', 100)
                self.draw_health_bar(420, 50 + board_rows * self.CELL_SIZE + 36, p2_health, is_my_health=None if self.player_id == 'spectator' else (self.player_id == "player2"))
                
                p2_revive_time = state2.get('revive_time', 0)
                if p2_revive_time > 0:
                    text_color = (255, 100, 100) if self.player_id == "player2" else (200, 200, 200)
                    if self.player_id == 'spectator':
                        text_color = (200, 200, 50)
                    self.draw_text(f"Reviving in: {p2_revive_time:.1f}s", (420, 50 + board_rows * self.CELL_SIZE // 2), color=text_color) # center of board

            

            if 'game_over' in data and not self.game_over:
                self.game_over = True
            if self.game_over:
                self.game_over_time_remaining -= delta_time
                if 'winner' in data and 'message' in data:
                    self.draw_text(f"Game Over! Winner: {data.get('winner')} ({data.get('message')})", (150, 150), color=(255, 255, 255))
                elif 'winner' in data:
                    self.draw_text(f"Game Over! Winner: {data.get('winner')}", (250, 250), color=(255, 255, 255))
                elif 'message' in data:
                    self.draw_text(f"Game Over! {data.get('message')}", (150, 150), color=(255, 255, 255))
                
                if self.game_over_time_remaining <= 0:
                    self.running = False
        else:
            self.draw_text("Waiting for game data...", (250, 250), color=(200, 200, 200))
                

        pygame.display.flip()
        

    def run(self):
        clock = pygame.time.Clock()
        try:
            while self.running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    if self.game_started and not self.game_over and self.game_playing and self.player_id in ["player1", "player2"]:
                        if event.type == pygame.KEYDOWN:
                            if self.game_server_passer and self.player_id:
                                key_action = None
                                color = None
                                match event.key:
                                    case pygame.K_LEFT:
                                        key_action = Words.GameAction.MOVE_LEFT
                                    case pygame.K_RIGHT:
                                        key_action = Words.GameAction.MOVE_RIGHT
                                    case pygame.K_DOWN:
                                        key_action = Words.GameAction.SOFT_DROP
                                    case pygame.K_UP:
                                        key_action = Words.GameAction.ROTATE
                                    case pygame.K_SPACE:
                                        key_action = Words.GameAction.HARD_DROP
                                    case pygame.K_z:
                                        key_action = Words.GameAction.CHANGE_COLOR
                                        color = 1  # example: change to color index 1
                                    case pygame.K_x:
                                        key_action = Words.GameAction.CHANGE_COLOR
                                        color = 2  # example: change to color index 2
                                    case pygame.K_c:
                                        key_action = Words.GameAction.CHANGE_COLOR
                                        color = 3  # example: change to color index 3

                                if key_action:
                                    if color is not None:
                                        self.game_server_passer.send_args(Protocols.PlayerToGameServer.GAME_ACTION, key_action, {"color": color})
                                        print(f"Sent action: {key_action} with color {color}")
                                    else:
                                        self.game_server_passer.send_args(Protocols.PlayerToGameServer.GAME_ACTION, key_action, {})
                                        print(f"Sent action: {key_action}")
                
                self.update()
                clock.tick(60)
        except Exception as e:
            print(f"Exception in GameWindow run loop: {e}")

        if self.game_server_passer is not None:
            try:
                self.game_server_passer.close()
            except Exception as e:
                print(f"Error closing game server passer: {e}")
        pygame.quit()