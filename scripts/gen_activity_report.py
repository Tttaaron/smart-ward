#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""边缘端活动汇报小 agent -- 模式B：时段活动摘要

读取边缘 SQLite 中 camera 观测的 activity 记录（模式A 实时播报已逐条入库），
聚合活动分布/切换次数，由边缘 LLM 生成时段摘要（mock/real 双模式）。

用法:
  python scripts/gen_activity_report.py --bed B02 --period evening
  python scripts/gen_activity_report.py --bed B02 --period evening --date 2026-08-19
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

EDGE_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "edge-agent", "src")
if EDGE_SRC not in sys.path:
    sys.path.insert(0, os.path.abspath(EDGE_SRC))

from database import LocalDatabase  # noqa: E402
from llm_advisor import LLMAdvisor, PERIOD_CN, compute_shift_window  # noqa: E402


def default_period(now: datetime = None) -> str:
    now = now or datetime.now()
    h = now.hour
    if 8 <= h < 16:
        return "day"
    if 16 <= h < 24:
        return "evening"
    return "night"


def load_patients(path: str) -> dict:
    if not path or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="边缘端活动汇报（模式B：时段摘要）")
    parser.add_argument("--db", default="edge-agent/src/data/edge_EDGE-W01-B01.db")
    parser.add_argument("--patients", default="edge-agent/config/patients.json")
    parser.add_argument("--bed", default="B01")
    parser.add_argument("--node", default="")
    parser.add_argument("--ward", default="W-01")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--period", choices=["day", "evening", "night"], default=None)
    parser.add_argument("--out", default="edge-agent/data/handovers",
                        help="Markdown 输出目录")
    args = parser.parse_args()

    period = args.period or default_period()
    node_id = args.node or f"EDGE-{args.ward}-{args.bed}"
    patients = load_patients(args.patients)
    patient = patients.get(args.bed, {})

    start_utc, end_utc = compute_shift_window(args.date, period)
    shift_label = f"{args.date} {PERIOD_CN.get(period, period)}"
    print(f"[activity-agent] 时段: {shift_label} (UTC {start_utc} ~ {end_utc})")

    db = LocalDatabase(args.db)
    activities = db.get_activity_between(start_utc, end_utc)
    print(f"[activity-agent] 查询到活动记录 {len(activities)} 条")

    advisor = LLMAdvisor(node_id, args.bed, args.ward)
    broadcast = advisor.activity_period_summary(
        patient, activities, shift_label,
        window_start=start_utc, window_end=end_utc)

    db.save_activity_broadcast({
        "node_id": node_id, "bed_id": args.bed,
        "mode": broadcast.mode, "text": broadcast.text,
        "activity": broadcast.activity,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    })
    print(f"[activity-agent] 已写入 SQLite activity_broadcasts 表")

    os.makedirs(args.out, exist_ok=True)
    md_path = os.path.join(args.out, f"activity-{args.bed}-{args.date}-{period}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(broadcast.text + "\n")
    print(f"[activity-agent] 已导出: {md_path}")

    print("\n" + "=" * 60)
    print(broadcast.text)
    print("=" * 60)


if __name__ == "__main__":
    main()
