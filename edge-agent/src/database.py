"""边缘端本地数据库（SQLite）

缓存观测数据、安全事件和节点健康，支持断网补传。
所有表含 synced 字段，网络恢复后按序号补传。

对齐方案书 §4.1：edge-node 改造方向为"病房采集适配器、事件融合引擎、
本地模型推理和离线事件队列"。

写入路径性能
------------
此前每次写入都新建连接、执行 CREATE TABLE IF NOT EXISTS、然后单独 commit。
实测单条 save_observation 约 9.6ms，其中 connect 仅 0.17ms、INSERT 仅 0.05ms，
其余全是 commit 触发的 fsync；三个适配器每 tick 合计约 22ms，
在 TICK_SECONDS=0.2 的 YOLO 实时模式下占掉 11% 的周期预算。

现改为：复用持久连接 + WAL 日志 + synchronous=NORMAL，并提供
save_observations() 把一个周期的多源观测合并进单个事务。
实测三源写入 22.07ms -> 0.11ms。

WAL + synchronous=NORMAL 的取舍：断电时可能丢失最近若干个事务。
观测数据本就是 cleanup_old_data 只保留最近 1000 条的滚动数据，可接受；
安全事件另有 MQTT QoS1 与云端幂等入库兜底。

线程安全
--------
持久连接以 check_same_thread=False 创建，所有写入经 self._lock 串行化。
调用方来自三个线程：主循环、MQTT 回调线程（handle_inference_response）、
云端超时守护线程（_expire_cloud_inferences）。
get_conn() 仍返回**新连接**，供测试与只读查询独立使用（WAL 允许并发读）。
"""

import sqlite3
import os
import threading
from datetime import datetime, timezone


class LocalDatabase:
    """边缘端本地 SQLite 数据库

    四张表：
    - observations：多源观测数据（带 source_type）
    - safety_events：融合引擎产出的安全事件
    - node_health：节点健康心跳记录
    - shift_handovers：边缘 LLM 生成的交接班记录
    """

    def __init__(self, db_path: str = "data/edge.db"):
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self.db_path = db_path
        self._lock = threading.RLock()
        self._conn = self._connect(shared=True)
        self.init_tables()

    # ─── 连接管理 ───

    def _connect(self, shared: bool = False) -> sqlite3.Connection:
        """建立连接并应用 WAL/同步级别设置。

        WAL 是数据库文件的持久属性，设置一次即对后续所有连接生效；
        synchronous 是每连接设置，故每次新建连接都要重设。
        """
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=not shared,
            timeout=10.0,
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def get_conn(self) -> sqlite3.Connection:
        """返回一个新连接（调用方负责 close）。

        保持"每次新建"语义：测试与只读查询会自行 close，
        不能把内部持久连接交出去。
        """
        return self._connect()

    def close(self) -> None:
        """关闭持久连接。

        持久连接会一直占着数据库文件，Windows 上未关闭会导致临时目录删不掉。
        EdgeAgent._cleanup() 会调用；测试请用 addCleanup(db.close)。
        """
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.commit()
                    self._conn.close()
                finally:
                    self._conn = None

    def __enter__(self) -> "LocalDatabase":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def __del__(self) -> None:
        # 兜底，不能替代显式 close()：解释器退出时 GC 顺序不保证。
        try:
            self.close()
        except Exception:
            pass

    def init_tables(self) -> None:
        with self._lock:
            cursor = self._conn.cursor()

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
            # 补传每 tick 都要查未同步事件，按 synced 建索引避免全表扫描。
            # 复用的旧 volume 可能是缺 synced 列的早期 schema（CREATE TABLE
            # IF NOT EXISTS 不会补列），此时跳过建索引而不是让启动失败。
            if self._has_column(cursor, "safety_events", "synced"):
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_evt_synced "
                    "ON safety_events(synced, occurred_at)")

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

            self._conn.commit()

    @staticmethod
    def _has_column(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
        cursor.execute(f"PRAGMA table_info({table})")
        return any(row[1] == column for row in cursor.fetchall())

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

    # ─── 写入 ───

    @staticmethod
    def _observation_row(obs_dict: dict, synced: bool) -> tuple:
        import json
        return (
            obs_dict["ward_id"], obs_dict["node_id"], obs_dict["bed_id"],
            obs_dict["source_type"],
            json.dumps(obs_dict.get("data", {}), ensure_ascii=False),
            json.dumps(obs_dict.get("quality", {}), ensure_ascii=False),
            obs_dict["timestamp"], synced,
        )

    _OBS_INSERT = """
        INSERT INTO observations
            (ward_id, node_id, bed_id, source_type, data, quality, timestamp, synced)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    def save_observation(self, obs_dict: dict, synced: bool = False) -> None:
        """保存一条观测数据"""
        self.save_observations([obs_dict], synced=synced)

    def save_observations(self, obs_dicts: list, synced: bool = False) -> None:
        """把一个周期内的多源观测合并写入单个事务。

        主循环每 tick 采集 camera/bed_sensor/environment 三源；
        合并提交后 fsync 从 3 次降为 1 次。
        """
        if not obs_dicts:
            return
        rows = [self._observation_row(obs, synced) for obs in obs_dicts]
        with self._lock:
            cursor = self._conn.cursor()
            # 旧 volume 可能比镜像更久，缺表时补建后再写
            self._ensure_observations_table(cursor)
            cursor.executemany(self._OBS_INSERT, rows)
            self._conn.commit()

    def save_event(self, event_dict: dict, synced: bool = False) -> None:
        """保存一条安全事件"""
        import json
        with self._lock:
            self._conn.execute("""
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
            self._conn.commit()

    def update_event(self, event_dict: dict, synced: bool = None) -> bool:
        """更新已有事件 payload/state，返回是否找到目标事件。"""
        import json
        payload = json.dumps(event_dict, ensure_ascii=False)
        with self._lock:
            if synced is None:
                cursor = self._conn.execute("""
                    UPDATE safety_events
                    SET state = ?, confidence = ?, payload = ?
                    WHERE event_id = ?
                """, (
                    event_dict.get("state", "new"), event_dict["confidence"],
                    payload, event_dict["event_id"],
                ))
            else:
                cursor = self._conn.execute("""
                    UPDATE safety_events
                    SET state = ?, confidence = ?, payload = ?, synced = ?
                    WHERE event_id = ?
                """, (
                    event_dict.get("state", "new"), event_dict["confidence"],
                    payload, synced, event_dict["event_id"],
                ))
            updated = cursor.rowcount > 0
            self._conn.commit()
        return updated

    def save_health(self, health_dict: dict, synced: bool = False) -> None:
        """保存节点健康记录"""
        import json
        with self._lock:
            self._conn.execute("""
                INSERT INTO node_health (node_id, status, metrics, timestamp, synced)
                VALUES (?, ?, ?, ?, ?)
            """, (
                health_dict["node_id"], health_dict["status"],
                json.dumps(health_dict.get("metrics", {}), ensure_ascii=False),
                health_dict["timestamp"], synced,
            ))
            self._conn.commit()

    # ─── 查询 ───

    def get_unsynced_events(self, limit: int = 50) -> list:
        """获取未同步的安全事件（按时间序）"""
        with self._lock:
            cursor = self._conn.execute("""
                SELECT id, payload FROM safety_events
                WHERE synced = 0 ORDER BY occurred_at LIMIT ?
            """, (limit,))
            return cursor.fetchall()

    def mark_events_synced(self, ids: list) -> None:
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        with self._lock:
            self._conn.execute(
                f"UPDATE safety_events SET synced = 1 WHERE id IN ({placeholders})", ids)
            self._conn.commit()

    def get_buffered_event_count(self) -> int:
        """未同步事件数（用于 health 上报）"""
        with self._lock:
            cursor = self._conn.execute("SELECT COUNT(*) FROM safety_events WHERE synced = 0")
            return cursor.fetchone()[0]

    def cleanup_old_data(self, keep_count: int = 1000) -> None:
        """清理旧观测数据，仅保留最近 N 条"""
        with self._lock:
            self._conn.execute("""
                DELETE FROM observations WHERE id NOT IN (
                    SELECT id FROM observations ORDER BY id DESC LIMIT ?
                )
            """, (keep_count,))
            self._conn.commit()

    def get_events_between(self, start: str, end: str) -> list:
        """查询班次窗口内（occurred_at 介于 start/end，UTC ISO）的事件列表。

        返回含时间信息的 dict（含 payload 解析后的 details/rule_hits），
        供交接班 agent 生成自然语言记录使用。
        """
        import json
        with self._lock:
            cursor = self._conn.execute("""
                SELECT payload FROM safety_events
                WHERE occurred_at >= ? AND occurred_at < ?
                ORDER BY occurred_at
            """, (start, end))
            rows = cursor.fetchall()

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
        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO shift_handovers
                    (node_id, bed_id, shift_date, shift_period, window_start, window_end,
                     event_count, p1_count, patient, handover_text, mode, generated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record["node_id"], record["bed_id"], record["shift_date"], record["shift_period"],
                record.get("window_start"), record.get("window_end"),
                record.get("event_count", 0), record.get("p1_count", 0),
                json.dumps(record.get("patient", {}), ensure_ascii=False),
                record["handover_text"], record.get("mode", "mock"), record["generated_at"],
            ))
            self._conn.commit()

    def list_shift_handovers(self, bed_id: str = None, limit: int = 20) -> list:
        """列出交接班记录（最近 N 条）。"""
        sql = ("SELECT node_id, bed_id, shift_date, shift_period, event_count, p1_count, "
               "handover_text, mode, generated_at FROM shift_handovers")
        params: list = []
        if bed_id:
            sql += " WHERE bed_id = ?"
            params.append(bed_id)
        sql += " ORDER BY generated_at DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            cursor = self._conn.execute(sql, params)
            rows = cursor.fetchall()
        return [{
            "node_id": r[0], "bed_id": r[1], "shift_date": r[2], "shift_period": r[3],
            "event_count": r[4], "p1_count": r[5], "handover_text": r[6],
            "mode": r[7], "generated_at": r[8],
        } for r in rows]
