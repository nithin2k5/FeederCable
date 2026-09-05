import mysql.connector
from contextlib import contextmanager

DB_CONFIG = {
    "host": "localhost",
    "database": "feeder",
    "user": "root",
    "password": "12345",
    "use_pure": True
}

def get_connection():
    """Returns a new connection to the database."""
    return mysql.connector.connect(**DB_CONFIG)

def ensure_column(table: str, column: str, coltype: str):
    """Add a column to an existing table if it isn't there yet.

    Idempotent and safe to call on every startup against a live DB that
    predates the column -- init_db.py's CREATE TABLE IF NOT EXISTS only
    covers a fresh install, it never alters a table that already exists.
    """
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
    except mysql.connector.Error as e:
        if e.errno != 1060:  # 1060 = ER_DUP_FIELDNAME, i.e. already added
            raise

def widen_column(table: str, column: str, coltype: str):
    """Widen an existing column's type in place. Idempotent -- re-running a
    MODIFY COLUMN to the same type is a harmless no-op."""
    with get_cursor(commit=True) as cur:
        cur.execute(f"ALTER TABLE {table} MODIFY COLUMN {column} {coltype}")

@contextmanager
def get_cursor(commit=False):
    """
    Context manager that yields a database cursor.
    Automatically closes the cursor and connection when done.
    If commit=True, it commits the transaction before closing on success.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
        if commit:
            conn.commit()
    finally:
        if 'cur' in locals() and cur is not None:
            cur.close()
        if conn is not None:
            conn.close()

@contextmanager
def get_dict_cursor(commit=False):
    """
    Context manager that yields a dictionary database cursor.
    Automatically closes the cursor and connection when done.
    If commit=True, it commits the transaction before closing on success.
    """
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        yield cur
        if commit:
            conn.commit()
    finally:
        if 'cur' in locals() and cur is not None:
            cur.close()
        if conn is not None:
            conn.close()
