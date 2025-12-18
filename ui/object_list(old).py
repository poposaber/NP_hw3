import customtkinter
import tkinter
from typing import Callable, Iterable

ROW_HEIGHT = 48
LABEL_FONT = ("Arial", 14)
BTN_WIDTH = 100
PAD_X = 8
PAD_Y = 6

class ObjectList(customtkinter.CTkScrollableFrame):
    """
    A generic scrollable list:
    - Left: item label
    - Right: action buttons
    Store items by a unique key (e.g., username, room_id).
    """
    def __init__(self, master, width=800, height=520, **kwargs):
        super().__init__(master=master, width=width, height=height, **kwargs)
        self.configure(width=width, height=height)
        # Ensure children can expand horizontally (relative width = 1)
        # try:
        #     self._scrollable_frame.grid_columnconfigure(0, weight=1)
        # except Exception:
            # Fallback if internal name changes in future versions
        # prefer configuring internal scrollable frame if available
        parent_container = getattr(self, "_scrollable_frame", None)
        if parent_container is not None:
            try:
                parent_container.grid_columnconfigure(0, weight=1)
            except Exception:
                pass
            print(f"[ObjectList] using internal _scrollable_frame as parent: {type(parent_container)}")
        else:
            self.grid_columnconfigure(0, weight=1)
        self._rows: dict[str, dict] = {}  # key -> {frame, label, btns(list), btn_bar}

    def clear(self):
        for row in list(self._rows.values()):
            try:
                print(f"[ObjectList] clearing row {row['label'].cget('text')}")
                row["frame"].destroy()
            except Exception:
                pass
        self._rows.clear()

    def remove_item(self, key: str):
        row = self._rows.pop(key, None)
        if row:
            try:
                row["frame"].destroy()
            except Exception:
                pass

    def add_item(
        self,
        key: str,
        text: str,
        actions: Iterable[tuple[str, Callable[[], None] | None, bool]] = (),
    ):
        """
        actions: iterable of (button_text, callback, enabled)
        """
        if key in self._rows:
            self.update_item_text(key, text)
            self.update_item_actions(key, actions)
            return

        # Full-width horizontal strip with fixed height
        # place rows inside internal scrollable frame if present
        parent_container = getattr(self, "_scrollable_frame", self)
        row = customtkinter.CTkFrame(parent_container, height=ROW_HEIGHT)
        row.grid(sticky="ew", padx=PAD_X, pady=PAD_Y)
        row.grid_propagate(False)  # keep fixed height
        row.grid_columnconfigure(0, weight=1)  # label expands
        row.grid_columnconfigure(1, weight=0)  # buttons fixed

        lbl = customtkinter.CTkLabel(row, text=text, font=LABEL_FONT)
        lbl.grid(row=0, column=0, sticky="w", padx=PAD_X, pady=PAD_Y)

        btn_bar = customtkinter.CTkFrame(row, fg_color="transparent")
        btn_bar.grid(row=0, column=1, sticky="e", padx=PAD_X, pady=PAD_Y)

        btns: list[customtkinter.CTkButton] = []
        for (btn_text, cb, enabled) in actions:
            btn = customtkinter.CTkButton(
                btn_bar, text=btn_text, width=BTN_WIDTH,
                command=(cb if cb else None)
            )
            btn.grid(row=0, column=len(btns), padx=6)
            btn.configure(state=("normal" if enabled else "disabled"))
            btns.append(btn)
        print(f"[ObjectList] add_item key={key} text={text} actions={len(actions)}")
        self._rows[key] = {"frame": row, "label": lbl, "btns": btns, "btn_bar": btn_bar}

    def update_item_text(self, key: str, text: str):
        row = self._rows.get(key)
        if row:
            row["label"].configure(text=text)

    def update_item_actions(
        self,
        key: str,
        actions: Iterable[tuple[str, Callable[[], None] | None, bool]],
    ):
        row = self._rows.get(key)
        if not row:
            return
        btn_bar = row["btn_bar"]
        # remove old buttons
        for b in row["btns"]:
            try:
                b.destroy()
            except Exception:
                pass
        row["btns"].clear()
        # add new
        for idx, (btn_text, cb, enabled) in enumerate(actions):
            btn = customtkinter.CTkButton(
                btn_bar, text=btn_text, width=BTN_WIDTH,
                command=(cb if cb else None)
            )
            btn.grid(row=0, column=idx, padx=6)
            btn.configure(state=("normal" if enabled else "disabled"))
            row["btns"].append(btn)

    def set_items(
        self,
        items: list[tuple[str, str]],
        make_actions: Callable[[str], Iterable[tuple[str, Callable[[], None] | None, bool]]] | None = None,
    ):
        """
        items: list of (key, text)
        make_actions: function(key) -> actions
        """
        self.clear()
        for key, text in items:
            acts = make_actions(key) if make_actions else ()
            self.add_item(key, text, acts)