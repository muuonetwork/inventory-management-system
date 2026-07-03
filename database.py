"""
database.py
-----------
Small SQLite data-access layer for the Inventory Management System.

Kept intentionally dependency-free (just the standard library `sqlite3`
module) so the lab is easy to run anywhere with no extra services.
"""
import sqlite3
from datetime import datetime, timezone


def get_connection(db_path: str) -> sqlite3.Connection:
    """Open a connection to the given SQLite database file.

    `check_same_thread=False` lets us reuse one connection across the
    Flask dev server's request-handling thread(s) and the CLI.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create the items table if it doesn't already exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            barcode TEXT,
            category TEXT,
            quantity INTEGER NOT NULL DEFAULT 0,
            price REAL NOT NULL DEFAULT 0.0,
            description TEXT,
            image_url TEXT,
            source TEXT NOT NULL DEFAULT 'manual',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row) if row is not None else None


# ---------------------------------------------------------------- CREATE --
def create_item(conn: sqlite3.Connection, data: dict) -> dict:
    now = _now()
    cur = conn.execute(
        """
        INSERT INTO items (name, barcode, category, quantity, price,
                            description, image_url, source, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["name"],
            data.get("barcode"),
            data.get("category"),
            int(data.get("quantity", 0)),
            float(data.get("price", 0.0)),
            data.get("description"),
            data.get("image_url"),
            data.get("source", "manual"),
            now,
            now,
        ),
    )
    conn.commit()
    return get_item(conn, cur.lastrowid)


# ------------------------------------------------------------------ READ --
def get_all_items(conn: sqlite3.Connection) -> list:
    rows = conn.execute("SELECT * FROM items ORDER BY id").fetchall()
    return [row_to_dict(r) for r in rows]


def get_item(conn: sqlite3.Connection, item_id: int) -> dict:
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    return row_to_dict(row)


def search_items(conn: sqlite3.Connection, name: str = None, category: str = None) -> list:
    query = "SELECT * FROM items WHERE 1=1"
    params = []
    if name:
        query += " AND name LIKE ?"
        params.append(f"%{name}%")
    if category:
        query += " AND category LIKE ?"
        params.append(f"%{category}%")
    query += " ORDER BY id"
    rows = conn.execute(query, params).fetchall()
    return [row_to_dict(r) for r in rows]


# ---------------------------------------------------------------- UPDATE --
UPDATABLE_FIELDS = (
    "name", "barcode", "category", "quantity", "price",
    "description", "image_url", "source",
)


def update_item(conn: sqlite3.Connection, item_id: int, data: dict) -> dict:
    existing = get_item(conn, item_id)
    if existing is None:
        return None

    fields, values = [], []
    for key in UPDATABLE_FIELDS:
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])

    if not fields:
        return existing

    fields.append("updated_at = ?")
    values.append(_now())
    values.append(item_id)

    conn.execute(f"UPDATE items SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    return get_item(conn, item_id)


# ---------------------------------------------------------------- DELETE --
def delete_item(conn: sqlite3.Connection, item_id: int) -> bool:
    existing = get_item(conn, item_id)
    if existing is None:
        return False
    conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    return True
