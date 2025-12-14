import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
from typing import Any, Iterable, Callable, Optional

class FileBrowser(ctk.CTkFrame):
    def __init__(self, master: Any, width: int, height: int, filetypes: Iterable[tuple[str, str | list[str] | tuple[str, ...]]], 
                 on_browse_done: Optional[Callable[[str], None]] = None):
        super().__init__(master, width, height)
        self._filetypes = filetypes
        self._on_browse_done = on_browse_done

        self.entry = ctk.CTkEntry(self)
        self.entry.place(relx=0, rely=0, relwidth=0.775)
        self._browse_btn = ctk.CTkButton(self, text="Browse", command=self.browse_file)
        self._browse_btn.place(relx=1, rely=0, relwidth=0.175, anchor=tk.NE)
        # # ensure the frame has the requested size so column weight expansion works
        # self.configure(width=width, height=height)
        # # prevent children from forcing frame resize
        # # try:
        # #     self.grid_propagate(False)
        # # except Exception:
        # #     pass

        # self.grid_rowconfigure(0, weight=1)
        # self.grid_columnconfigure(0, weight=1)  # entry expands horizontally
        # self.grid_columnconfigure(1, weight=0)  # button fixed size

        # self.entry = ctk.CTkEntry(self)
        # self.entry.grid(row=0, column=0, sticky="ew", padx=(12,6), pady=12)
        # self._browse_btn = ctk.CTkButton(self, text="Browse", command=self.browse_file)
        # try:
        #     self._browse_btn.configure(width=30)
        # except Exception:
        #     pass
        # self._browse_btn.grid(row=0, column=1, sticky="e", padx=(6,12), pady=12)

    def browse_file(self):
        path = filedialog.askopenfilename(title="Select File", filetypes=self._filetypes)
        if path:
            self.entry.delete(0, tk.END)
            self.entry.insert(0, path)
            if self._on_browse_done:
                self._on_browse_done(path)


# root = ctk.CTk()
# entry = ctk.CTkEntry(root, width=480)
# entry.pack(padx=12, pady=12)



# def browse_folder():
#     path = filedialog.askdirectory(title="Select folder")
#     if path:
#         entry.delete(0, tk.END)
#         entry.insert(0, path)

# ctk.CTkButton(root, text="Browse File", command=browse_file).pack(padx=8, pady=6)
# ctk.CTkButton(root, text="Browse Folder", command=browse_folder).pack(padx=8, pady=6)

# root.mainloop()