import os
import tempfile
import unittest
import concurrent.futures
from pathlib import Path

from sentinel.recovery import Recovery
from sentinel.store import Store


class RecoveryTests(unittest.TestCase):
    def test_restore_preserves_origin_session_and_operator_actor(self):
        target = self.workspace / "attributed.txt"
        target.write_text("before")
        point = self.recovery.checkpoint(
            target, {"session_id": "origin-session", "mission_id": "origin-mission"}
        )
        target.write_text("after")
        self.recovery.seal(point["id"])
        self.recovery.restore(point["id"], authorized=True)
        event = self.store.events()[-1]
        self.assertEqual(event["session_id"], "origin-session")
        self.assertEqual(event["mission_id"], "origin-mission")
        self.assertEqual(event["actor"], "local-operator")

    def test_identity_cannot_replace_integrity_metadata(self):
        point = self.recovery.checkpoint(
            "new.txt",
            {
                "id": "spoof",
                "path": "../escape",
                "original_hash": "spoof",
                "session_id": "valid",
            },
        )
        self.assertNotEqual(point["id"], "spoof")
        self.assertEqual(point["original_hash"], None)
        self.assertEqual(point["session_id"], "valid")

    def test_only_one_concurrent_restore_claim(self):
        target = self.workspace / "concurrent.txt"
        target.write_text("before")
        point = self.recovery.checkpoint(target)
        target.write_text("after")
        self.recovery.seal(point["id"])

        def restore(_):
            try:
                return Recovery(self.store, self.workspace).restore(
                    point["id"], authorized=True
                )["status"]
            except ValueError:
                return "REJECTED"

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(restore, range(2)))
        self.assertCountEqual(results, ["RESTORED", "REJECTED"])
        self.assertEqual(target.read_text(), "before")

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


class SymlinkBoundaryTests(unittest.TestCase):
    """Links above the workspace are host layout; links inside it are refused."""

    def _link(self, target, link):
        try:
            os.symlink(target, link, target_is_directory=Path(target).is_dir())
        except (OSError, NotImplementedError):
            self.skipTest("Symbolic links are not available on this host")

    def test_workspace_reached_through_a_host_link_is_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            real = Path(folder) / "real"
            (real / "work").mkdir(parents=True)
            (real / "work" / "notes.txt").write_text("v1", encoding="utf-8")
            self._link(real, Path(folder) / "alias")
            store = Store(Path(folder) / "state")
            recovery = Recovery(store, Path(folder) / "alias" / "work")
            made = recovery.checkpoint(Path(folder) / "alias" / "work" / "notes.txt")
            self.assertTrue(made["path"].endswith("notes.txt"))
            self.assertEqual(
                Recovery(store, real / "work").checkpoint("notes.txt")["status"], "OPEN"
            )

    def test_links_inside_the_workspace_are_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder) / "work"
            work.mkdir()
            (work / "notes.txt").write_text("v1", encoding="utf-8")
            outside = Path(folder) / "outside.txt"
            outside.write_text("secret", encoding="utf-8")
            self._link(outside, work / "link.txt")
            self._link(work, work / "loop")
            recovery = Recovery(Store(Path(folder) / "state"), work)
            for path in (
                work / "link.txt",
                work / "loop" / "notes.txt",
                "loop/notes.txt",
            ):
                with self.assertRaisesRegex(ValueError, "Symbolic links"):
                    recovery.checkpoint(path)

    def test_traversal_out_of_the_workspace_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder) / "work"
            work.mkdir()
            (Path(folder) / "outside.txt").write_text("x", encoding="utf-8")
            recovery = Recovery(Store(Path(folder) / "state"), work)
            for path in (
                "../outside.txt",
                work / ".." / "outside.txt",
                Path(folder) / "outside.txt",
            ):
                with self.assertRaisesRegex(ValueError, "escapes workspace"):
                    recovery.checkpoint(path)
