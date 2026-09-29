"""A local persistence exercise; external delivery and worker leases are out of scope."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class WorkflowStore:
    def __init__(self, path: str | Path):
        self.db = sqlite3.connect(path, isolation_level=None, timeout=5)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                request_key TEXT PRIMARY KEY, payload TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('pending','completed')),
                result TEXT
            );
            CREATE TABLE IF NOT EXISTS audit (
                sequence INTEGER PRIMARY KEY, request_key TEXT NOT NULL,
                event TEXT NOT NULL,
                recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(request_key) REFERENCES tasks(request_key)
            );
        """)

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    @staticmethod
    def encode(value: dict) -> str:
        if not isinstance(value, dict):
            raise TypeError("Expected a JSON object")
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(encoded.encode("utf-8")) > 16_384:
            raise ValueError("Example payload limit is 16 KiB")
        return encoded

    def enqueue(self, request_key: str, payload: dict) -> bool:
        """Return True for a new task, False for an identical existing request."""
        if not isinstance(request_key, str) or not request_key.strip() or len(request_key) > 200:
            raise ValueError("A nonempty request key of at most 200 characters is required")
        encoded = self.encode(payload)
        with self.transaction():
            old = self.db.execute(
                "SELECT payload FROM tasks WHERE request_key=?", (request_key,)
            ).fetchone()
            if old:
                if old[0] != encoded:
                    raise ValueError("This key already belongs to different content")
                return False
            self.db.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, NULL)", (request_key, encoded, "pending")
            )
            self.db.execute(
                "INSERT INTO audit(request_key,event) VALUES (?,?)", (request_key, "accepted")
            )
            return True

    def complete(self, request_key: str, result: dict) -> bool:
        """Atomically save a result and one audit event; reject conflicting replay."""
        encoded = self.encode(result)
        with self.transaction():
            old = self.db.execute(
                "SELECT state,result FROM tasks WHERE request_key=?", (request_key,)
            ).fetchone()
            if old is None:
                raise KeyError(request_key)
            if old[0] == "completed":
                if old[1] != encoded:
                    raise ValueError("The completed result cannot be silently replaced")
                return False
            self.db.execute(
                "UPDATE tasks SET state=?,result=? WHERE request_key=?",
                ("completed", encoded, request_key),
            )
            self.db.execute(
                "INSERT INTO audit(request_key,event) VALUES (?,?)", (request_key, "completed")
            )
            return True

    def close(self):
        self.db.close()


if __name__ == "__main__":
    store = WorkflowStore(":memory:")
    try:
        print("First request:", store.enqueue("training:example:1", {"course": "safety-basics"}))
        print("Repeated request:", store.enqueue("training:example:1", {"course": "safety-basics"}))
        print("Completion:", store.complete("training:example:1", {"outcome": "recorded"}))
        print(
            "Audit events:",
            store.db.execute("SELECT event FROM audit ORDER BY sequence").fetchall(),
        )
    finally:
        store.close()
