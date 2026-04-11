"""
db.py — Database Connector
--------------------------
Handles the Stage 1 → 2 → 3 migration path:
  Stage 1: SQLite  (DB_STAGE=sqlite)
  Stage 2: DuckDB  (DB_STAGE=duckdb)
  Stage 3: Snowflake (DB_STAGE=snowflake)

The Query Agent always calls execute_query() — it never
touches the underlying connection directly.
"""

import os
import sqlite3
from typing import Any

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

DB_STAGE = os.getenv("DB_STAGE", "sqlite")
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "data/fmcg.db")


def get_connection():
    """Return a database connection for the current stage."""
    if DB_STAGE == "sqlite":
        return sqlite3.connect(SQLITE_DB_PATH)

    elif DB_STAGE == "duckdb":
        import duckdb
        return duckdb.connect(SQLITE_DB_PATH.replace(".db", ".duckdb"))

    elif DB_STAGE == "snowflake":
        import snowflake.connector
        return snowflake.connector.connect(
            account=os.getenv("SNOWFLAKE_ACCOUNT"),
            user=os.getenv("SNOWFLAKE_USER"),
            password=os.getenv("SNOWFLAKE_PASSWORD"),
            database=os.getenv("SNOWFLAKE_DATABASE"),
            schema=os.getenv("SNOWFLAKE_SCHEMA"),
            warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        )
    else:
        raise ValueError(f"Unknown DB_STAGE: {DB_STAGE}")


def execute_query(sql: str, params: dict | None = None) -> pd.DataFrame:
    """
    Execute a parameterised SQL query and return a DataFrame.
    The Query Agent calls this — it never builds raw connections itself.
    
    ALLOWED: Read queries only. Any write/update/delete raises an error.
    """
    sql_upper = sql.strip().upper()
    if any(sql_upper.startswith(kw) for kw in ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER"]):
        raise PermissionError(
            "Write operations are not permitted. The assistant is read-only."
        )

    conn = get_connection()
    try:
        if DB_STAGE == "sqlite":
            df = pd.read_sql_query(sql, conn)
        elif DB_STAGE == "duckdb":
            df = conn.execute(sql).df()
        elif DB_STAGE == "snowflake":
            cursor = conn.cursor()
            cursor.execute(sql)
            cols = [desc[0].lower() for desc in cursor.description]
            df = pd.DataFrame(cursor.fetchall(), columns=cols)
        return df
    finally:
        conn.close()
