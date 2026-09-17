"""Make the local PostgreSQL database an exact restore of Vercel production.

The command deliberately creates two custom-format dumps: one safety backup of
the current local database and one immutable copy of the production snapshot.
Credentials are read from the ignored Vercel env export and never printed.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
from urllib.parse import parse_qs, unquote, urlparse

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]
BACKUPS = ROOT / "output" / "sync-backups"
ENV_FILE = ROOT / "output" / "vercel.production.env"


def run(command: list[str], *, stdout=None, stdin=None, env=None) -> None:
    subprocess.run(command, cwd=ROOT, check=True, stdout=stdout, stdin=stdin, env=env)


def production_pg_env(database_url: str) -> tuple[list[str], dict[str, str]]:
    parsed = urlparse(database_url.replace("postgresql+psycopg://", "postgresql://", 1))
    if not parsed.hostname or not parsed.path:
        raise SystemExit("The production DATABASE_URL is not a valid PostgreSQL URL.")
    query = parse_qs(parsed.query)
    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = unquote(parsed.password)
    env["PGSSLMODE"] = query.get("sslmode", ["require"])[0]
    if "channel_binding" in query:
        env["PGCHANNELBINDING"] = query["channel_binding"][0]
    command = [
        "/opt/homebrew/bin/pg_dump",
        "--host", parsed.hostname,
        "--port", str(parsed.port or 5432),
        "--username", unquote(parsed.username or "postgres"),
        "--dbname", parsed.path.lstrip("/"),
        "--format", "custom",
        "--no-owner",
        "--no-privileges",
    ]
    return command, env


def main() -> None:
    values = dotenv_values(ENV_FILE)
    database_url = values.get("DATABASE_URL") or values.get("POSTGRES_URL")
    if not database_url:
        raise SystemExit("No production DATABASE_URL was found in output/vercel.production.env.")

    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    local_dump = BACKUPS / f"local-before-production-{stamp}.dump"
    production_dump = BACKUPS / f"production-{stamp}.dump"

    with local_dump.open("wb") as output:
        run([
            "docker", "compose", "exec", "-T", "postgres", "pg_dump",
            "-U", "bytecode", "-d", "bytecode", "-Fc", "--no-owner", "--no-privileges",
        ], stdout=output)

    dump_command, dump_env = production_pg_env(database_url)
    with production_dump.open("wb") as output:
        run(dump_command, stdout=output, env=dump_env)

    # Production is currently PostgreSQL 17+, while the Docker demonstration
    # uses PostgreSQL 16. Convert the custom archive with the newer host client
    # and remove its one newer-server session setting before loading it.
    compatible_sql = production_dump.with_suffix(".public.sql")
    run([
        "/opt/homebrew/bin/pg_restore", "--schema=public", "--no-owner", "--no-privileges",
        "--file", str(compatible_sql), str(production_dump),
    ])
    compatible_sql.write_text(compatible_sql.read_text().replace("SET transaction_timeout = 0;\n", ""))

    run(["docker", "compose", "stop", "backend", "frontend", "mock-gov-api"])
    run([
        "docker", "compose", "exec", "-T", "postgres", "psql", "-U", "bytecode", "-d", "bytecode",
        "-v", "ON_ERROR_STOP=1", "-c",
        "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO bytecode;",
    ])
    local_env = os.environ.copy()
    local_env["PGPASSWORD"] = os.environ.get("POSTGRES_PASSWORD", "bytecode_local_demo")
    with compatible_sql.open("rb") as source:
        run([
            "/opt/homebrew/bin/psql", "--host", "127.0.0.1", "--port", "55432",
            "--username", "bytecode", "--dbname", "bytecode", "--set", "ON_ERROR_STOP=on",
        ], stdin=source, env=local_env)
    run(["docker", "compose", "up", "-d", "--wait"])

    print(f"Local backup: {local_dump.relative_to(ROOT)}")
    print(f"Production snapshot: {production_dump.relative_to(ROOT)}")
    print("Local database is now restored from the production snapshot.")


if __name__ == "__main__":
    main()
