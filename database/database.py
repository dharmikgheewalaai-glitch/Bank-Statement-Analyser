import sqlite3
from datetime import datetime
from pathlib import Path

DB = Path("bank_analyzer.db")

def init():
    with sqlite3.connect(DB) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT, processed_at TEXT, transactions INTEGER,
        method TEXT, confidence REAL)""")

def add(filename, transactions, method, confidence):
    with sqlite3.connect(DB) as c:
        c.execute("INSERT INTO history(filename,processed_at,transactions,method,confidence) VALUES(?,?,?,?,?)",
                  (filename,datetime.now().isoformat(timespec="seconds"),transactions,method,confidence))

def all_history():
    with sqlite3.connect(DB) as c:
        return c.execute("SELECT filename,processed_at,transactions,method,confidence FROM history ORDER BY id DESC").fetchall()
