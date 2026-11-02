"""SQLite storage implementation for macros."""

import json
import sqlite3
import time
from pathlib import Path


class MacroStorage:
    def __init__(self, path=None):
        """
        Initializes the SQLite database connection.
        If a directory path is provided (for legacy compatibility with tests),
        the database is created inside it.
        """
        if path is not None:
            path_obj = Path(path)
            if path_obj.is_dir():
                self.db_path = path_obj / "database.sqlite3"
            else:
                self.db_path = path_obj
        else:
            self.db_path = Path("database.sqlite3")
            
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS macros (
                    name TEXT PRIMARY KEY,
                    version INTEGER,
                    created_at REAL,
                    event_count INTEGER,
                    duration REAL,
                    events TEXT
                )
            ''')

    def save(self, filename, events, metadata=None):
        name = str(filename).replace(".json", "")
        
        # Legacy path traversal protection (preserves test requirements)
        if ".." in name or "/" in name or "\\" in name:
            raise ValueError("Nama file tidak valid.")

        events_list = [e.to_dict() if hasattr(e, 'to_dict') else e for e in events]
        event_count = len(events_list)
        
        if event_count > 0:
            duration = events_list[-1].get("timestamp", 0) - events_list[0].get("timestamp", 0)
        else:
            duration = 0.0

        version = 1
        created_at = (metadata or {}).get("created_at", time.time())
        events_json = json.dumps(events_list)

        with self._get_connection() as conn:
            conn.execute('''
                INSERT INTO macros (name, version, created_at, event_count, duration, events)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    version = excluded.version,
                    created_at = excluded.created_at,
                    event_count = excluded.event_count,
                    duration = excluded.duration,
                    events = excluded.events
            ''', (name, version, created_at, event_count, duration, events_json))
            
        return str(self.db_path)

    def load(self, filename):
        name = str(filename).replace(".json", "")
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM macros WHERE name = ?", (name,)).fetchone()
            
            if not row:
                raise FileNotFoundError(f"Macro '{name}' tidak ditemukan.")
                
            return {
                "name": row["name"],
                "version": row["version"],
                "created_at": row["created_at"],
                "event_count": row["event_count"],
                "duration": row["duration"],
                "events": json.loads(row["events"])
            }

    def delete(self, filename):
        name = str(filename).replace(".json", "")
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM macros WHERE name = ?", (name,))
            return cursor.rowcount > 0

    def get_all_macros(self):
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT name, version, created_at, event_count, duration 
                FROM macros 
                ORDER BY created_at DESC
            ''').fetchall()
            
            return [{
                "name": row["name"],
                "version": row["version"],
                "created_at": row["created_at"],
                "event_count": row["event_count"],
                "duration": row["duration"],
                "invalid": False
            } for row in rows]