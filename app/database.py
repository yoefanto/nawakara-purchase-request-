import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.environ.get("DATABASE_PATH", "purchase_requests.db")

def get_connection(db_path: str = None) -> sqlite3.Connection:
    target_path = db_path or DB_PATH
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@contextmanager
def transaction(conn: sqlite3.Connection):
    """Context manager for explicit atomic transaction handling."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise

def init_db(db_path: str = None):
    conn = get_connection(db_path)
    with transaction(conn):
        conn.execute("""
        CREATE TABLE IF NOT EXISTS purchase_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_number TEXT UNIQUE NOT NULL,
            requester_name TEXT NOT NULL,
            department TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED')),
            grand_total REAL NOT NULL DEFAULT 0.0,
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """)
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS line_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            unit_price REAL NOT NULL CHECK(unit_price >= 0),
            line_total REAL NOT NULL,
            FOREIGN KEY (request_id) REFERENCES purchase_requests(id) ON DELETE CASCADE
        );
        """)
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            from_status TEXT,
            to_status TEXT,
            note TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (request_id) REFERENCES purchase_requests(id) ON DELETE CASCADE
        );
        """)
        
        # Indexes for fast querying
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pr_status ON purchase_requests(status);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_items_pr_id ON line_items(request_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_pr_id ON audit_logs(request_id);")
    conn.close()
