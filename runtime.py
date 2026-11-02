"""Portable data migration and per-folder process locking."""
import os
import shutil
import sqlite3
from pathlib import Path


def migrate_legacy(directory):
    target = directory / "notes.db"
    legacy = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "AppData" / "Local" / "NoteZxh"
    if target.exists() or not (legacy / "notes.db").exists():
        return
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / "notes.migrating.db"
    source = sqlite3.connect((legacy / "notes.db").as_uri() + "?mode=ro", uri=True)
    destination = sqlite3.connect(temporary)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    if (legacy / "images").exists():
        shutil.copytree(legacy / "images", directory / "images", dirs_exist_ok=True)
    temporary.replace(target)


class InstanceLock:
    def __init__(self, directory):
        import msvcrt
        directory.mkdir(parents=True, exist_ok=True)
        self.file = (directory / ".notes.lock").open("a+b")
        self.file.seek(0, 2)
        if self.file.tell() == 0:
            self.file.write(b"0")
            self.file.flush()
        self.file.seek(0)
        try:
            msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            self.file.close()
            raise RuntimeError("便笺已经在运行，请从任务栏打开已有窗口。")

    def close(self):
        self.file.close()
