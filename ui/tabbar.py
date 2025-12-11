import customtkinter
import tkinter
from typing import Callable, Dict, Optional

class TabButton(customtkinter.CTkButton):
    def __init__(self, master, name: str, command: Callable[[str], None], **kwargs):
        # remove rounded edge by default
        if "corner_radius" not in kwargs:
            kwargs["corner_radius"] = 0
        super().__init__(master=master, text=name, command=lambda: command(name), font=("Arial", 14), **kwargs)
        self._name = name
        # compute color palette for active/inactive  hover
        mode = customtkinter.get_appearance_mode().lower()
        if mode == "dark":
            self._active_fg = "#004268"
            self._active_text = "white"
            self._active_hover = "#00608b"
            self._inactive_text = "white"
            self._inactive_hover = "#293952"
        else:
            self._active_fg = "#7ABAFF"
            self._active_text = "black"
            self._active_hover = "#9fd6ff"
            self._inactive_text = "black"
            self._inactive_hover = "#e9f5ff"
        # apply initial hover color
        try:
            self.configure(hover_color=self._inactive_hover)
        except Exception:
            pass

    def set_active(self, active: bool):
        mode = customtkinter.get_appearance_mode().lower()
        if active:
            self.configure(fg_color=self._active_fg, text_color=self._active_text, hover_color=self._active_hover, font=("Arial", 15, "bold"))
        else:
            # use transparent background and pick readable text color for current appearance mode
            self.configure(fg_color="transparent", text_color=self._inactive_text, hover_color=self._inactive_hover, font=("Arial", 14))

class TabBar(customtkinter.CTkFrame):
    def __init__(self, master, command: Callable[[str], None], height: int = 40, **kwargs):
        # remove rounded edge by default
        if "corner_radius" not in kwargs:
            kwargs["corner_radius"] = 0
        super().__init__(master=master, height=height, **kwargs)
        self.place(relx=0, rely=0, relwidth=1)
        self._command = command
        self._buttons: Dict[str, TabButton] = {}
        self._frames: Dict[str, customtkinter.CTkFrame] = {}
        self._active: Optional[str] = None
        self._height = height

    def add_tab(self, name: str, frame: customtkinter.CTkFrame, default: bool = False):
        """註冊 tab 及對應 content frame（frame 先建立但不顯示）。"""
        # 建按鈕
        btn = TabButton(self, name=name, command=self._on_click, width=120, height=self._height)
        btn.place(relx=0, rely=0.5, anchor=tkinter.CENTER)  # temporary; will update layout
        self._buttons[name] = btn

        # store frame (caller should not place it; TabBar will place when shown)
        self._frames[name] = frame

        # re-layout buttons evenly
        self._relayout_buttons()

        if default or self._active is None:
            self.show(name)

    def _relayout_buttons(self):
        n = max(1, len(self._buttons))
        for i, (name, btn) in enumerate(self._buttons.items()):
            relx = (i + 0.5) / n
            btn.place_configure(relx=relx)

    def _on_click(self, name: str):
        self.show(name)
        # notify external handler
        try:
            self._command(name)
        except Exception:
            pass

    def show(self, name: str):
        if name not in self._frames:
            return
        # hide previous
        if self._active and self._active in self._frames:
            try:
                self._frames[self._active].place_forget()
            except Exception:
                pass
        # show new content under tab bar
        frame = self._frames[name]
        frame.place(relx=0, rely=1, relwidth=1, relheight=0.92, anchor=tkinter.SW)
        # update buttons state
        for n, btn in self._buttons.items():
            btn.set_active(n == name)
        self._active = name