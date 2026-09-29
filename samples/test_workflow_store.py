import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from workflow_store import WorkflowStore


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "tasks.sqlite3"
        self.store = WorkflowStore(self.path)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_duplicate_reordered_payload_has_one_record(self):
        self.assertTrue(self.store.enqueue("one", {"a": 1, "b": 2}))
        self.assertFalse(self.store.enqueue("one", {"b": 2, "a": 1}))
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM tasks").fetchone()[0], 1)

    def test_conflicting_key_does_not_change_original(self):
        self.store.enqueue("one", {"course": "A"})
        with self.assertRaises(ValueError):
            self.store.enqueue("one", {"course": "B"})
        self.assertEqual(
            self.store.db.execute("SELECT payload FROM tasks").fetchone()[0], '{"course":"A"}'
        )

    def test_completion_replay_is_idempotent_and_conflict_is_rejected(self):
        self.store.enqueue("one", {})
        self.assertTrue(self.store.complete("one", {"receipt": "r1"}))
        self.assertFalse(self.store.complete("one", {"receipt": "r1"}))
        with self.assertRaises(ValueError):
            self.store.complete("one", {"receipt": "r2"})
        self.assertEqual(
            self.store.db.execute("SELECT event FROM audit ORDER BY sequence").fetchall(),
            [("accepted",), ("completed",)],
        )

    def test_audit_failure_rolls_back_state_transition(self):
        self.store.enqueue("one", {})
        self.store.db.execute(
            "CREATE TRIGGER reject_completion BEFORE INSERT ON audit WHEN NEW.event='completed' BEGIN SELECT RAISE(ABORT,'simulated failure'); END"
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.complete("one", {"receipt": "r1"})
        self.assertEqual(
            self.store.db.execute("SELECT state,result FROM tasks").fetchone(), ("pending", None)
        )

    def test_two_connections_racing_on_one_key_accept_once(self):
        def enqueue(_):
            connection = WorkflowStore(self.path)
            try:
                return connection.enqueue("shared", {"course": "A"})
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(enqueue, range(2))), [False, True])

    def test_missing_task_and_invalid_payloads_are_rejected(self):
        with self.assertRaises(KeyError):
            self.store.complete("missing", {})
        with self.assertRaises(ValueError):
            self.store.enqueue("nan", {"n": float("nan")})
        with self.assertRaises(ValueError):
            self.store.enqueue("large", {"data": "x" * 17000})


if __name__ == "__main__":
    unittest.main()
