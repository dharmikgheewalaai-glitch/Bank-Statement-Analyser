import sqlite3
from datetime import datetime
from pathlib import Path

DB = Path("bank_analyzer.db")

def init():
    with sqlite3.connect(DB) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT, processed_at TEXT, transactions INTEGER,
        method TEXT, confidence REAL, data TEXT)""")
        cols = [r[1] for r in c.execute("PRAGMA table_info(history)")]
        if "data" not in cols:
            c.execute("ALTER TABLE history ADD COLUMN data TEXT")

def add(filename, transactions, method, confidence, data_json=None):
    with sqlite3.connect(DB) as c:
        c.execute(
            "INSERT INTO history(filename,processed_at,transactions,method,confidence,data) VALUES(?,?,?,?,?,?)",
            (filename, datetime.now().isoformat(timespec="seconds"), transactions, method, confidence, data_json)
        )

def all_history():
    with sqlite3.connect(DB) as c:
        return c.execute(
            "SELECT id,filename,processed_at,transactions,method,confidence FROM history ORDER BY id DESC"
        ).fetchall()

def get_history_data(hid):
    with sqlite3.connect(DB) as c:
        row = c.execute("SELECT data FROM history WHERE id=?", (hid,)).fetchone()
        return row[0] if row else None

def delete_history(hid):
    with sqlite3.connect(DB) as c:
        c.execute("DELETE FROM history WHERE id=?", (hid,))
