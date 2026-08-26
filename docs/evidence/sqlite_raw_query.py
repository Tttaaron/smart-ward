"""SQLite 原始查询脚本（可复现）。

以 sqlite3 CLI 输出风格（.mode list, .headers on）打印原始查询结果：
  - .tables / .schema（CREATE TABLE 原文）
  - SELECT 原始行：字段用 | 分隔，payload 完整不截断、不解析

用法:
    python docs/evidence/sqlite_raw_query.py  >  docs/evidence/sqlite-query-vllm-raw.txt
"""
import sqlite3
import sys

DB = "edge-agent/data/edge_EDGE-W01-B02.db"

con = sqlite3.connect(DB)
cur = con.cursor()

TARGET_EVENTS = [
    "78012aed-11fa-431a-910c-975eaf1ac7de",  # CLOUD
    "7d3d4414-3b12-4063-9dac-7adee39f67c7",  # HYBRID
]


def q(sql):
    """执行一条 SELECT/SQL，按 CLI 风格打印表头与原始行。"""
    print(f"sqlite> {sql}")
    cur.execute(sql)
    if cur.description:
        print(" | ".join(d[0] for d in cur.description))
        for row in cur.fetchall():
            print(" | ".join("NULL" if v is None else str(v) for v in row))
    else:
        print(f"(rows affected: {cur.rowcount})")
    print()


print("==== sqlite3 CLI (Python sqlite3 stdlib, list mode) ====")
print(f"database: {DB}\n")

print("sqlite> .tables")
tables = [r[0] for r in cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
print(" | ".join(tables))
print()

for tbl in ("safety_events", "observations"):
    print(f"sqlite> .schema {tbl}")
    print(cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (tbl,)).fetchone()[0])
    print()

q("SELECT * FROM safety_events WHERE event_id IN ('78012aed-11fa-431a-910c-975eaf1ac7de','7d3d4414-3b12-4063-9dac-7adee39f67c7') ORDER BY occurred_at;")

q("SELECT event_id, event_type, priority, state, confidence, synced, occurred_at FROM safety_events WHERE event_id='78012aed-11fa-431a-910c-975eaf1ac7de';")

q("SELECT event_id, event_type, priority, state, confidence, synced, occurred_at FROM safety_events WHERE event_id='7d3d4414-3b12-4063-9dac-7adee39f67c7';")

q("SELECT COUNT(*) AS n FROM observations;")

q("SELECT COUNT(*) AS n FROM observations WHERE node_id='EDGE-W01-B02' AND bed_id='B02';")

q("SELECT COUNT(*) AS n FROM observations WHERE substr(timestamp,1,16) IN ('2026-08-23T15:32','2026-08-23T15:33');")

q("SELECT id, ward_id, node_id, bed_id, source_type, timestamp, synced, data, quality FROM observations WHERE substr(timestamp,1,16) IN ('2026-08-23T15:32','2026-08-23T15:33') ORDER BY timestamp;")

con.close()
