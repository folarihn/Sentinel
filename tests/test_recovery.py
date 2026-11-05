import tempfile
import unittest
from pathlib import Path

from sentinel.recovery import Recovery
from sentinel.store import Store


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / "workspace"
        self.workspace.mkdir()
        self.store = Store(Path(self.temp.name) / "state")
        self.recovery = Recovery(self.store, self.workspace)

    def test_restore_existing_and_authorization(self):
        target = self.workspace / "example.txt"
        target.write_text("before")
        point = self.recovery.checkpoint(target)
        target.write_text("after")
        self.recovery.seal(point["id"])
        with self.assertRaises(PermissionError):
            self.recovery.restore(point["id"])
        self.recovery.restore(point["id"], authorized=True)
        self.assertEqual(target.read_text(), "before")

    def test_new_file_and_deleted_file(self):
        target = self.workspace / "new.txt"
        point = self.recovery.checkpoint(target)
        target.write_text("new")
        self.recovery.seal(point["id"])
        self.recovery.restore(point["id"], authorized=True)
        self.assertFalse(target.exists())
        target.write_text("old")
        point = self.recovery.checkpoint(target)
        target.unlink()
        self.recovery.seal(point["id"])
        self.recovery.restore(point["id"], authorized=True)
        self.assertEqual(target.read_text(), "old")

    def test_conflict(self):
        target = self.workspace / "conflict.txt"
        target.write_text("before")
        point = self.recovery.checkpoint(target)
        target.write_text("agent")
        self.recovery.seal(point["id"])
        target.write_text("new user changes")
        with self.assertRaisesRegex(ValueError, "Conflict"):
            self.recovery.restore(point["id"], authorized=True)
        self.assertEqual(target.read_text(), "new user changes")

    def test_traversal_and_corruption(self):
        with self.assertRaises(ValueError):
            self.recovery.checkpoint("../escape.txt")
        target = self.workspace / "corrupt.txt"
        target.write_text("before")
        point = self.recovery.checkpoint(target)
        target.write_text("after")
        self.recovery.seal(point["id"])
        with self.store.connect() as db:
            db.execute(
                "UPDATE checkpoints SET original=? WHERE id=?",
                (b"corrupt", point["id"]),
            )
        with self.assertRaisesRegex(ValueError, "integrity"):
            self.recovery.restore(point["id"], authorized=True)

    def test_unsealed_restore(self):
        point = self.recovery.checkpoint("missing.txt")
        with self.assertRaisesRegex(ValueError, "sealed"):
            self.recovery.restore(point["id"], authorized=True)
