"""Conflict-aware checkpoints for explicitly selected local files only."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from pathlib import Path

from .store import now


def digest(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


class Recovery:
    def __init__(self, store, workspace):
        self.store = store
        self.workspace = Path(workspace).resolve(strict=True)

    def _path(self, path):
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.workspace / candidate
        # Links at or above the workspace root belong to the host (for example
        # macOS /var -> /private/var, or a symlinked home folder). Anchor on the
        # OUTERMOST ancestor that resolves to the workspace, so an inner link
        # pointing back at the workspace cannot become the anchor itself.
        anchor = None
        for parent in reversed(candidate.parents):
            try:
                if parent.resolve() == self.workspace:
                    anchor = parent
                    break
            except OSError:
                continue
        if anchor is None:
            raise ValueError("Recovery path escapes workspace")
        relative = candidate.relative_to(anchor)
        # Reject traversal and symlinks at every component inside the workspace,
        # including the final file.
        current = self.workspace
        for name in relative.parts:
            if name in ("..", "."):
                raise ValueError("Recovery path escapes workspace")
            current = current / name
            if current.is_symlink():
                raise ValueError("Symbolic links are not recoverable")
        candidate = current.resolve()
        if not candidate.is_relative_to(self.workspace) or candidate == self.workspace:
            raise ValueError("Recovery path escapes workspace")
        if candidate.is_relative_to(self.store.root):
            raise ValueError("Sentinel state cannot be checkpointed")
        return candidate

    def checkpoint(self, path, identity=None):
        path = self._path(path)
        if path.exists() and path.stat().st_size > 10 * 1024 * 1024:
            raise ValueError("File exceeds 10 MiB checkpoint limit")
        original = path.read_bytes() if path.exists() else None
        if original is not None and len(original) > 10 * 1024 * 1024:
            raise ValueError("File exceeds 10 MiB checkpoint limit")
        meta = {
            **{
                key: value
                for key, value in (identity or {}).items()
                if key in {"session_id", "mission_id", "tool_call_id", "agent_id"}
            },
            "id": uuid.uuid4().hex,
            "path": str(path),
            "original_hash": digest(original),
            "timestamp": now(),
            "status": "OPEN",
            "mode": path.stat().st_mode if path.exists() else None,
        }
        with self.store.connect() as db:
            db.execute(
                "INSERT INTO checkpoints VALUES(?,?,?)",
                (meta["id"], json.dumps(meta), original),
            )
        self.store.append(
            "checkpoint.created", identity, checkpoint_id=meta["id"], path=str(path)
        )
        return meta

    def _get(self, checkpoint_id):
        with self.store.connect() as db:
            row = db.execute(
                "SELECT payload,original FROM checkpoints WHERE id=?", (checkpoint_id,)
            ).fetchone()
        if not row:
            raise ValueError("Unknown checkpoint")
        return json.loads(row[0]), row[1]

    def _save(self, meta):
        with self.store.connect() as db:
            db.execute(
                "UPDATE checkpoints SET payload=? WHERE id=?",
                (json.dumps(meta), meta["id"]),
            )

    def seal(self, checkpoint_id):
        meta, _ = self._get(checkpoint_id)
        if meta["status"] != "OPEN":
            raise ValueError("Checkpoint is not open")
        path = self._path(meta["path"])
        meta.update(
            post_hash=digest(path.read_bytes() if path.exists() else None),
            status="SEALED",
        )
        self._save(meta)
        return meta

    def checkpoints(self):
        with self.store.connect() as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT payload FROM checkpoints ORDER BY rowid DESC"
                )
            ]

    def restore(self, checkpoint_id, authorized=False):
        if not authorized:
            raise PermissionError("Explicit restore authorization is required")
        # Claim the checkpoint under SQLite's writer lock. Separate HTTP workers
        # and processes must never both restore the same original concurrently.
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT payload FROM checkpoints WHERE id=?", (checkpoint_id,)
            ).fetchone()
            if not row:
                raise ValueError("Unknown checkpoint")
            meta = json.loads(row[0])
            if meta["status"] != "SEALED":
                raise ValueError("Only sealed checkpoints can be restored")
            meta["status"] = "RESTORING"
            db.execute(
                "UPDATE checkpoints SET payload=? WHERE id=?",
                (json.dumps(meta), checkpoint_id),
            )
        try:
            return self._restore_claimed(checkpoint_id)
        except Exception:
            # Never silently retry an interrupted/failed restoration. Its bytes
            # may already have changed if an I/O or journal write failed.
            meta["status"] = "FAILED"
            self._save(meta)
            raise

    def _restore_claimed(self, checkpoint_id):
        meta, original = self._get(checkpoint_id)
        identity = {
            key: meta[key]
            for key in ("session_id", "mission_id", "agent_id", "tool_call_id")
            if key in meta
        }
        path = self._path(meta["path"])
        if meta["status"] != "RESTORING":
            raise ValueError("Checkpoint is not claimed for restoration")
        if digest(original) != meta["original_hash"]:
            raise ValueError("Checkpoint integrity check failed")
        current = path.read_bytes() if path.exists() else None
        if digest(current) != meta["post_hash"]:
            raise ValueError("Conflict: file changed after checkpoint was sealed")
        self.store.append(
            "recovery.attempted",
            identity,
            checkpoint_id=checkpoint_id,
            path=str(path),
            actor="local-operator",
        )
        if original is None:
            self._path(path)
            if (
                digest(path.read_bytes() if path.exists() else None)
                != meta["post_hash"]
            ):
                raise ValueError("Conflict: concurrent modification")
            if path.exists():
                path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(prefix=".sentinel-restore-", dir=path.parent)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(original)
                    stream.flush()
                    os.fsync(stream.fileno())
                if meta.get("mode") is not None:
                    os.chmod(name, meta["mode"])
                # Recheck immediately before replacing; hook-level recovery is not an OS sandbox.
                if (
                    digest(path.read_bytes() if path.exists() else None)
                    != meta["post_hash"]
                ):
                    raise ValueError("Conflict: concurrent modification")
                self._path(path)
                os.replace(name, path)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
        meta.update(status="RESTORED", restored_at=now())
        self._save(meta)
        self.store.append(
            "recovery.completed",
            identity,
            checkpoint_id=checkpoint_id,
            path=str(path),
            actor="local-operator",
        )
        return meta
