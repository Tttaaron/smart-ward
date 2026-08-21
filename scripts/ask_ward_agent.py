#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""边缘端问答小 agent -- 自然语言查询本床历史（工具路由 + LLM 回答）

混合式工具调用：规则路由识别问题中的床位/时间段/事件类型 -> 调用边缘 SQLite
查询工具（事件/交接班/活动/在床率）-> 边缘 LLM 依据检索到的事实作答
（mock 确定性拼接 / real GGUF 自然回答，不编造数据）。

用法:
  python scripts/ask_ward_agent.py --bed B02 --question "今晚离床了几次？"
  python scripts/ask_ward_agent.py --question "李伯伯昨天发生了什么？"
  python scripts/ask_ward_agent.py --question "上次交班要注意什么？"
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

EDGE_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "edge-agent", "src")
if EDGE_SRC not in sys.path:
    sys.path.insert(0, os.path.abspath(EDGE_SRC))

from database import LocalDatabase  # noqa: E402
from llm_advisor import (LLMAdvisor, EVENT_TYPE_CN, PERIOD_CN,  # noqa: E402
                         compute_shift_window)

LOCAL_TZ = timezone(timedelta(hours=8))

EVENT_KEYWORDS = [
    (("离床",), ("bed_leave",)),
    (("徘徊",), ("night_wandering",)),
    (("跌倒", "坠床"), ("fall_suspected", "fall_prediction")),
    (("抽搐",), ("seizure",)),
    (("呼叫",), ("nurse_call",)),
    (("压疮",), ("bedsore_risk",)),
    (("静止",), ("long_still",)),
    (("体态",), ("abnormal_posture",)),
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def local_to_utc_iso(dt: datetime) -> str:
    return dt.replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc).replace(
        tzinfo=None).isoformat() + "Z"


def detect_time_range(question: str):
    """从问题识别时间范围 -> (start_utc, end_utc, label)；默认近24小时"""
    now_local = datetime.now()
    q = question
    if "本班" in q or "这个班" in q:
        period = ("day" if 8 <= now_local.hour < 16
                  else "evening" if 16 <= now_local.hour < 24 else "night")
        start, end = compute_shift_window(now_local.strftime("%Y-%m-%d"), period)
        return start, end, f"本班（{PERIOD_CN[period]}）"
    if "今天" in q or "今晚" in q:
        start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        return local_to_utc_iso(start), utc_now_iso(), "今天"
    if "昨天" in q or "昨晚" in q:
        y = now_local - timedelta(days=1)
        start = y.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return local_to_utc_iso(start), local_to_utc_iso(end), "昨天"
    if "近7天" in q or "最近一周" in q or "过去7天" in q or "上周" in q or "这周" in q:
        return local_to_utc_iso(now_local - timedelta(days=7)), utc_now_iso(), "近7天"
    for hours in (48, 36, 24, 12, 8, 6, 4, 2, 1):
        tag = f"近{hours}小时"
        if tag in q or f"最近{hours}小时" in q or f"{hours}小时" in q:
            return local_to_utc_iso(now_local - timedelta(hours=hours)), utc_now_iso(), tag
    return local_to_utc_iso(now_local - timedelta(hours=24)), utc_now_iso(), "近24小时"


def detect_event_types(question: str):
    """识别问题涉及的事件类型；None 表示全部事件"""
    for keywords, types in EVENT_KEYWORDS:
        if any(k in question for k in keywords):
            return types
    if "事件" in question or "发生" in question or "什么" in question:
        return None
    return None


def detect_bed(question: str, patients: dict, default_bed: str) -> str:
    for bed_id in patients:
        if bed_id in question or patients[bed_id].get("name", "") in question:
            return bed_id
    for bed_id in ("B01", "B02", "B03"):
        if bed_id in question:
            return bed_id
    return default_bed


def fmt_local(iso: str) -> str:
    try:
        parsed = datetime.fromisoformat(str(iso).replace("Z", ""))
        return (parsed.replace(tzinfo=timezone.utc) + timedelta(hours=8)).strftime("%m-%d %H:%M")
    except Exception:
        return str(iso)[:16]


def main():
    parser = argparse.ArgumentParser(description="边缘端问答小 agent（自然语言查历史）")
    parser.add_argument("--question", "-q", required=True, help="护士问题")
    parser.add_argument("--db", default="edge-agent/src/data/edge_EDGE-W01-B01.db")
    parser.add_argument("--patients", default="edge-agent/config/patients.json")
    parser.add_argument("--bed", default="B02", help="默认床位（问题中提及则覆盖）")
    parser.add_argument("--ward", default="W-01")
    parser.add_argument("--node", default="")
    args = parser.parse_args()

    patients = {}
    if os.path.exists(args.patients):
        with open(args.patients, encoding="utf-8") as f:
            patients = json.load(f)

    bed = detect_bed(args.question, patients, args.bed)
    node_id = args.node or f"EDGE-{args.ward}-{bed}"
    patient = patients.get(bed, {})
    start, end, range_label = detect_time_range(args.question)
    event_types = detect_event_types(args.question)

    print(f"[ask-agent] 床位={bed} 患者={patient.get('name', '?')} "
          f"时间范围={range_label} 事件类型={event_types or '全部'}")

    db = LocalDatabase(args.db)
    events = db.get_events_between(start, end)
    if event_types:
        events = [e for e in events if e.get("event_type") in event_types]

    # ── 工具路由：按问题意图检索事实 ──
    context_blocks = []
    q = args.question
    wants_handover = any(k in q for k in ("交班", "交接", "上次交接"))
    wants_activity = any(k in q for k in ("活动", "姿势", "在做什么"))
    wants_bed = "在床" in q

    if wants_handover:
        handovers = db.list_shift_handovers(bed_id=bed, limit=1)
        if handovers:
            h = handovers[0]
            context_blocks.append(
                f"最近一次交接班（{h['shift_date']} {PERIOD_CN.get(h['shift_period'], h['shift_period'])}）：{h['handover_text'][:400]}")
        else:
            context_blocks.append("尚无交接班记录")

    if wants_activity:
        activities = db.get_activity_between(start, end)
        stats = LLMAdvisor.aggregate_activities(activities)
        context_blocks.append(f"{range_label}活动分布：{stats['dist_str']}，切换 {stats['switches']} 次")

    if wants_bed:
        bed_stats = db.get_bed_stats_between(start, end)
        if bed_stats.get("samples"):
            context_blocks.append(
                f"{range_label}在床率 {bed_stats['occupied_ratio']:.0%}"
                f"（采样 {bed_stats['samples']} 次）")

    # 事件事实（默认总是提供）
    if events:
        type_count: dict = {}
        for e in events:
            t = e.get("event_type", "")
            type_count[t] = type_count.get(t, 0) + 1
        dist = "、".join(f"{EVENT_TYPE_CN.get(t, t)} {c} 次"
                         for t, c in sorted(type_count.items(), key=lambda x: -x[1]))
        context_blocks.append(f"{range_label}共 {len(events)} 起事件：{dist}")
        recent = sorted(events, key=lambda e: e.get("occurred_at", ""))[-5:]
        for e in recent:
            context_blocks.append(
                f"{fmt_local(e.get('occurred_at', ''))} "
                f"{EVENT_TYPE_CN.get(e.get('event_type', ''), e.get('event_type', ''))} "
                f"({e.get('priority', 'P3')}，置信度{e.get('confidence', 0):.0%})")
    elif not wants_handover:
        context_blocks.append(f"{range_label}无相关事件记录")

    # ── 回答 ──
    advisor = LLMAdvisor(node_id, bed, args.ward)
    answer = advisor.answer_question(args.question, context_blocks, patient)

    print("\n" + "=" * 60)
    print(f"问：{args.question}")
    print(f"答：{answer}")
    print("=" * 60)


if __name__ == "__main__":
    main()
