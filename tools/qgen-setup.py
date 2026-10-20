#!/usr/bin/env python3
"""qgen-setup.py — one-command run setup for a lean generation session (no network writes).

Builds the admin env file the tools read (default /dev/shm/qgen-admin.env, mode 0600) from
environment variables, then runs read-only preflight checks. Values are NEVER printed — only
key names and ok/missing.

    python3 tools/qgen-setup.py [--out /dev/shm/qgen-admin.env] [--check-only]

Keys (env var → env-file line; first non-empty source wins):
  NEXT_PUBLIC_API_BASE_URL      env, else Vibhaga-Admin/.env.local
  NEXT_PUBLIC_SUPABASE_URL      env (Vibhaga-Admin/.env.local may hold a dead project — not read)
  NEXT_PUBLIC_SUPABASE_ANON_KEY env
  VIBHAGA_ADMIN_EMAIL / VIBHAGA_ADMIN_PASSWORD   env (bind the Vibhaga-Admin repo secrets)
  CF_ACCESS_CLIENT_ID / CF_ACCESS_CLIENT_SECRET  env
  VIBHAGA_ADMIN_AUTH_DB_URL     env (optional — Q3 falls back to DATABASE_URL)
  DATABASE_URL                  env (bind the Vibhaga-DB repo secret)
Then: export VIBHAGA_ADMIN_ENV=<out> for every later command.
Exit: 0 ready · 2 something required is missing (named).
"""
from __future__ import annotations

import argparse, os, shutil, subprocess, sys, urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
REQUIRED = ["NEXT_PUBLIC_API_BASE_URL", "NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_ANON_KEY",
            "VIBHAGA_ADMIN_EMAIL", "VIBHAGA_ADMIN_PASSWORD", "CF_ACCESS_CLIENT_ID", "CF_ACCESS_CLIENT_SECRET",
            "DATABASE_URL"]
OPTIONAL = ["VIBHAGA_ADMIN_AUTH_DB_URL"]


def read_dotenv(p: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if p.is_file():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def sibling(name: str, env_key: str, environ=os.environ) -> Path:
    return Path(environ[env_key]) if environ.get(env_key) else PLUGIN.parent / name


def collect(environ=os.environ) -> tuple[dict[str, str], list[str]]:
    admin_local = read_dotenv(sibling("Vibhaga-Admin", "VIBHAGA_ADMIN", environ) / ".env.local")
    vals: dict[str, str] = {}
    for k in REQUIRED + OPTIONAL:
        v = environ.get(k) or (admin_local.get(k) if k == "NEXT_PUBLIC_API_BASE_URL" else None)
        if v: vals[k] = v
    return vals, [k for k in REQUIRED if k not in vals]


def write_env(path: Path, vals: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    old = os.umask(0o077)
    try:
        path.write_text("".join(f"{k}={v}\n" for k, v in vals.items()), encoding="utf-8")
    finally:
        os.umask(old)
    path.chmod(0o600)


def preflight(vals: dict[str, str]) -> list[str]:
    problems = []
    corpus = sibling("Vibhaga-Maths-Corpus", "VIBHAGA_CORPUS")
    if not (corpus / "maths").is_dir(): problems.append(f"corpus checkout not found at {corpus}")
    for tool in ("psql", "node"):
        if not shutil.which(tool): problems.append(f"{tool} not on PATH")
    try:
        import yaml  # noqa: F401
    except ImportError:
        problems.append("PyYAML missing (pip install pyyaml)")
    if "DATABASE_URL" in vals and shutil.which("psql"):
        pg = pg_env(vals["DATABASE_URL"])
        if pg is None:
            problems.append("content DB: DATABASE_URL is not a postgres URL (needs host + user)")
        else:
            r = subprocess.run(["psql", "-X", "-A", "-t", "-w", "-c", "SELECT 1"], capture_output=True, text=True,
                               env={**os.environ, "PGCONNECT_TIMEOUT": "10", **pg})
            if r.returncode != 0 or r.stdout.strip() != "1": problems.append("content DB: SELECT 1 failed (check DATABASE_URL)")
    return problems


def pg_env(url: str) -> dict | None:
    """postgres URL → libpq env vars (libpq never expands a URL held in PGDATABASE, and argv
    would expose the password). `?sslmode=` honoured; default `require`. None if malformed."""
    try:
        u = urllib.parse.urlsplit(url)
        port = u.port
    except ValueError:
        return None
    if not u.hostname or not u.username:
        return None
    q = urllib.parse.parse_qs(u.query)
    return {"PGHOST": u.hostname, "PGPORT": str(port or 5432),
            "PGUSER": urllib.parse.unquote(u.username),
            "PGPASSWORD": urllib.parse.unquote(u.password or ""),
            "PGDATABASE": urllib.parse.unquote(u.path.lstrip("/")) or "postgres",
            "PGSSLMODE": (q.get("sslmode") or ["require"])[0]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="qgen-setup.py", description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="/dev/shm/qgen-admin.env")
    ap.add_argument("--check-only", action="store_true", help="do not write the env file")
    a = ap.parse_args(argv)
    vals, missing = collect()
    for k in REQUIRED + OPTIONAL:
        print(f"  {k}: {'ok' if k in vals else ('MISSING' if k in REQUIRED else 'absent (optional)')}")
    if missing:
        print(f"qgen-setup: missing {', '.join(missing)} — bind the repo secrets in the shell env and re-run")
        return 2
    if not a.check_only:
        write_env(Path(a.out), vals)
        print(f"qgen-setup: wrote {a.out} (0600) — export VIBHAGA_ADMIN_ENV={a.out}")
    problems = preflight(vals)
    for p in problems: print(f"qgen-setup: PROBLEM {p}")
    if problems: return 2
    print("qgen-setup: ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
