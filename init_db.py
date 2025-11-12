#!/usr/bin/env python3
import asyncio
import os
import re
import ssl
from pathlib import Path

import asyncpg
import sqlparse
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")  # e.g. postgresql://...  (Supabase OK)

MIGRATIONS_DIR = Path(__file__).parent / "scripts" / "migrations"
SAFE_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def get_migration_files() -> list[Path]:
    if not MIGRATIONS_DIR.exists():
        print(f"❌ Migrations directory not found: {MIGRATIONS_DIR}")
        return []
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def quote_ident(name: str) -> str:
    """Minimal identifier safety. If it doesn't look like a bare identifier, refuse."""
    if not SAFE_IDENT.match(name):
        raise ValueError(f"Unsafe identifier: {name!r}")
    return f'"{name}"'  # preserve case if you use mixed-case identifiers


async def run_sql_file(conn: asyncpg.Connection, path: Path) -> None:
    print(f"📄 Running migration: {path.name}")
    sql = path.read_text(encoding="utf-8")

    stmt_count = 0
    for stmt in sqlparse.split(sql):
        s = stmt.strip()
        # Skip empty statements and comment-only lines
        if not s or s.startswith("--"):
            continue

        # Remove comments but keep the statement
        parsed = sqlparse.parse(s)
        if not parsed:
            continue

        stmt_count += 1
        try:
            # asyncpg executes one statement per call; splitting is required for multi-stmt files.
            await conn.execute(s)
            print(f"   ✅ Statement {stmt_count} ok")
        except Exception as e:
            print(f"   ❌ Statement {stmt_count} failed: {e}")
            print(f"   Statement was: {s[:200]}...")
            raise
    print(f"✅ Migration {path.name} completed ({stmt_count} statements)")


async def verify_table_exists(conn: asyncpg.Connection, table: str) -> bool:
    try:
        # Portable existence check
        exists = await conn.fetchval(
            "select 1 from information_schema.tables "
            "where table_name = $1 and table_schema in ('public', current_schema())",
            table,
        )
        if not exists:
            print(f"❌ Table '{table}' not found")
            return False

        # Check accessibility (simple SELECT 0-row)
        q = f"select 1 from {quote_ident(table)} limit 0"
        await conn.execute(q)
        print(f"✅ Table '{table}' exists and is accessible")
        return True
    except Exception as e:
        print(f"❌ Verification error for '{table}': {e}")
        return False


async def amain() -> int:
    print("=" * 60)
    print("🚀 Finto Database Initialization (Direct Postgres via asyncpg)")
    print("=" * 60)

    if not DATABASE_URL:
        print("\n❌ ERROR: DATABASE_URL not set.")
        print("Get it from Supabase → Project → Settings → Database → Connection string")
        print("Use the Postgres URI and ensure SSL is enabled.")
        return 1

    try:
        print("\n📡 Connecting to Postgres (SSL)…")
        # Create SSL context that accepts self-signed certificates
        # For production, use proper certificate verification
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        conn = await asyncpg.connect(DATABASE_URL, ssl=ssl_context, timeout=60)
        print("✅ Connected")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return 1

    try:
        files = get_migration_files()
        if not files:
            return 1

        # Run migrations inside a single transaction so a failed file rolls everything back
        async with conn.transaction():
            for f in files:
                await run_sql_file(conn, f)

        print("\n🔍 Verifying tables…")
        ok = await verify_table_exists(conn, "f_users")

        print("\n" + "=" * 60)
        if ok:
            print("✅ Database initialization completed successfully!")
            print("  make run-apis  # Start the backend")
            print("  make run-ui    # Start the frontend")
            return 0
        else:
            print("❌ Database initialization incomplete")
            return 1
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
