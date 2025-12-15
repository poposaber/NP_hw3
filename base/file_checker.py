from pathlib import Path
from protocols.protocols import Words
import hashlib

class FileChecker:
    def __init__(self, file_path: Path, metadata_dict: dict):
        self.file_path = file_path
        self.metadata_dict = metadata_dict

    def check(self) -> tuple[bool, dict]:
        # game_id = str(self.metadata_dict.get(Words.ParamKeys.Metadata.GAME_ID))
        # version = str(self.metadata_dict.get(Words.ParamKeys.Metadata.VERSION))
        # uploader = str(self.metadata_dict.get(Words.ParamKeys.Metadata.UPLOADER))
        # file_name = str(self.metadata_dict.get(Words.ParamKeys.Metadata.FILE_NAME))
        size = self.metadata_dict.get(Words.ParamKeys.Metadata.SIZE)
        sha256 = str(self.metadata_dict.get(Words.ParamKeys.Metadata.SHA256))

        # self.file_path = GAME_FOLDER / game_id / version / file_name
        assert isinstance(size, int)
        # verify size
        try:
            actual_size = self.file_path.stat().st_size
        except Exception:
            actual_size = -1
        if actual_size != size:
            return (False, {Words.ParamKeys.Failure.REASON: f"Size mismatch: {actual_size} != {size}"})
            # # cleanup
            # try: self.file_path.unlink()
            # except Exception: pass
            # with self.upload_lock:
            #     self.upload_params.clear()
            # self.send_response(passer, msg_id, Words.Result.FAILURE, {
            #     Words.ParamKeys.Failure.REASON: f"Size mismatch: {actual_size} != {st['size']}"
            # })
            # continue
        # verify sha256
        try:
            h = hashlib.sha256()
            with open(self.file_path, "rb") as rf:
                for b in iter(lambda: rf.read(1024*1024), b""):
                    h.update(b)
            digest = h.hexdigest()
        except Exception as e:
            return (False, {Words.ParamKeys.Failure.REASON: f"Checksum error: {e}"})
            # try: self.file_path.unlink()
            # except Exception: pass
            # with self.upload_lock:
            #     self.upload_params.clear()
            # self.send_response(passer, msg_id, Words.Result.FAILURE, {
            #     Words.ParamKeys.Failure.REASON: f"Checksum error: {e}"
            # })
            # continue
        if digest != sha256:
            return (False, {Words.ParamKeys.Failure.REASON: "Checksum mismatch"})
            # try: self.file_path.unlink()
            # except Exception: pass
            # with self.upload_lock:
            #     self.upload_params.clear()
            # self.send_response(passer, msg_id, Words.Result.FAILURE, {
            #     Words.ParamKeys.Failure.REASON: "Checksum mismatch"
            # })
            # continue
        return (True, {})