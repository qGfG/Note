"""Local, transactional storage for the notes application."""
from __future__ import annotations

import os
import sys
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path


def default_data_dir() -> Path:
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent


class NoteStore:
    def __init__(self, directory: Path | None = None):
        self.directory = directory if directory is not None else default_data_dir()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.directory / "notes.db")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("""CREATE TABLE IF NOT EXISTS notes (
            id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '',
            body TEXT NOT NULL DEFAULT '', color TEXT NOT NULL DEFAULT '奶油',
            pinned INTEGER NOT NULL DEFAULT 0, deleted INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(notes)")}
        for name, definition in {"topmost": "INTEGER NOT NULL DEFAULT 0", "geometry": "TEXT NOT NULL DEFAULT ''", "formatting": "TEXT NOT NULL DEFAULT '{}'", "closed_at": "TEXT NOT NULL DEFAULT ''"}.items():
            if name not in columns:
                self.connection.execute(f"ALTER TABLE notes ADD COLUMN {name} {definition}")
        self.connection.commit()

    def create(self, title: str = "", body: str = "") -> str:
        note_id = uuid.uuid4().hex
        now = datetime.now().isoformat(timespec="microseconds")
        with self.connection:
            self.connection.execute(
                "INSERT INTO notes (id,title,body,created_at,updated_at) VALUES (?,?,?,?,?)",
                (note_id, title, body, now, now),
            )
        return note_id

    def get(self, note_id: str) -> dict | None:
        row = self.connection.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
        return dict(row) if row else None

    def list(self, query: str = "", mode: str = "all") -> list[dict]:
        # instr treats %, _ and other search characters literally.
        rows = self.connection.execute(
            """SELECT * FROM notes WHERE deleted=? AND (?=0 OR pinned=1)
            AND (?='' OR instr(lower(title),lower(?))>0 OR instr(lower(body),lower(?))>0)
            ORDER BY pinned DESC, updated_at DESC, id""",
            (int(mode == "trash"), int(mode == "pinned"), query, query, query),
        ).fetchall()
        return [dict(row) for row in rows]

    def update(self, note_id: str, **values) -> None:
        allowed = {"title", "body", "color", "pinned", "deleted", "topmost", "geometry", "formatting"}
        if not values or not set(values).issubset(allowed):
            raise ValueError("Invalid note fields")
        if {"title", "body", "formatting"}.intersection(values):
            values["updated_at"] = datetime.now().isoformat(timespec="microseconds")
        columns = ", ".join(f"{key}=?" for key in values)
        with self.connection:
            self.connection.execute(f"UPDATE notes SET {columns} WHERE id=?", (*values.values(), note_id))

    def purge(self, note_id: str) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM notes WHERE id=? AND deleted=1", (note_id,))

    def remember_closed(self, note_id: str) -> None:
        with self.connection:
            self.connection.execute("UPDATE notes SET closed_at=? WHERE id=? AND deleted=0",
                                    (datetime.now().isoformat(timespec="microseconds"), note_id))

    def last_closed(self) -> dict | None:
        row = self.connection.execute(
            "SELECT * FROM notes WHERE deleted=0 AND closed_at!='' ORDER BY closed_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def close(self) -> None:
        self.connection.close()
