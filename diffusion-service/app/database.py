"""SQLite 数据库管理

3 表：
  - generated_samples: 生成的困难样本元数据
  - false_positive_events: 接收到的误报事件
  - dataset_exports: 导出记录
"""

import os
import json
import sqlite3
import uuid
import threading
from datetime import datetime, timezone

from .logger import get_logger

logger = get_logger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class Database:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        with self._lock:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS generated_samples (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    sample_id       TEXT UNIQUE NOT NULL,
                    source_event_id TEXT,
                    ward_id         TEXT,
                    bed_id          TEXT,
                    event_type      TEXT NOT NULL,
                    file_path       TEXT,
                    file_format     TEXT DEFAULT 'npy',
                    file_size       INTEGER DEFAULT 0,
                    sample_metadata TEXT DEFAULT '{}',
                    created_at      TEXT NOT NULL,
                    exported        INTEGER DEFAULT 0,
                    exported_at     TEXT
                );

                CREATE TABLE IF NOT EXISTS false_positive_events (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id          TEXT UNIQUE NOT NULL,
                    ward_id           TEXT,
                    bed_id            TEXT,
                    event_type        TEXT,
                    priority          TEXT,
                    original_data     TEXT DEFAULT '{}',
                    occurred_at       TEXT,
                    false_positive_at TEXT NOT NULL,
                    is_processed      INTEGER DEFAULT 0,
                    processed_at      TEXT,
                    sample_count      INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS dataset_exports (
                    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                    export_id               TEXT UNIQUE NOT NULL,
                    sample_count            INTEGER NOT NULL,
                    export_path             TEXT,
                    file_size               INTEGER DEFAULT 0,
                    exported_to_coordinator INTEGER DEFAULT 0,
                    coordinator_job_id      TEXT,
                    created_at              TEXT NOT NULL
                );
            """)
            self._conn.commit()

    # ── 样本操作 ────────────────────────────────────────

    def save_sample(self, sample: dict) -> str:
        sample_id = sample.get("sample_id", str(uuid.uuid4()))
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO generated_samples
                   (sample_id, source_event_id, ward_id, bed_id, event_type,
                    file_path, file_format, file_size, sample_metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    sample_id,
                    sample.get("source_event_id"),
                    sample.get("ward_id"),
                    sample.get("bed_id"),
                    sample.get("event_type"),
                    sample.get("file_path"),
                    sample.get("file_format", "npy"),
                    sample.get("file_size", 0),
                    json.dumps(sample.get("sample_metadata", {})),
                    sample.get("created_at", _now_iso()),
                ),
            )
            self._conn.commit()
        return sample_id

    def get_sample(self, sample_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM generated_samples WHERE sample_id = ?", (sample_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_samples(
        self, event_type: str = None, ward_id: str = None, limit: int = 50, offset: int = 0
    ) -> tuple[list, int]:
        where = []
        params = []
        if event_type:
            where.append("event_type = ?")
            params.append(event_type)
        if ward_id:
            where.append("ward_id = ?")
            params.append(ward_id)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        count_row = self._conn.execute(
            f"SELECT COUNT(*) as cnt FROM generated_samples{clause}", params
        ).fetchone()
        total = count_row["cnt"]
        rows = self._conn.execute(
            f"SELECT * FROM generated_samples{clause} ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        return [dict(r) for r in rows], total

    def delete_sample(self, sample_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM generated_samples WHERE sample_id = ?", (sample_id,)
            )
            self._conn.commit()
            return cur.rowcount > 0

    # ── 误报事件 ────────────────────────────────────────

    def save_false_positive(self, event: dict) -> bool:
        event_id = event.get("event_id")
        if not event_id:
            return False
        with self._lock:
            existing = self._conn.execute(
                "SELECT id FROM false_positive_events WHERE event_id = ?", (event_id,)
            ).fetchone()
            if existing:
                return False
            self._conn.execute(
                """INSERT INTO false_positive_events
                   (event_id, ward_id, bed_id, event_type, priority,
                    original_data, occurred_at, false_positive_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event_id,
                    event.get("ward_id"),
                    event.get("bed_id"),
                    event.get("event_type"),
                    event.get("priority"),
                    json.dumps(event.get("original_data", {})),
                    event.get("occurred_at"),
                    event.get("false_positive_at", _now_iso()),
                ),
            )
            self._conn.commit()
        return True

    def get_false_positive(self, event_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM false_positive_events WHERE event_id = ?", (event_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_false_positives(self, limit: int = 50, offset: int = 0) -> tuple[list, int]:
        total = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM false_positive_events"
        ).fetchone()["cnt"]
        rows = self._conn.execute(
            "SELECT * FROM false_positive_events ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows], total

    def mark_processed(self, event_id: str, sample_count: int):
        with self._lock:
            self._conn.execute(
                """UPDATE false_positive_events
                   SET is_processed = 1, processed_at = ?, sample_count = ?
                   WHERE event_id = ?""",
                (_now_iso(), sample_count, event_id),
            )
            self._conn.commit()

    # ── 导出 ────────────────────────────────────────────

    def get_unexported_samples(self, limit: int = 100) -> list:
        rows = self._conn.execute(
            "SELECT * FROM generated_samples WHERE exported = 0 LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_samples_exported(self, sample_ids: list[str], export_id: str):
        if not sample_ids:
            return
        now = _now_iso()
        placeholders = ",".join("?" * len(sample_ids))
        with self._lock:
            self._conn.execute(
                f"UPDATE generated_samples SET exported = 1, exported_at = ? "
                f"WHERE sample_id IN ({placeholders})",
                [now] + sample_ids,
            )
            self._conn.commit()

    def create_export(self, export_id: str, sample_count: int, export_path: str, file_size: int = 0):
        with self._lock:
            self._conn.execute(
                """INSERT INTO dataset_exports
                   (export_id, sample_count, export_path, file_size, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (export_id, sample_count, export_path, file_size, _now_iso()),
            )
            self._conn.commit()

    def update_export_coordinator(self, export_id: str, job_id: str):
        with self._lock:
            self._conn.execute(
                "UPDATE dataset_exports SET exported_to_coordinator = 1, coordinator_job_id = ? WHERE export_id = ?",
                (job_id, export_id),
            )
            self._conn.commit()

    def list_exports(self, limit: int = 20, offset: int = 0) -> tuple[list, int]:
        total = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM dataset_exports"
        ).fetchone()["cnt"]
        rows = self._conn.execute(
            "SELECT * FROM dataset_exports ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows], total

    def get_export(self, export_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM dataset_exports WHERE export_id = ?", (export_id,)
        ).fetchone()
        return dict(row) if row else None

    # ── 统计 ────────────────────────────────────────────

    def get_stats(self) -> dict:
        total_samples = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM generated_samples"
        ).fetchone()["cnt"]
        unexported = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM generated_samples WHERE exported = 0"
        ).fetchone()["cnt"]
        total_fp = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM false_positive_events"
        ).fetchone()["cnt"]
        total_exports = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM dataset_exports"
        ).fetchone()["cnt"]
        by_type = self._conn.execute(
            "SELECT event_type, COUNT(*) as cnt FROM generated_samples GROUP BY event_type ORDER BY cnt DESC"
        ).fetchall()
        return {
            "total_samples": total_samples,
            "unexported_samples": unexported,
            "total_false_positives": total_fp,
            "total_exports": total_exports,
            "samples_by_type": {r["event_type"]: r["cnt"] for r in by_type},
        }
