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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_obs_node_time ON observations(node_id, timestamp)")

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

        # 交接班记录（边缘 LLM 小 agent 生成，每床各自一份）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shift_handovers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id VARCHAR(30) NOT NULL,
                bed_id VARCHAR(10) NOT NULL,
                shift_date VARCHAR(10) NOT NULL,
                shift_period VARCHAR(10) NOT NULL,
                window_start DATETIME,
                window_end DATETIME,
                event_count INTEGER DEFAULT 0,
                p1_count INTEGER DEFAULT 0,
                patient TEXT,
                handover_text TEXT NOT NULL,
                mode VARCHAR(10) DEFAULT 'mock',
                generated_at DATETIME NOT NULL,
                UNIQUE(bed_id, shift_date, shift_period)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ho_bed_time ON shift_handovers(bed_id, shift_date)")

        # 活动播报记录（模式A 实时播报 / 模式B 时段摘要）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id VARCHAR(30) NOT NULL,
                bed_id VARCHAR(10) NOT NULL,
                mode VARCHAR(10) NOT NULL,
                text TEXT NOT NULL,
                activity TEXT,
                timestamp DATETIME NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ab_bed_time ON activity_broadcasts(bed_id, timestamp)")

        # 迁移：shift_handovers 增加 watch_points（旧库兼容）
        try:
            cursor.execute("ALTER TABLE shift_handovers ADD COLUMN watch_points TEXT")
        except sqlite3.OperationalError:
            pass  # 列已存在

        conn.commit()
        conn.close()

    def save_observation(self, obs_dict: dict, synced: bool = False) -> None:
        """保存一条观测数据"""
        import json
        conn = self.get_conn()
        cursor = conn.cursor()
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

    def get_events_between(self, start: str, end: str) -> list:
        """查询班次窗口内（occurred_at 介于 start/end，UTC ISO）的事件列表。

        返回含时间信息的 dict（含 payload 解析后的 details/rule_hits），
        供交接班 agent 生成自然语言记录使用。
        """
        import json
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT payload FROM safety_events
            WHERE occurred_at >= ? AND occurred_at < ?
            ORDER BY occurred_at
        """, (start, end))
        rows = cursor.fetchall()
        conn.close()

        events = []
        for (payload_json,) in rows:
            try:
                events.append(json.loads(payload_json))
            except (ValueError, TypeError):
                continue
        return events

    def save_shift_handover(self, record: dict) -> None:
        """保存一条交接班记录（同 bed+date+period 幂等覆盖）。"""
        import json
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO shift_handovers
                (node_id, bed_id, shift_date, shift_period, window_start, window_end,
                 event_count, p1_count, patient, handover_text, mode, generated_at, watch_points)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record["node_id"], record["bed_id"], record["shift_date"], record["shift_period"],
            record.get("window_start"), record.get("window_end"),
            record.get("event_count", 0), record.get("p1_count", 0),
            json.dumps(record.get("patient", {}), ensure_ascii=False),
            record["handover_text"], record.get("mode", "mock"), record["generated_at"],
            json.dumps(record.get("watch_points", []), ensure_ascii=False),
        ))
        conn.commit()
        conn.close()

    def list_shift_handovers(self, bed_id: str = None, limit: int = 20) -> list:
        """列出交接班记录（最近 N 条）。"""
        conn = self.get_conn()
        cursor = conn.cursor()
        sql = ("SELECT node_id, bed_id, shift_date, shift_period, event_count, p1_count, "
               "handover_text, mode, generated_at FROM shift_handovers")
        params: list = []
        if bed_id:
            sql += " WHERE bed_id = ?"
            params.append(bed_id)
        sql += " ORDER BY generated_at DESC LIMIT ?"
        params.append(limit)
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return [{
            "node_id": r[0], "bed_id": r[1], "shift_date": r[2], "shift_period": r[3],
            "event_count": r[4], "p1_count": r[5], "handover_text": r[6],
            "mode": r[7], "generated_at": r[8],
        } for r in rows]

    def get_last_handover(self, bed_id: str, before_generated_at: str) -> dict:
        """查询指定时刻之前最近一次交接班（含 watch_points），供交接闭环跟踪。"""
        import json
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT shift_date, shift_period, handover_text, watch_points, generated_at
            FROM shift_handovers
            WHERE bed_id = ? AND generated_at < ?
            ORDER BY generated_at DESC LIMIT 1
        """, (bed_id, before_generated_at))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return {}
        watch_points = []
        if row[3]:
            try:
                watch_points = json.loads(row[3])
            except (ValueError, TypeError):
                watch_points = []
        return {
            "shift_date": row[0], "shift_period": row[1], "handover_text": row[2],
            "watch_points": watch_points, "generated_at": row[4],
        }

    def get_activity_between(self, start: str, end: str) -> list:
        """查询窗口内 camera 观测的活动条目（含切换），供活动汇报/交接班。"""
        import json
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT data, timestamp FROM observations
            WHERE source_type = 'camera' AND timestamp >= ? AND timestamp < ?
            ORDER BY timestamp
        """, (start, end))
        rows = cursor.fetchall()
        conn.close()
        activities = []
        for data_json, ts in rows:
            try:
                data = json.loads(data_json)
            except (ValueError, TypeError):
                continue
            activity = data.get("activity")
            if isinstance(activity, dict) and activity:
                entry = dict(activity)
                entry["observed_at"] = ts
                activities.append(entry)
        return activities

    def get_bed_stats_between(self, start: str, end: str) -> dict:
        """床位占用统计：在床率（bed_sensor 观测聚合）。"""
        import json
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT data FROM observations
            WHERE source_type = 'bed_sensor' AND timestamp >= ? AND timestamp < ?
        """, (start, end))
        rows = cursor.fetchall()
        conn.close()
        total = occupied = 0
        for (data_json,) in rows:
            try:
                data = json.loads(data_json)
            except (ValueError, TypeError):
                continue
            total += 1
            if data.get("occupied"):
                occupied += 1
        return {"samples": total, "occupied_samples": occupied,
                "occupied_ratio": round(occupied / total, 3) if total else None}

    def get_env_stats_between(self, start: str, end: str) -> dict:
        """环境读数均值：温度/湿度/CO2/光照（environment 观测聚合）。"""
        import json
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT data FROM observations
            WHERE source_type = 'environment' AND timestamp >= ? AND timestamp < ?
        """, (start, end))
        rows = cursor.fetchall()
        conn.close()
        sums: dict = {}
        counts: dict = {}
        for (data_json,) in rows:
            try:
                data = json.loads(data_json)
            except (ValueError, TypeError):
                continue
            for key in ("temperature", "humidity", "co2", "light"):
                value = data.get(key)
                if isinstance(value, (int, float)):
                    sums[key] = sums.get(key, 0.0) + value
                    counts[key] = counts.get(key, 0) + 1
        return {key: round(sums[key] / counts[key], 1) for key in counts}

    def save_activity_broadcast(self, record: dict) -> None:
        """保存一条活动播报（模式A/B）。"""
        import json
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO activity_broadcasts
                (node_id, bed_id, mode, text, activity, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            record["node_id"], record["bed_id"], record.get("mode", "instant"),
            record["text"], json.dumps(record.get("activity", {}), ensure_ascii=False),
            record["timestamp"],
        ))
        conn.commit()
        conn.close()
