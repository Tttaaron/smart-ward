#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""边缘端交接班小 agent -- 生成每床自然语言交接班记录

数据来源：
  - 边缘 SQLite safety_events（YOLO 采集/融合产生的事件，含 occurred_at 时间）
  - observations（在床率/环境均值/活动分布）
  - 近7天事件趋势（班均对比，主动风险预警）
  - 上一次交接班的注意事项（闭环跟踪）
  - 本地 patients.json（病人信息档案）
生成：
  - 调用 LLMAdvisor.generate_shift_handover（mock/real 双模式）
  - 写入边缘 SQLite shift_handovers 表（含结构化 watch_points）
  - 导出 Markdown 文件（默认 edge-agent/data/handovers/）

用法:
  python scripts/gen_shift_handover.py --bed B02 --period day
  python scripts/gen_shift_handover.py --bed B02 --period day --date 2026-08-19
  LLM_MODE=real LLM_N_GPU_LAYERS=99 python scripts/gen_shift_handover.py --bed B01  # GGUF 真模型
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

# 使 edge-agent/src 可导入（与 tests 一致的导入方式）
EDGE_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "edge-agent", "src")
if EDGE_SRC not in sys.path:
    sys.path.insert(0, os.path.abspath(EDGE_SRC))

from database import LocalDatabase  # noqa: E402
from llm_advisor import LLMAdvisor, PERIOD_CN, compute_shift_window  # noqa: E402


def default_period(now: datetime = None) -> str:
    """按当前本地时刻推断班次"""
    now = now or datetime.now()
    h = now.hour
    if 8 <= h < 16:
        return "day"
    if 16 <= h < 24:
        return "evening"
    return "night"


def load_patients(path: str) -> dict:
    if not path or not os.path.exists(path):
        print(f"[shift-agent] 病人档案不存在: {path}，使用空档案", file=sys.stderr)
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_trend(db: LocalDatabase, end_utc: str, days: int = 7) -> dict:
    """近 N 天事件计数（按类型）-> 趋势数据（班均 = 计数 / (天数*3班)）"""
    end_dt = datetime.fromisoformat(end_utc.replace("Z", ""))
    start = (end_dt - timedelta(days=days)).isoformat() + "Z"
    counts: dict = {}
    for e in db.get_events_between(start, end_utc):
        t = e.get("event_type", "")
        counts[t] = counts.get(t, 0) + 1
    return {"counts": counts, "shifts": days * 3}


def main():
    parser = argparse.ArgumentParser(description="边缘端交接班小 agent：生成每床自然交接班记录")
    parser.add_argument("--db", default="edge-agent/src/data/edge_EDGE-W01-B01.db",
                        help="边缘 SQLite 路径（默认 edge-agent/src/data/edge_EDGE-W01-B01.db）")
    parser.add_argument("--patients", default="edge-agent/config/patients.json",
                        help="病人信息档案（默认 edge-agent/config/patients.json）")
    parser.add_argument("--bed", default="B01", help="床位 ID（默认 B01）")
    parser.add_argument("--node", default="", help="节点 ID（默认按 bed 推断 EDGE-W01-{bed}）")
    parser.add_argument("--ward", default="W-01", help="病区 ID（默认 W-01）")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"),
                        help="交接班日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--period", choices=["day", "evening", "night"], default=None,
                        help="班次（默认按当前时刻推断）")
    parser.add_argument("--out", default="edge-agent/data/handovers",
                        help="Markdown 输出目录（默认 edge-agent/data/handovers）")
    args = parser.parse_args()

    period = args.period or default_period()
    node_id = args.node or f"EDGE-{args.ward}-{args.bed}"

    # 1. 病人信息
    patients = load_patients(args.patients)
    patient = patients.get(args.bed, {})
    if patient:
        print(f"[shift-agent] 加载病人档案: {args.bed} -> {patient.get('name', '?')}")
    else:
        print(f"[shift-agent] 警告: {args.bed} 无病人档案，使用空档案")

    # 2. 班次窗口 + 事件 + 增强数据面
    start_utc, end_utc = compute_shift_window(args.date, period)
    print(f"[shift-agent] 班次: {args.date} {PERIOD_CN.get(period, period)} "
          f"(UTC {start_utc} ~ {end_utc})")

    db = LocalDatabase(args.db)
    events = db.get_events_between(start_utc, end_utc)
    print(f"[shift-agent] 查询到事件 {len(events)} 条")

    bed_stats = db.get_bed_stats_between(start_utc, end_utc)
    env_stats = db.get_env_stats_between(start_utc, end_utc)
    activities = db.get_activity_between(start_utc, end_utc)
    activity_stats = LLMAdvisor.aggregate_activities(activities)
    trend = build_trend(db, end_utc)
    previous = db.get_last_handover(args.bed, before_generated_at=start_utc)
    if previous:
        print(f"[shift-agent] 上次交接: {previous['shift_date']} "
              f"{PERIOD_CN.get(previous['shift_period'], previous['shift_period'])}，"
              f"{len(previous.get('watch_points', []))} 项注意事项待跟踪")

    # 3. LLM 生成交接班记录
    advisor = LLMAdvisor(node_id, args.bed, args.ward)
    handover = advisor.generate_shift_handover(
        patient, events, args.date, period,
        window_start=start_utc, window_end=end_utc,
        env_stats=env_stats, bed_stats=bed_stats, activity_stats=activity_stats,
        trend=trend, previous_handover=previous,
    )
    print(f"[shift-agent] 生成完成 (mode={handover.mode}, p1={handover.p1_count}, "
          f"total={handover.event_count})")
    if handover.llm_response:
        print(f"[shift-agent] LLM 指标: ttft={handover.llm_response.ttft_ms:.1f}ms "
              f"tokens={handover.llm_response.tokens_generated}")

    # 4. 写入 SQLite（含结构化 watch_points，供下个班闭环跟踪）
    db.save_shift_handover({
        "node_id": node_id, "bed_id": args.bed,
        "shift_date": args.date, "shift_period": period,
        "window_start": start_utc, "window_end": end_utc,
        "event_count": handover.event_count, "p1_count": handover.p1_count,
        "patient": patient, "handover_text": handover.handover_text,
        "mode": handover.mode,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "watch_points": handover.watch_points,
    })
    print(f"[shift-agent] 已写入 SQLite shift_handovers 表（含 {len(handover.watch_points)} 项 watch_points）")

    # 5. 导出 Markdown
    os.makedirs(args.out, exist_ok=True)
    md_path = os.path.join(args.out, f"{args.bed}-{args.date}-{period}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(handover.handover_text + "\n")
    print(f"[shift-agent] 已导出: {md_path}")

    # 6. 打印
    print("\n" + "=" * 60)
    print(handover.handover_text)
    print("=" * 60)


if __name__ == "__main__":
    main()
