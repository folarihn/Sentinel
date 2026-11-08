"""Authenticated loopback-only Control Room, independent of enforcement."""

from __future__ import annotations

import argparse
import hmac
import json
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import __version__
from .policy import evaluate
from .recovery import Recovery
from .runtime import data_home
from .store import Store
from .templates import TEMPLATES
from .rules import RuleSet


def create_server(root, workspace, port=8765, token=None):
    store = Store(Path(root))
    recovery = Recovery(store, Path(workspace))
    rules = RuleSet(store.root)
    secret = token or secrets.token_urlsafe(32)
    assets = Path(__file__).parent / "web"

    class Handler(BaseHTTPRequestHandler):
        timeout = 15

        def log_message(self, *_):
            pass  # Request bodies and authentication never enter access logs.

        def respond(self, value, status=200):
            payload = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def authorized(self):
            # DNS rebinding and cross-origin browser requests are rejected.
            if self.headers.get("Host") not in {
                f"127.0.0.1:{self.server.server_port}",
                f"localhost:{self.server.server_port}",
            }:
                return False
            origin = self.headers.get("Origin")
            if origin and origin not in {
                f"http://127.0.0.1:{self.server.server_port}",
                f"http://localhost:{self.server.server_port}",
            }:
                return False
            # compare_digest rejects non-ASCII strings; compare encoded bytes so
            # malformed headers receive 401 rather than dropping the connection.
            return hmac.compare_digest(
                self.headers.get("Authorization", "").encode("utf-8"),
                ("Bearer " + secret).encode("utf-8"),
            )

        def do_GET(self):
            url = urlsplit(self.path)
            if not url.path.startswith("/api/"):
                name = {
                    "/": "index.html",
                    "/app.js": "app.js",
                    "/style.css": "style.css",
                    "/fonts/inter.ttf": "fonts/inter.ttf",
                    "/fonts/jetbrains-mono.ttf": "fonts/jetbrains-mono.ttf",
                    "/fonts/instrument-serif.ttf": "fonts/instrument-serif.ttf",
                }.get(url.path)
                if not name or not (assets / name).is_file():
                    return self.respond({"error": "Not found"}, 404)
                payload = (assets / name).read_bytes()
                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    {
                        "html": "text/html",
                        "js": "text/javascript",
                        "css": "text/css",
                        "ttf": "font/ttf",
                    }[name.split(".")[-1]],
                )
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'",
                )
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if not self.authorized():
                return self.respond(
                    {"error": "Local bearer authentication required"}, 401
                )
            try:
                query = parse_qs(url.query)
                if url.path == "/api/status":
                    return self.respond(
                        {
                            "version": __version__,
                            "stats": store.stats(),
                            "sessions": store.sessions(),
                            "mode": "local",
                            "approval_transport": "Hermes native",
                            "enforcement": "Plugin hooks; dashboard connectivity does not attest plugin health",
                        }
                    )
                if url.path == "/api/events":
                    if query.get("tail") == ["1"]:
                        with store.connect() as db:
                            rows = db.execute(
                                "SELECT seq,payload FROM events ORDER BY seq DESC LIMIT 500"
                            ).fetchall()
                        return self.respond(
                            [
                                {**json.loads(row["payload"]), "seq": row["seq"]}
                                for row in reversed(rows)
                            ]
                        )
                    return self.respond(
                        store.events(
                            limit=min(500, max(1, int(query.get("limit", [100])[0]))),
                            after=max(0, int(query.get("after", [0])[0])),
                            session_id=query.get("session_id", [""])[0],
                            search=query.get("search", [""])[0],
                        )
                    )
                if url.path == "/api/templates":
                    return self.respond(TEMPLATES)
                if url.path == "/api/policies":
                    return self.respond(rules.load())
                if url.path == "/api/sessions":
                    return self.respond(store.sessions())
                if url.path == "/api/missions":
                    missions = store.missions()
                    for mission in missions:
                        mission["display_allowed_directories"] = [
                            Path(path)
                            .resolve()
                            .relative_to(recovery.workspace)
                            .as_posix()
                            if Path(path).is_absolute()
                            and Path(path).resolve().is_relative_to(recovery.workspace)
                            else path
                            for path in mission.get("allowed_directories", [])
                        ]
                    return self.respond(missions)
                if url.path == "/api/checkpoints":
                    points = recovery.checkpoints()
                    for point in points:
                        path = Path(point["path"])
                        if path.is_relative_to(recovery.workspace):
                            point["display_path"] = path.relative_to(
                                recovery.workspace
                            ).as_posix()
                    return self.respond(points)
                return self.respond({"error": "Not found"}, 404)
            except (ValueError, TypeError) as exc:
                return self.respond({"error": str(exc)}, 400)
            except Exception:
                return self.respond({"error": "Storage unavailable"}, 503)

        def do_POST(self):
            if not self.authorized():
                return self.respond(
                    {"error": "Local bearer authentication required"}, 401
                )
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 262144:
                    return self.respond(
                        {"error": "Request body must be 1–262144 bytes"}, 413
                    )
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("Request body must be a JSON object")
                path = urlsplit(self.path).path
                if path == "/api/evaluate":
                    identity = body.get("identity", {})
                    if (
                        not isinstance(identity, dict)
                        or not isinstance(body.get("args", {}), dict)
                        or not isinstance(body.get("tool_name"), str)
                    ):
                        raise ValueError(
                            "Evaluation requires a tool name and object arguments/identity"
                        )
                    identity["protected_directories"] = [
                        str(store.root),
                        str(Path(__file__).resolve().parent.parent),
                    ]
                    decision = evaluate(
                        body["tool_name"],
                        body.get("args", {}),
                        identity,
                        store.mission_for_session(identity.get("session_id", "")),
                    )
                    custom = rules.evaluate(
                        body["tool_name"], body.get("args", {}), identity
                    )
                    if (
                        custom
                        and decision["decision"] != "BLOCK"
                        and (
                            custom["decision"] == "BLOCK"
                            or decision["decision"] == "ALLOW"
                        )
                    ):
                        decision = custom
                    return self.respond(decision)
                if path == "/api/policies":
                    saved = rules.save(body)
                    store.append("policy_changed", rule_count=len(saved["rules"]))
                    return self.respond(saved)
                if path == "/api/missions":
                    template = body.get("template")
                    if template:
                        if template not in TEMPLATES:
                            raise ValueError("Unknown mission template")
                        body = {**TEMPLATES[template], **body}
                    return self.respond(store.save_mission(body), 201)
                if path == "/api/retention":
                    return self.respond({"deleted": store.retain(body["before"])})
                if path.startswith("/api/missions/"):
                    mid = path.removeprefix("/api/missions/")
                    mission = next(
                        (m for m in store.missions() if m["id"] == mid), None
                    )
                    if mission is None:
                        return self.respond({"error": "Mission not found"}, 404)
                    return self.respond(
                        store.save_mission({**mission, **body, "id": mid})
                    )
                if path == "/api/checkpoints":
                    return self.respond(recovery.checkpoint(body["path"]), 201)
                if path == "/api/checkpoints/seal":
                    return self.respond(recovery.seal(body["id"]))
                if path == "/api/restore":
                    return self.respond(
                        recovery.restore(
                            body["id"], authorized=body.get("authorized") is True
                        )
                    )
                return self.respond({"error": "Not found"}, 404)
            except (
                ValueError,
                TypeError,
                KeyError,
                PermissionError,
                FileNotFoundError,
            ) as exc:
                return self.respond({"error": str(exc)}, 400)
            except Exception:
                return self.respond(
                    {"error": "Operation failed; inspect local state"}, 409
                )

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.auth_token = secret
    return server


def main():
    parser = argparse.ArgumentParser(description="SENTINEL OS local Control Room")
    parser.add_argument("--data", type=Path, default=data_home())
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = create_server(
        args.data, args.workspace, args.port, os.environ.get("SENTINEL_TOKEN")
    )
    print(f"Control Room: http://127.0.0.1:{server.server_port}")
    print(f"Session token (enter locally, never share): {server.auth_token}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
