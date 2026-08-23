"""SQLite schema initialization and legacy-database migration tests."""

import os
import sqlite3
import sys
import tempfile
import unittest

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from database import LocalDatabase


class LocalDatabaseSchemaTest(unittest.TestCase):
    def test_existing_database_without_observations_is_migrated(self):
        """A reused edge volume gets the observations table on startup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "edge.db")
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE safety_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    node_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
            conn.close()

            db = LocalDatabase(db_path)
            conn = db.get_conn()
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            self.assertIn("observations", tables)
            self.assertIn("safety_events", tables)

            db.save_observation(
                {
                    "ward_id": "W-01",
                    "node_id": "EDGE-W01-B01",
                    "bed_id": "B01",
                    "source_type": "camera",
                    "data": {"presence": True},
                    "quality": {"score": 1.0},
                    "timestamp": "2026-08-19T00:00:00Z",
                }
            )
            row = conn.execute(
                "SELECT node_id, source_type FROM observations"
            ).fetchone()
            conn.close()
            self.assertEqual(row, ("EDGE-W01-B01", "camera"))


if __name__ == "__main__":
    unittest.main()
