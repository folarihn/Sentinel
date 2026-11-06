"""Audit the git-tracked working snapshot without printing matched values.

This is a conservative release aid, not proof that arbitrary secrets or image
pixels are safe. Git history and untracked files are intentionally out of scope.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import struct
import subprocess
import sys
import zlib
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
GENERIC_USERS = {
    "user",
    "username",
    "your-user",
    "your-username",
    "example",
    "example-user",
}
PATTERNS = {
    "credential-token": re.compile(
        r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16}|xox[baprs]-[A-Za-z0-9-]{20,})\b"
    ),
    "private-key": re.compile(
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
    ),
    "credential-assignment": re.compile(
        r"""(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password)\b["']?\s*[:=]\s*["']([^"'\r\n]{12,})["']"""
    ),
    "url-credentials": re.compile(r"(?i)https?://[^\s/:@]+:[^\s/@]+@"),
}
HOME_PATH = re.compile(
    r"(?i)(?:\b[A-Z]:(?:\\+|/)Users(?:\\+|/)|/(?:home|Users)/)([^\\/\r\n\"<>]+)"
)
URL = re.compile(r"(?i)https?://[^\s\"'<>]+")
IP = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
PLACEHOLDER = re.compile(
    r"(?i)(?:example|placeholder|redacted|synthetic|fixture|your[-_ ]|changeme|replace[-_ ]|test[-_ ]|<|\$\{|%[A-Z_]+%|\[redacted)"
)


def _fixture(path: str) -> bool:
    parts = Path(path).parts
    return (
        "tests" in parts or "fixtures" in parts or Path(path).name.startswith("test_")
    )


def scan_text(path: str, text: str, *, source="text") -> list[dict]:
    """Return locations/categories/severities only; never matched substrings."""
    findings = []
    fixture = _fixture(path)
    for number, line in enumerate(text.splitlines(), 1):
        categories = set()
        for category, pattern in PATTERNS.items():
            for match in pattern.finditer(line):
                # Assignments often document placeholders or regex patterns.
                if category == "credential-assignment" and PLACEHOLDER.search(
                    match.group(1)
                ):
                    continue
                categories.add(category)
        for match in HOME_PATH.finditer(line):
            username = match.group(1).strip().lower()
            if username not in GENERIC_USERS and not PLACEHOLDER.search(username):
                categories.add("personal-home-path")
        for match in IP.finditer(line):
            try:
                address = ipaddress.ip_address(match.group())
            except ValueError:
                continue
            if (
                address.is_private
                and not address.is_loopback
                and not address.is_unspecified
            ):
                # RFC 5737 addresses are documentation values, not private LAN.
                if not any(
                    address in network
                    for network in (
                        ipaddress.ip_network("192.0.2.0/24"),
                        ipaddress.ip_network("198.51.100.0/24"),
                        ipaddress.ip_network("203.0.113.0/24"),
                    )
                ):
                    categories.add("private-network-address")
        for match in URL.finditer(line.replace("\\/", "/")):
            try:
                host = (urlsplit(match.group()).hostname or "").lower().rstrip(".")
            except ValueError:
                continue
            if host.endswith(
                (".local", ".internal", ".lan")
            ) and not PLACEHOLDER.search(host):
                categories.add("private-network-host")
        for category in sorted(categories):
            findings.append(
                {
                    "file": path,
                    "line": number,
                    "category": category,
                    "severity": "review" if fixture else "fail",
                    "source": source,
                }
            )
    return findings


def _image_metadata(data: bytes, suffix: str):
    """Extract textual PNG chunks/JPEG APP segments, without decoding pixels.

    Other formats get a conservative printable-string pass. This is not OCR.
    """
    if suffix == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n"):
        offset = 8
        while offset + 12 <= len(data):
            size = struct.unpack(">I", data[offset : offset + 4])[0]
            kind = data[offset + 4 : offset + 8]
            payload = data[offset + 8 : offset + 8 + size]
            if kind in {b"tEXt", b"iTXt", b"eXIf"}:
                yield payload.decode("utf-8", errors="replace")
            elif kind == b"zTXt":
                try:
                    encoded = payload.split(b"\0", 1)[1]
                    decompressor = zlib.decompressobj()
                    yield decompressor.decompress(encoded[1:], 1024 * 1024).decode(
                        "utf-8", errors="replace"
                    )
                except (IndexError, zlib.error):
                    pass
            offset += size + 12
    else:
        # EXIF, XMP and JPEG comments are typically ASCII/UTF-8. UTF-16 strings
        # also get a pass; pixels are not interpreted as proof of safe content.
        for match in re.finditer(rb"[\x20-\x7e]{8,}", data):
            yield match.group().decode("ascii")
        yield data.decode("utf-16-le", errors="ignore")


def audit(root: Path, paths: list[str] | None = None) -> dict:
    root = root.resolve()
    if paths is None:
        result = subprocess.run(
            ["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True
        )
        paths = [path for path in result.stdout.decode("utf-8").split("\0") if path]
    findings = []
    images = []
    for relative in sorted(paths):
        target = root / relative
        findings.extend(scan_text(relative, relative, source="tracked-path"))
        if target.is_symlink() or not target.is_file():
            findings.append(
                {
                    "file": relative,
                    "line": 0,
                    "category": "unreadable-or-symlink-tracked-file",
                    "severity": "review",
                    "source": "tracked-path",
                }
            )
            continue
        data = target.read_bytes()
        if target.suffix.lower() in IMAGE_SUFFIXES:
            images.append(relative)
            for metadata in _image_metadata(data, target.suffix.lower()):
                findings.extend(scan_text(relative, metadata, source="image-metadata"))
            findings.append(
                {
                    "file": relative,
                    "line": 0,
                    "category": "image-pixels-require-human-review",
                    "severity": "review",
                    "source": "image-pixels",
                }
            )
        else:
            try:
                decoded = data.decode("utf-8")
            except UnicodeDecodeError:
                findings.append(
                    {
                        "file": relative,
                        "line": 0,
                        "category": "binary-requires-review",
                        "severity": "review",
                        "source": "binary",
                    }
                )
            else:
                findings.extend(scan_text(relative, decoded))
    # Duplicate metadata representations do not inflate the result.
    findings = list({tuple(sorted(item.items())): item for item in findings}.values())
    return {
        "scope": "git-tracked working snapshot; excludes git history and untracked files",
        "scanned_files": len(paths),
        "image_files": images,
        "counts": dict(Counter(item["severity"] for item in findings)),
        "categories": dict(Counter(item["category"] for item in findings)),
        "findings": findings,
        "limitations": [
            "Pattern matching cannot prove absence of arbitrary secrets.",
            "Image pixels are not OCR-scanned; review every listed image visually.",
            "Current-snapshot cleanup does not remove earlier committed sensitive data from Git history.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    report = audit(args.root)
    print(json.dumps(report, indent=2))
    return 1 if report["counts"].get("fail", 0) else 0


if __name__ == "__main__":
    sys.exit(main())
