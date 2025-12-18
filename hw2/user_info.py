class UserInfo:
    def __init__(self):
        self.name: str | None = None
        self.current_room_id: str | None = None
        self.is_room_owner: bool = False
        self.users_inviting_me: set = set()
        self.is_spectating: bool = False
        #self.current_game: str | None = None

    def reset(self) -> None:
        self.name = None
        self.current_room_id = None
        self.is_room_owner = False
        self.users_inviting_me.clear()
        self.is_spectating = False
        #self.current_game = None