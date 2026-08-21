import mysql.connector
from contextlib import contextmanager

DB_CONFIG = {
    "host": "localhost",
    "database": "fceol",
    "user": "root",
    "password": "12345"
}

def get_connection():
    """Returns a new connection to the database."""
    return mysql.connector.connect(**DB_CONFIG)

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
