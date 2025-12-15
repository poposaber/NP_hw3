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
    def __init__(self, host = "127.0.0.1", port = 21355) -> None:
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
                                                                                    "           client.py\n" \
                                                                                    "       server\n" \
                                                                                    "           server.py\n" \
                                                                                    "       config.json\n" \
                                                                                    "- client.py should contain a class GameClient(host, port)\n" \
                                                                                    "- server.py should contain a class GameServer(host, port)", 
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
            self.account_name_label.configure(text=self._username)

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
            gid_list = list(params.keys())
            def delete(gid: str):
                print(f"delete {gid}")
            self.works_list.set_items([(gid, gid) for gid in gid_list], lambda s: [("delete123", lambda: delete(s), True)])
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

    def _run_upload_chunked(self, zip_path: Path) -> None:
        def _sha256_file(path: Path) -> str:
            h = hashlib.sha256()
            with path.open("rb") as f:
                for b in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(b)
            return h.hexdigest()

        def _is_safe(name: str) -> bool:
            p = Path(name)
            return not p.is_absolute() and (".." not in p.parts)

        try:
            size = zip_path.stat().st_size
            sha256 = _sha256_file(zip_path)
            # Defaults if manifest is missing fields
            game_id = zip_path.stem
            version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

            # Strict validation against your template rules
            with zipfile.ZipFile(zip_path, "r") as z:
                names = z.namelist()
                # path safety
                bad = [n for n in names if not _is_safe(n)]
                if bad:
                    self._notify_error(f"Unsafe paths in zip: {bad[:3]}...")
                    return

                # must-have files at expected locations
                required = ["config.json", "client/__main__.py", "server/__main__.py"]
                missing = [r for r in required if r not in names]
                if missing:
                    self._notify_error(f"Missing required files: {', '.join(missing)}")
                    return

                # parse config.json at root
                try:
                    manifest = json.loads(z.read("config.json").decode("utf-8"))
                except Exception as e:
                    self._notify_error(f"Invalid config.json: {e}")
                    return

                game_id = manifest.get("id") or game_id
                version = manifest.get("version") or version

                # Optional sanity: check server/client module names
                # server_module = manifest.get("server_module")
                # client_module = manifest.get("client_module")

            # Start request
            assert isinstance(self.client, DeveloperClient) and self.client.worker is not None
            start_resp = self.client.worker.pend_and_wait(
                Words.MessageType.REQUEST,
                {
                    Words.DataKeys.Request.COMMAND: Words.Command.UPLOAD_START,
                    Words.DataKeys.PARAMS: {
                        "game_id": game_id,
                        "version": version,
                        "filename": zip_path.name,
                        "size": size,
                        "sha256": sha256,
                        # Optional: echo manifest details for server-side validation
                        # "manifest": {"min_players": manifest.get("min_players"), "max_players": manifest.get("max_players")}
                    },
                },
                self.client.server_response_timeout,
            )
            if start_resp.get(Words.DataKeys.Response.RESULT) != Words.Result.SUCCESS:
                params = start_resp.get(Words.DataKeys.PARAMS) or {}
                reason = params.get(Words.ParamKeys.Failure.REASON, "Upload start rejected")
                self._notify_error(reason)
                return

            # Chunked streaming (<= 65536 per frame: header + chunk)
            CHUNK_MAX = 60 * 1024
            passer = self.client.worker.passer
            seq = 0
            with zip_path.open("rb") as f:
                while True:
                    chunk = f.read(CHUNK_MAX)
                    if not chunk:
                        break
                    passer.send_chunk(seq, chunk)
                    seq += 1
                passer.send_chunk(seq, None)

            # End request
            end_resp = self.client.worker.pend_and_wait(
                Words.MessageType.REQUEST,
                {
                    Words.DataKeys.Request.COMMAND: Words.Command.UPLOAD_END,
                    Words.DataKeys.PARAMS: {
                        "game_id": game_id,
                        "version": version,
                        "filename": zip_path.name,
                        "last_seq": seq,
                        "sha256": sha256,
                        "size": size,
                    },
                },
                self.client.server_response_timeout,
            )
            if end_resp.get(Words.DataKeys.Response.RESULT) == Words.Result.SUCCESS:
                self._notify_info(f"Upload complete: {game_id} v{version}")
            else:
                params = end_resp.get(Words.DataKeys.PARAMS) or {}
                reason = params.get(Words.ParamKeys.Failure.REASON, "Upload end failed")
                self._notify_error(reason)
        except TimeoutError:
            self._notify_error("Upload timed out")
        except ConnectionError as e:
            self._notify_error(f"Connection error: {e}")
        except Exception as e:
            self._notify_error(f"Upload error: {e}")
        finally:
            try:
                self.app.after(0, lambda: self.upload_btn.configure(state="normal"))
            except Exception:
                pass

    # def _run_upload_chunked(self, zip_path: Path) -> None:
    #     """
    #     Protocol:
    #       - REQUEST: UPLOAD_START {game_id, version, filename, size, sha256}
    #       - RAW: length-prefixed frames for each chunk:
    #         frame = struct.pack("!I", len(json_header) + len(chunk)) + json_header + chunk
    #         where json_header = b'{"type":"UPLOAD_CHUNK","seq":n,"size":len(chunk)}'
    #       - REQUEST: UPLOAD_END {seq_last}
    #     Server should respond SUCCESS/FAILURE to START and END; CHUNKs are fire-and-forget.
    #     """
    #     def _sha256_file(path: Path) -> str:
    #         h = hashlib.sha256()
    #         with path.open("rb") as f:
    #             for b in iter(lambda: f.read(1024 * 1024), b""):
    #                 h.update(b)
    #         return h.hexdigest()
        
    #     try:
    #         # basic checks and manifest hints
    #         size = zip_path.stat().st_size
    #         sha256 = _sha256_file(zip_path)
    #         game_id = zip_path.stem
    #         version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    #         # optional: peek config.json inside zip for id/version
    #         try:
    #             with zipfile.ZipFile(zip_path, "r") as z:
    #                 candidates = [n for n in z.namelist() if n.endswith("config.json") or n.endswith("manifest.json")]
    #                 if candidates:
    #                     c = min(candidates, key=lambda s: s.count("/"))
    #                     data = json.loads(z.read(c).decode("utf-8"))
    #                     game_id = data.get("id") or game_id
    #                     version = data.get("version") or version
    #         except Exception:
    #             pass

    #         # start request via client worker
    #         assert isinstance(self.client, DeveloperClient) and self.client.worker is not None
    #         start_resp = self.client.worker.pend_and_wait(
    #             Words.MessageType.REQUEST,
    #             {
    #                 Words.DataKeys.Request.COMMAND: Words.Command.UPLOAD_START,
    #                 Words.DataKeys.PARAMS: {
    #                     "game_id": game_id,
    #                     "version": version,
    #                     "filename": zip_path.name,
    #                     "size": size,
    #                     "sha256": sha256,
    #                 },
    #             },
    #             self.client.lobby_response_timeout,
    #         )
    #         if start_resp.get(Words.DataKeys.Response.RESULT) != Words.Result.SUCCESS:
    #             params = start_resp.get(Words.DataKeys.PARAMS) or {}
    #             reason = params.get(Words.ParamKeys.Failure.REASON, "Upload start rejected")
    #             self._notify_error(reason)
    #             return

    #         # stream chunks using MessageFormatPasser (max raw frame <= 65536)
    #         # header + chunk must be <= LENGTH_LIMIT (65536)
    #         CHUNK_MAX = 60 * 1024  # 60KB to leave room for header
    #         passer = self.client.worker.passer  # underlying MessageFormatPasser
    #         seq = 0
    #         with zip_path.open("rb") as f:
    #             while True:
    #                 chunk = f.read(CHUNK_MAX)
    #                 if not chunk:
    #                     break
    #                 header = json.dumps({"type": "UPLOAD_CHUNK", "seq": seq, "size": len(chunk)}).encode("utf-8")
    #                 frame = header + chunk
    #                 # send as one raw frame (MessageFormatPasser adds 4-byte length prefix)
    #                 # ensure single frame size fits limit
    #                 if len(frame) > 65536:
    #                     self._notify_error(f"Internal frame too large: {len(frame)} bytes")
    #                     return
    #                 passer.send_raw(frame)
    #                 seq += 1

    #         # end request
    #         end_resp = self.client.worker.pend_and_wait(
    #             Words.MessageType.REQUEST,
    #             {
    #                 Words.DataKeys.Request.COMMAND: Words.Command.UPLOAD_END,
    #                 Words.DataKeys.PARAMS: {
    #                     "game_id": game_id,
    #                     "version": version,
    #                     "filename": zip_path.name,
    #                     "last_seq": seq - 1,
    #                     "sha256": sha256,
    #                     "size": size,
    #                 },
    #             },
    #             self.client.lobby_response_timeout,
    #         )
    #         if end_resp.get(Words.DataKeys.Response.RESULT) == Words.Result.SUCCESS:
    #             self._notify_info(f"Upload complete: {game_id} v{version}")
    #         else:
    #             params = end_resp.get(Words.DataKeys.PARAMS) or {}
    #             reason = params.get(Words.ParamKeys.Failure.REASON, "Upload end failed")
    #             self._notify_error(reason)
    #     except TimeoutError:
    #         self._notify_error("Upload timed out")
    #     except ConnectionError as e:
    #         self._notify_error(f"Connection error: {e}")
    #     except Exception as e:
    #         self._notify_error(f"Upload error: {e}")
    #     finally:
    #         try:
    #             self.app.after(0, lambda: self.upload_btn.configure(state="normal"))
    #         except Exception:
    #             pass

        

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
        
