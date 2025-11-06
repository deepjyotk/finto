#!/usr/bin/env python3
import os, sys
from pathlib import Path
import psycopg
from psycopg.rows import tuple_row

import sqlparse 
from dotenv import load_dotenv


load_dotenv()
# Expect DATABASE_URL in env, e.g.:
# postgresql://postgres:<DB_PASSWORD>@db.<ref>.supabase.co:5432/postgres?sslmode=require
DATABASE_URL = os.getenv("DATABASE_URL")


def get_migration_files() -> list[Path]:
    d = Path(__file__).parent / "scripts/migrations"
    if not d.exists():
        print(f"❌ Migrations directory not found: {d}")
        return []
    return sorted(d.glob("*.sql"))

def run_sql_file(conn: psycopg.Connection, path: Path) -> None:
    print(f"📄 Running migration: {path.name}")
    sql = path.read_text(encoding="utf-8")
    # Split safely on top-level semicolons
    for i, stmt in enumerate(sqlparse.split(sql), 1):
        s = stmt.strip()
        if not s:
            continue
        try:
            with conn.cursor() as cur:
                cur.execute(s)
            print(f"   ✅ Statement {i} ok")
        except Exception as e:
            print(f"   ❌ Statement {i} failed: {e}")
            raise
    print(f"✅ Migration {path.name} completed")

def verify_table_exists(conn: psycopg.Connection, table: str) -> bool:
    try:
        with conn.cursor(row_factory=tuple_row) as cur:
            cur.execute("select 1 from information_schema.tables where table_name=%s", (table,))
            exists = cur.fetchone() is not None
        if exists:
            # Also check SELECT permission
            with conn.cursor() as cur:
                cur.execute(f"select 1 from {table} limit 0")
            print(f"✅ Table '{table}' exists and is accessible")
            return True
        print(f"❌ Table '{table}' not found")
        return False
    except Exception as e:
        print(f"❌ Verification error for '{table}': {e}")
        return False

def main():
    print("=" * 60)
    print("🚀 Finto Database Initialization (Direct Postgres)")
    print("=" * 60)

    if not DATABASE_URL:
        print("\n❌ ERROR: DATABASE_URL not set.")
        print("Get it from Supabase → Project → Settings → Database → Connection string")
        print("Use the Postgres URI and include your Database Password, plus `?sslmode=require`.")
        sys.exit(1)

    try:
        print("\n📡 Connecting to Postgres (SSL required)...")
        with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
            print("✅ Connected")

            files = get_migration_files()
            if not files:
                sys.exit(1)

            for f in files:
                run_sql_file(conn, f)

            print("\n🔍 Verifying tables…")
            ok = all(verify_table_exists(conn, t) for t in ["f_users"])

            print("\n" + "=" * 60)
            if ok:
                print("✅ Database initialization completed successfully!")
                print("  make run-apis  # Start the backend")
                print("  make run-ui    # Start the frontend")
            else:
                print("❌ Database initialization incomplete"); sys.exit(1)
    except Exception as e:
        print(f"❌ Failed: {e}"); sys.exit(1)

if __name__ == "__main__":
    main()
