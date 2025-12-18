from __future__ import annotations

class Player:
    MAX_HEALTH = 40
    INIT_REVIVE_TIME = 15.0
    INCREASED_REVIVE_TIME = 5.0
    def __init__(self, player_id: str) -> None:
        self.health: int = Player.MAX_HEALTH
        self.revive_time: float = 0.0 #0.0 means alive, >0.0 means dead
        self.player_id: str = player_id
        self.death_count: int = 0
        self.score: int = 0
    def is_alive(self) -> bool:
        return self.revive_time == 0.0
    def die(self) -> None:
        self.health = 0
        self.revive_time = Player.INIT_REVIVE_TIME + (self.death_count * Player.INCREASED_REVIVE_TIME)
        self.death_count += 1
    def revive(self) -> None:
        self.health = Player.MAX_HEALTH
        self.revive_time = 0.0
    def take_damage(self, damage: int) -> None:
        if self.is_alive():
            self.health -= damage
            if self.health <= 0:
                self.die()
    def heal(self, amount: int) -> None:
        if self.is_alive():
            self.health += amount
            if self.health > Player.MAX_HEALTH:
                self.health = Player.MAX_HEALTH
    def update(self, delta_time: float) -> None:
        if not self.is_alive():
            self.revive_time -= delta_time
            if self.revive_time <= 0.0:
                self.revive()
    def add_score(self, points: int) -> None:
        self.score += points

    def process_cleared_cells(self, cleared_cells: list[int], opponent: Player) -> None:
        # cleared_cells: [empty, score, heal, attack]
        self.add_score(cleared_cells[1])
        self.heal(cleared_cells[2])
        opponent.take_damage(cleared_cells[3])

        

