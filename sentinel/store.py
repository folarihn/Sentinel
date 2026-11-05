"""Local, redacted operational journal. No credentials are required."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def redact(value):
    if isinstance(value, dict):
        return {
            str(k): "[REDACTED]"
            if re.search(
                r"password|secret|token|api[_-]?key|authorization|credential|private[_-]?key",
                str(k),
                re.I,
            )
            or str(k).lower() in {"content", "text", "code", "script"}
            else redact(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        value = re.sub(
            r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----",
            "[REDACTED PRIVATE KEY]",
            value,
            flags=re.S,
        )
        value = re.sub(
            r"(https?://)[^/\s:@]+:[^/\s@]+@", r"\1[REDACTED]@", value, flags=re.I
        )
        value = re.sub(r"(?i)(bearer\s+)[\w.\-]+", r"\1[REDACTED]", value)
        value = re.sub(
            r"(?i)((?:password|secret|token|api[_-]?key)\s*[=:]\s*)[^\s,;]+",
            r"\1[REDACTED]",
            value,
        )
        return re.sub(
            r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{16,}|AKIA[A-Z0-9]{16})\b",
            "[REDACTED]",
            value,
        )
    return value


class _Connection(sqlite3.Connection):
    def __exit__(self, *exc):
        try:
            return super().__exit__(*exc)
        finally:
            self.close()


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "sentinel.sqlite3"
        with self.connect() as db:
            exists = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version'"
            ).fetchone()
            if exists:
                versions = [
                    r[0] for r in db.execute("SELECT version FROM schema_version")
                ]
                if versions != [1]:
                    raise ValueError(
                        f"Unsupported Sentinel schema version: {versions}; use a compatible release"
                    )
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS schema_version(version INTEGER NOT NULL);
            INSERT INTO schema_version SELECT 1 WHERE NOT EXISTS(SELECT 1 FROM schema_version);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT UNIQUE NOT NULL,event_type TEXT NOT NULL,timestamp TEXT NOT NULL,session_id TEXT NOT NULL,payload TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS events_session_time ON events(session_id,timestamp);
            CREATE INDEX IF NOT EXISTS events_time ON events(timestamp);
            CREATE TABLE IF NOT EXISTS missions(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS checkpoints(id TEXT PRIMARY KEY,payload TEXT NOT NULL,original BLOB);
            """)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10, factory=_Connection)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def append(self, event_type, identity=None, **data):
        event = redact(
            {
                **data,
                **(identity or {}),
                "event_type": event_type,
                "id": uuid.uuid4().hex,
                "timestamp": now(),
            }
        )
        event["session_id"] = str(event.get("session_id") or "")
        with self.connect() as db:
            cursor = db.execute(
                "INSERT INTO events(id,event_type,timestamp,session_id,payload) VALUES(?,?,?,?,?)",
                (
                    event["id"],
                    event_type,
                    event["timestamp"],
                    event["session_id"],
                    json.dumps(event),
                ),
            )
            event["seq"] = cursor.lastrowid
        return event

    def events(self, limit=100, after=0, session_id="", search=""):
        limit = max(1, min(int(limit), 1000))
        query, params = "SELECT seq,payload FROM events WHERE seq>?", [int(after)]
        if session_id:
            query += " AND session_id=?"
            params.append(session_id)
        if search:
            query += " AND payload LIKE ? ESCAPE '\\'"
            params.append(
                "%"
                + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                + "%"
            )
        with self.connect() as db:
            return [
                {**json.loads(r["payload"]), "seq": r["seq"]}
                for r in db.execute(query + " ORDER BY seq LIMIT ?", params + [limit])
            ]

    def sessions(self):
        with self.connect() as db:
            rows = db.execute(
                "SELECT e.payload,e.seq,c.count FROM events e JOIN (SELECT session_id,MAX(seq) latest,COUNT(*) count FROM events WHERE session_id<>'' GROUP BY session_id) c ON e.seq=c.latest ORDER BY e.seq DESC"
            ).fetchall()
        result = []
        for row in rows:
            event = json.loads(row["payload"])
            result.append(
                {
                    "session_id": event["session_id"],
                    "agent_id": event.get("agent_id"),
                    "mission_id": event.get("mission_id"),
                    "last_event": event["event_type"],
                    "last_seen": event["timestamp"],
                    "event_count": row["count"],
                    "status": "ended"
                    if event["event_type"]
                    in ("session.ended", "on_session_end", "session_ended")
                    else "observed",
                }
            )
        return result

    def stats(self):
        with self.connect() as db:
            counts = {
                r[0]: r[1]
                for r in db.execute(
                    "SELECT event_type,COUNT(*) FROM events GROUP BY event_type"
                )
            }
        return {
            "events": sum(counts.values()),
            "sessions": len(self.sessions()),
            "by_type": counts,
        }

    def save_mission(self, mission):
        if not isinstance(mission, dict):
            raise ValueError("Mission must be an object")
        mission = dict(mission)
        mission.setdefault("id", uuid.uuid4().hex)
        mission.setdefault("status", "DRAFT")
        if mission["status"] not in {
            "DRAFT",
            "ACTIVE",
            "PAUSED",
            "COMPLETED",
            "FAILED",
            "CANCELLED",
        }:
            raise ValueError("Invalid mission status")
        if not isinstance(mission.get("name"), str) or not mission["name"].strip():
            raise ValueError("Mission name is required")
        for field in (
            "allowed_directories",
            "restricted_directories",
            "approved_tools",
            "restricted_tools",
            "network_permissions",
            "allowed_domains",
            "required_approvals",
        ):
            if field in mission and (
                not isinstance(mission[field], list)
                or not all(isinstance(x, str) for x in mission[field])
            ):
                raise ValueError(f"{field} must be a list of strings")
        for field in ("allow_deployment",):
            if field in mission and not isinstance(mission[field], bool):
                raise ValueError(f"{field} must be a boolean")
        for field in (
            "id",
            "session_id",
            "agent_id",
            "description",
            "template",
            "expires_at",
        ):
            if field in mission and not isinstance(mission[field], str):
                raise ValueError(f"{field} must be a string")
        for domain in mission.get("allowed_domains", []):
            if not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?", domain):
                raise ValueError(
                    "allowed_domains must contain hostnames without schemes, paths or wildcards"
                )
        if mission.get("expires_at"):
            parsed = datetime.fromisoformat(
                mission["expires_at"].replace("Z", "+00:00")
            )
            if parsed.tzinfo is None:
                raise ValueError("Mission expiry must include a timezone")
        mission["updated_at"] = now()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if mission.get("session_id") and mission["status"] == "ACTIVE":
                for row in db.execute("SELECT payload FROM missions"):
                    other = json.loads(row[0])
                    if (
                        other["id"] != mission["id"]
                        and other.get("session_id") == mission["session_id"]
                        and other["status"] == "ACTIVE"
                    ):
                        raise ValueError("Session already has an active mission")
            db.execute(
                "INSERT INTO missions VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                (mission["id"], json.dumps(mission)),
            )
        self.append(
            "mission.changed",
            {"session_id": mission.get("session_id", ""), "mission_id": mission["id"]},
            status=mission["status"],
        )
        return mission

    def missions(self):
        with self.connect() as db:
            return [
                json.loads(r[0])
                for r in db.execute("SELECT payload FROM missions ORDER BY rowid DESC")
            ]

    def mission_for_session(self, session_id):
        if not session_id:
            return None
        return next(
            (
                m
                for m in self.missions()
                if m.get("session_id") == session_id
                and m["status"] in ("ACTIVE", "PAUSED")
            ),
            None,
        )

    def retain(self, before):
        """Delete journal entries older than an explicit ISO timestamp."""
        datetime.fromisoformat(before.replace("Z", "+00:00"))
        with self.connect() as db:
            return db.execute(
                "DELETE FROM events WHERE timestamp<?", (before,)
            ).rowcount
