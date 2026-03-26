"""
SQLite database connection management.
"""

import logging
import os
import sqlite3
from pathlib import Path

logger = logging.getLogger("o2c.db")

DB_PATH = Path(os.environ.get("DB_PATH", Path(__file__).resolve().parent / "data" / "o2c.db"))

MAX_ROWS = 500  # Safety cap on returned rows


def get_connection(readonly: bool = True) -> sqlite3.Connection:
    """Get a SQLite connection. Read-only by default for safety."""
    if readonly:
        uri = f"file:{DB_PATH}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_schema() -> str:
    """Return the full database schema as CREATE TABLE statements."""
    conn = get_connection()
    cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name")
    statements = [row[0] for row in cursor.fetchall() if row[0]]
    conn.close()
    return "\n\n".join(statements)


def get_table_info() -> dict[str, list[dict]]:
    """Return column info for all tables."""
    conn = get_connection()
    tables = {}
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    for (table_name,) in cursor.fetchall():
        cols = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        tables[table_name] = [{"name": c[1], "type": c[2]} for c in cols]
    conn.close()
    return tables


def execute_readonly_query(sql: str) -> tuple[list[str], list[list]]:
    """Execute a read-only SQL query and return (column_names, rows).
    
    Raises ValueError if the SQL contains dangerous statements.
    """
    # Safety check
    forbidden = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "ATTACH", "DETACH"]
    sql_upper = sql.upper().strip()
    for keyword in forbidden:
        if sql_upper.startswith(keyword) or f"; {keyword}" in sql_upper.replace("\n", " "):
            raise ValueError(f"Forbidden SQL operation: {keyword}")

    conn = get_connection(readonly=True)
    try:
        cursor = conn.execute(sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = [list(row) for row in cursor.fetchmany(MAX_ROWS)]
        logger.info("Executed query (%d cols, %d rows): %s", len(columns), len(rows), sql[:120])
        return columns, rows
    except Exception as e:
        logger.warning("Query failed: %s | %s", e, sql[:200])
        raise
    finally:
        conn.close()
