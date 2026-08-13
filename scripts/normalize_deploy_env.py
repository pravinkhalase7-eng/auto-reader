#!/usr/bin/env python3
"""Normalize a Jenkins/VPS .env file for Docker Compose and bash source.

- Maps GOOGLE_API_KEY → GOOGLE_AI_API_KEY
- Rebuilds DATABASE_URL from POSTGRES_* with a URL-encoded password
  (so characters like # do not become URL fragments)
- Quotes values that would break bash/compose (e.g. Pravin#123)
"""

from __future__ import annotations

import re
import sys
import urllib.parse
from pathlib import Path

SPECIAL = re.compile(r"""[\s#"'$\\]""")


def parse_env(text: str) -> list[tuple[str, str] | str]:
    rows: list[tuple[str, str] | str] = []
    for raw in text.splitlines():
        line = raw.strip("\ufeff")
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            rows.append(raw.rstrip("\n"))
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in {"'", '"'}:
            val = val[1:-1]
        rows.append((key, val))
    return rows


def env_map(rows: list[tuple[str, str] | str]) -> dict[str, str]:
    data: dict[str, str] = {}
    for row in rows:
        if isinstance(row, tuple):
            data[row[0]] = row[1]
    return data


def quote(val: str) -> str:
    if not val or SPECIAL.search(val):
        return "'" + val.replace("'", "'\\''") + "'"
    return val


def format_rows(rows: list[tuple[str, str] | str]) -> str:
    lines: list[str] = []
    for row in rows:
        if isinstance(row, str):
            lines.append(row)
        else:
            lines.append(f"{row[0]}={quote(row[1])}")
    return "\n".join(lines) + "\n"


def upsert(rows: list[tuple[str, str] | str], key: str, value: str) -> list[tuple[str, str] | str]:
    found = False
    out: list[tuple[str, str] | str] = []
    for row in rows:
        if isinstance(row, tuple) and row[0] == key:
            out.append((key, value))
            found = True
        else:
            out.append(row)
    if not found:
        out.append((key, value))
    return out


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--"]
    get_key = None
    public_api = None
    path = Path(".env.deploy")
    i = 0
    while i < len(args):
        if args[i] == "--get":
            get_key = args[i + 1]
            i += 2
            continue
        if args[i] == "--public-api-url":
            public_api = args[i + 1]
            i += 2
            continue
        if not args[i].startswith("-"):
            path = Path(args[i])
        i += 1

    text = path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    rows = parse_env(text)
    data = env_map(rows)

    if get_key:
        sys.stdout.write(data.get(get_key, ""))
        return 0

    google = (data.get("GOOGLE_AI_API_KEY") or "").strip()
    alias = (data.get("GOOGLE_API_KEY") or "").strip()
    if not google and alias:
        rows = upsert(rows, "GOOGLE_AI_API_KEY", alias)
        data = env_map(rows)
        print("Mapped GOOGLE_API_KEY → GOOGLE_AI_API_KEY")

    if public_api:
        rows = upsert(rows, "NEXT_PUBLIC_API_URL", public_api)
        print("PUBLIC_API_URL applied")

    user = (data.get("POSTGRES_USER") or "aiteacher").strip() or "aiteacher"
    password = data.get("POSTGRES_PASSWORD") or ""
    db = (data.get("POSTGRES_DB") or "aiteacher").strip() or "aiteacher"
    if password:
        encoded = urllib.parse.quote(password, safe="")
        url = f"postgresql+asyncpg://{user}:{encoded}@postgres:5432/{db}"
        rows = upsert(rows, "DATABASE_URL", url)
        print("DATABASE_URL synced from POSTGRES_USER/PASSWORD/DB (password URL-encoded)")
        if "#" in password:
            print("Quoted POSTGRES_PASSWORD because it contains # (not a comment)")

    path.write_text(format_rows(rows), encoding="utf-8")

    data = env_map(parse_env(path.read_text(encoding="utf-8")))
    print("=== .env key check (values hidden) ===")
    missing = False
    for key in ("SECRET_KEY", "DATABASE_URL", "NEXT_PUBLIC_API_URL", "CORS_ORIGINS", "POSTGRES_PASSWORD", "GOOGLE_AI_API_KEY"):
        ok = bool((data.get(key) or "").strip())
        print(f"{key}={'SET' if ok else 'MISSING'}")
        if not ok and key != "GOOGLE_AI_API_KEY":
            missing = True
    if not (data.get("GOOGLE_AI_API_KEY") or "").strip():
        print("WARN: GOOGLE_AI_API_KEY is empty — story pictures will not draw.")
    if missing:
        print("ERROR: required deploy keys are missing from the env file.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
