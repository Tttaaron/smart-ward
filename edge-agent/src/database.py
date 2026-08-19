"""边缘端本地数据库（SQLite）

缓存观测数据、安全事件和节点健康，支持断网补传。
所有表含 synced 字段，网络恢复后按序号补传。

对齐方案书 §4.1：edge-node 改造方向为"病房采集适配器、事件融合引擎、
本地模型推理和离线事件队列"。
"""

import sqlite3
import os
from datetime import datetime, timezone


class LocalDatabase:
    """边缘端本地 SQLite 数据库

    三张表：
    - observations：多源观测数据（带 source_type）
    - safety_events：融合引擎产出的安全事件
    - node_health：节点健康心跳记录
    """

    def __init__(self, db_path: str = "data/edge.db"):
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self.db_path = db_path
        self.init_tables()

    def get_conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def init_tables(self) -> None:
        conn = self.get_conn()
        cursor = conn.cursor()

        self._ensure_observations_table(cursor)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS safety_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id VARCHAR(64) NOT NULL UNIQUE,
                ward_id VARCHAR(10) NOT NULL,
                node_id VARCHAR(30) NOT NULL,
                bed_id VARCHAR(10) NOT NULL,
                event_type VARCHAR(30) NOT NULL,
                priority VARCHAR(5) NOT NULL,
                state VARCHAR(20) NOT NULL DEFAULT 'new',
                confidence FLOAT NOT NULL,
                payload TEXT NOT NULL,
                occurred_at DATETIME NOT NULL,
                synced BOOLEAN DEFAULT 0
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_evt_node_time ON safety_events(node_id, occurred_at)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS node_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id VARCHAR(30) NOT NULL,
                status VARCHAR(10) NOT NULL,
                metrics TEXT,
                timestamp DATETIME NOT NULL,
                synced BOOLEAN DEFAULT 0
            )
        """)

        conn.commit()
        conn.close()

    @staticmethod
    def _ensure_observations_table(cursor: sqlite3.Cursor) -> None:
        """Create the observation table/index when an old volume is missing it."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ward_id VARCHAR(10) NOT NULL,
                node_id VARCHAR(30) NOT NULL,
                bed_id VARCHAR(10) NOT NULL,
                source_type VARCHAR(20) NOT NULL,
                data TEXT NOT NULL,
                quality TEXT,
                timestamp DATETIME NOT NULL,
                synced BOOLEAN DEFAULT 0
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_obs_node_time "
            "ON observations(node_id, timestamp)"
        )

    def save_observation(self, obs_dict: dict, synced: bool = False) -> None:
        """保存一条观测数据"""
        import json
        conn = self.get_conn()
        cursor = conn.cursor()
        # Volumes can outlive an older image; repair this table before writing.
        self._ensure_observations_table(cursor)
        cursor.execute("""
            INSERT INTO observations
                (ward_id, node_id, bed_id, source_type, data, quality, timestamp, synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            obs_dict["ward_id"], obs_dict["node_id"], obs_dict["bed_id"],
            obs_dict["source_type"],
            json.dumps(obs_dict.get("data", {}), ensure_ascii=False),
            json.dumps(obs_dict.get("quality", {}), ensure_ascii=False),
            obs_dict["timestamp"], synced,
        ))
        conn.commit()
        conn.close()

    def save_event(self, event_dict: dict, synced: bool = False) -> None:
        """保存一条安全事件"""
        import json
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO safety_events
                (event_id, ward_id, node_id, bed_id, event_type, priority,
                 state, confidence, payload, occurred_at, synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event_dict["event_id"], event_dict["ward_id"], event_dict["node_id"],
            event_dict["bed_id"], event_dict["event_type"], event_dict["priority"],
            event_dict.get("state", "new"), event_dict["confidence"],
            json.dumps(event_dict, ensure_ascii=False),
            event_dict["occurred_at"], synced,
        ))
        conn.commit()
        conn.close()

    def update_event(self, event_dict: dict, synced: bool = None) -> bool:
        """更新已有事件 payload/state，返回是否找到目标事件。"""
        import json
        conn = self.get_conn()
        cursor = conn.cursor()
        if synced is None:
            cursor.execute("""
                UPDATE safety_events
                SET state = ?, confidence = ?, payload = ?
                WHERE event_id = ?
            """, (
                event_dict.get("state", "new"), event_dict["confidence"],
                json.dumps(event_dict, ensure_ascii=False), event_dict["event_id"],
            ))
        else:
            cursor.execute("""
                UPDATE safety_events
                SET state = ?, confidence = ?, payload = ?, synced = ?
                WHERE event_id = ?
            """, (
                event_dict.get("state", "new"), event_dict["confidence"],
                json.dumps(event_dict, ensure_ascii=False), synced, event_dict["event_id"],
            ))
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return updated

    def save_health(self, health_dict: dict, synced: bool = False) -> None:
        """保存节点健康记录"""
        import json
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO node_health (node_id, status, metrics, timestamp, synced)
            VALUES (?, ?, ?, ?, ?)
        """, (
            health_dict["node_id"], health_dict["status"],
            json.dumps(health_dict.get("metrics", {}), ensure_ascii=False),
            health_dict["timestamp"], synced,
        ))
        conn.commit()
        conn.close()

    def get_unsynced_events(self, limit: int = 50) -> list:
        """获取未同步的安全事件（按时间序）"""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, payload FROM safety_events
            WHERE synced = 0 ORDER BY occurred_at LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def mark_events_synced(self, ids: list) -> None:
        if not ids:
            return
        conn = self.get_conn()
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(ids))
        cursor.execute(f"UPDATE safety_events SET synced = 1 WHERE id IN ({placeholders})", ids)
        conn.commit()
        conn.close()

    def get_buffered_event_count(self) -> int:
        """未同步事件数（用于 health 上报）"""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM safety_events WHERE synced = 0")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def cleanup_old_data(self, keep_count: int = 1000) -> None:
        """清理旧观测数据，仅保留最近 N 条"""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM observations WHERE id NOT IN (
                SELECT id FROM observations ORDER BY id DESC LIMIT ?
            )
        """, (keep_count,))
        conn.commit()
        conn.close()
