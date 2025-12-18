# next: add heartbeat patience

import customtkinter
import tkinter
import threading
import time
from typing import Optional, Callable
from .developer_client import DeveloperClient
from protocols.protocols import Words
from clients.client_window_base import ClientWindowBase
from ui.tabbar import TabBar
from ui.object_list import ObjectList
from ui.file_browser import FileBrowser

import subprocess
import sys
from pathlib import Path
from tkinter import messagebox, simpledialog
from tkinter import filedialog
import zipfile
import json
import shutil
import hashlib
from datetime import datetime, timezone

# NORMAL_LABEL_COLOR = "#5882ff"
# HOVER_LABEL_COLOR = "#295fff"
# CLICK_LABEL_COLOR = "#1f4fcc"

class DeveloperClientWindow(ClientWindowBase):
    # LOGIN_TIMEOUT = 5.0
    def __init__(self, host = "linux1.cs.nycu.edu.tw", port = 21355) -> None:
        # GUI 與 client 分離：建立 PlayerClient 實例
        # self.client = PlayerClient(host=host, port=port, 
        #                            on_connection_done=self._on_client_connection_done, 
        #                            on_connection_fail=self._on_client_connection_fail, 
        #                            on_connection_lost=self._on_client_connection_lost)
        super().__init__(host, port, 
                         DeveloperClient(host=host, port=port, 
                            on_connection_done=self._on_client_connection_done, 
                            on_connection_fail=self._on_client_connection_fail, 
                            on_connection_lost=self._on_client_connection_lost))
        
        self.app.title("Develop 2 Amaze")
        customtkinter.set_appearance_mode("Light")
        self.developer_notion_text = customtkinter.CTkLabel(master=self.app, text="This is for developers, not players.")
        self.developer_notion_text.place(relx=0.0, rely=0.0)

        self.upload_frame = customtkinter.CTkFrame(master=self.home_frame, corner_radius=0, width=800, height=560, fg_color="transparent")
        self.upload_caption = customtkinter.CTkLabel(master=self.upload_frame, text="Rules of Uploads", font=("Arial", 40, "bold"))
        self.upload_caption.place(relx=0.5, rely=0.05, anchor=tkinter.N)
        self.upload_content = customtkinter.CTkLabel(master=self.upload_frame, text="- You should upload exactly one .zip file.\n" \
                                                                                    "- The minimum structure of .zip file: \n" \
                                                                                    "   xxx.zip\n" \
                                                                                    "       client\n" \
                                                                                    "           __main__.py\n" \
                                                                                    "       server\n" \
                                                                                    "           __main__.py\n" \
                                                                                    "       config.json\n" \
                                                                                    "- The config.json should contain at least the following fields:\n" \
                                                                                    "id, name, version, author, players\n",  
                                                                                    font=("Arial", 15), 
                                                                                    anchor=tkinter.W,
                                                                                    justify=tkinter.LEFT,
                                                                                    wraplength=720)
        self.upload_content.place(relx=0.1, rely=0.2)
        self.zip_browser = FileBrowser(master=self.upload_frame, width=480, height=40, filetypes=[("ZIP files", "*.zip")], on_browse_done=self._on_browse_done)
        self.zip_browser.place(relx=0.5, rely=0.8, anchor=tkinter.S)
        self.upload_btn = customtkinter.CTkButton(master=self.upload_frame, text="Upload Game", command=self.upload_game)
        self.upload_btn.place(relx=0.5, rely=0.95, anchor=tkinter.S)
        self.upload_btn.configure(state="disabled")
        # customtkinter.CTkLabel(master=self.upload_frame, text="upload!").place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)

        self.my_works_frame = customtkinter.CTkFrame(master=self.home_frame, corner_radius=0, width=800, height=560, fg_color="transparent")
        self.works_list = ObjectList(self.my_works_frame, width=780, height=500)
        self.works_list.place(relx=0, rely=0)
        self.create_template_button = customtkinter.CTkButton(master=self.my_works_frame, text="Create Game Template", command=self._on_create_template)
        self.create_template_button.place(relx=0.5, rely=0.95, anchor=tkinter.S)
        # customtkinter.CTkLabel(master=self.my_works_frame, text="my works!").place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)

        self.account_frame = customtkinter.CTkFrame(master=self.home_frame, corner_radius=0, width=800, height=560, fg_color="transparent")
        self.account_name_label = customtkinter.CTkLabel(master=self.account_frame, text="", font=("Arial", 25, "bold"))
        self.account_name_label.place(relx=0.1, rely=0.1, anchor=tkinter.CENTER)
        self.logout_btn = customtkinter.CTkButton(master=self.account_frame, text="Logout", command=self.logout)
        self.logout_btn.place(relx=0.5, rely=0.8, anchor=tkinter.CENTER)

        self.home_tabbar = TabBar(self.home_frame, self.show_tab)
        self.home_tabbar.add_tab("My Works", self.my_works_frame)
        self.home_tabbar.add_tab("Upload", self.upload_frame, default=True)
        self.home_tabbar.add_tab("Account", self.account_frame)
        self.home_tabbar.show("My Works")
        
        # self.developer_client_window_test_text = customtkinter.CTkLabel(master=self.home_frame, text="testing for developers")
        # self.developer_client_window_test_text.place(relx=0.5, rely=0.7, anchor=tkinter.CENTER)
    def login(self):
        super().login()
        self.home_tabbar.show("My Works")
    
    def _on_login_result_ui(self, success, params):
        super()._on_login_result_ui(success, params)
        if success:
            self.developer_notion_text.place_forget()
            self.account_name_label.configure(text=self.client.username)
            self.check_my_works()

    def _on_logout_result_ui(self, success, params):
        super()._on_logout_result_ui(success, params)
        if success:
            self.developer_notion_text.place(relx=0.0, rely=0.0)

    def show_tab(self, name: str):
        if name == "My Works":
            self.check_my_works()

    def check_my_works(self):
        threading.Thread(target=self._check_my_works_thread, daemon=True).start()

    def _check_my_works_thread(self):
        assert isinstance(self.client, DeveloperClient)
        success, params = self.client.try_check_my_works()
        self.app.after(0, self._on_check_my_works_ui, success, params)

    def _on_check_my_works_ui(self, success: bool, params: dict):
        if success:
            # gid_list = list(params.keys())
            def delete(gid: str):
                print(f"delete {gid} not implemented")
            self.works_list.set_items([(gid, params[gid][Words.ParamKeys.Metadata.GAME_NAME]) for gid in params], lambda s: [("delete123", lambda: delete(s), True)])
        else:
            print(f"failed. {params}")

    def _on_create_template(self) -> None:
        """Prompt for template metadata and run the scaffold script in background."""
        name = simpledialog.askstring("Create Game", "Game name:", parent=self.app)
        if name is None:
            return
        elif name == "":
            self._notify_error("Game name cannot be empty!")
            return
        gid = simpledialog.askstring("Create Game", "Game id (optional):", parent=self.app)
        if gid is None:
            return
        author = simpledialog.askstring("Create Game", "Author (optional):", parent=self.app)
        if author is None:
            return
        # disable the button while the background task runs
        try:
            self.create_template_button.configure(state="disabled")
        except Exception:
            pass
        threading.Thread(target=self._run_create_template, args=(name, gid, author), daemon=True).start()

    def _run_create_template(self, name: str, gid: str, author: str) -> None:
        try:
            script_path = Path(__file__).resolve().parent / "create_game_template.py"
            cmd = [sys.executable, str(script_path), "--name", name]
            if gid:
                cmd += ["--id", gid]
            if author:
                cmd += ["--author", author]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(script_path.parent), timeout=120)
            except subprocess.TimeoutExpired as e:
                self._notify_error(f"Scaffold timed out: {e}")
                return
            out = proc.stdout.strip()
            err = proc.stderr.strip()
            if proc.returncode == 0:
                message = out or "Template created successfully."
                self._notify_info(message)
            else:
                message = err or out or f"Return code: {proc.returncode}"
                self._notify_error(message)
        except Exception as e:
            self._notify_error(str(e))
        finally:
            # always re-enable the button on the main thread
            try:
                self.app.after(0, lambda: self.create_template_button.configure(state="normal") )
            except Exception:
                pass

    def _on_browse_done(self, filename: str):
        if not filename:
            self.upload_btn.configure(state="disabled")
        else:
            self.upload_btn.configure(state="normal")

    def upload_game(self) -> None:
        try:
            p = Path(self.zip_browser.entry.get().strip())
        except Exception:
            p = None
        if not p or not p.exists() or p.suffix.lower() != ".zip":
            self._notify_error("Please select a valid .zip file.")
            return
        try:
            self.upload_btn.configure(state="disabled")
        except Exception:
            pass
        threading.Thread(target=self._upload_game_thread, args=(p,), daemon=True).start()

    def _upload_game_thread(self, zip_path: Path):
        assert isinstance(self.client, DeveloperClient)
        success, params = self.client.upload_file(zip_path)
        self.app.after(0, self._on_upload_game_ui, success, params)
        # self._notify_error(str(e))
        # try: self.upload_btn.configure(state="normal") 
        # except Exception: pass

    def _on_upload_game_ui(self, success: bool, params: dict):
        if success:
            self._notify_info("Upload completed.")
        else:
            self._notify_error(f"Upload failed. Reason: {params.get(Words.ParamKeys.Failure.REASON, "unknown")}")
        self.upload_btn.configure(state="normal")  

    def _notify_info(self, message: str) -> None:
        def _show():
            try:
                messagebox.showinfo("Create Template", message, parent=self.app)
            except Exception:
                pass
        try:
            self.app.after(0, _show)
        except Exception:
            _show()

    def _notify_error(self, message: str) -> None:
        def _show():
            try:
                messagebox.showerror("Create Template Failed", message, parent=self.app)
            except Exception:
                pass
        try:
            self.app.after(0, _show)
        except Exception:
            _show()
        
