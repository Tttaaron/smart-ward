"""边缘 Agent 服务层：交接班生成与问答的共享实现

scripts/gen_shift_handover.py、scripts/ask_ward_agent.py 与主循环 MQTT 命令
（node/{node}/agent/request）共用同一套检索与生成逻辑，避免多入口实现漂移。

数据来源：
  - 本地 SQLite safety_events / observations / shift_handovers
  - config/patients.json 病人档案
生成：
  - LLMAdvisor.generate_shift_handover / answer_question（mock/real 双模式）
"""

import json
import os
from datetime import datetime, timedelta, timezone

from database import LocalDatabase
from llm_advisor import (LLMAdvisor, PERIOD_CN, EVENT_TYPE_CN,
                         compute_shift_window)

LOCAL_TZ = timezone(timedelta(hours=8))
PATIENTS_FILE_DEFAULT = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "config", "patients.json"))

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


def default_period(now: datetime = None) -> str:
    """按当前本地时刻推断班次"""
    now = now or datetime.now()
    if 8 <= now.hour < 16:
        return "day"
    if 16 <= now.hour < 24:
        return "evening"
    return "night"


def load_patients(path: str = None) -> dict:
    path = path or PATIENTS_FILE_DEFAULT
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def detect_time_range(question: str):
    """从问题识别时间范围 -> (start_utc_iso, end_utc_iso, label)；默认近24小时"""
    now_local = datetime.now()
    if "本班" in question or "这个班" in question:
        start, end = compute_shift_window(now_local.strftime("%Y-%m-%d"),
                                          default_period(now_local))
        label = f"本班（{PERIOD_CN[default_period(now_local)]}）"
        return start, end, label
    if "今天" in question or "今晚" in question:
        start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        return local_to_utc_iso(start), utc_now_iso(), "今天"
    if "昨天" in question or "昨晚" in question:
        y = now_local - timedelta(days=1)
        start = y.replace(hour=0, minute=0, second=0, microsecond=0)
        return local_to_utc_iso(start), local_to_utc_iso(start + timedelta(days=1)), "昨天"
    if any(k in question for k in ("近7天", "最近一周", "过去7天", "上周", "这周")):
        return local_to_utc_iso(now_local - timedelta(days=7)), utc_now_iso(), "近7天"
    for hours in (48, 36, 24, 12, 8, 6, 4, 2, 1):
        if f"近{hours}小时" in question or f"{hours}小时" in question:
            return (local_to_utc_iso(now_local - timedelta(hours=hours)),
                    utc_now_iso(), f"近{hours}小时")
    return local_to_utc_iso(now_local - timedelta(hours=24)), utc_now_iso(), "近24小时"


def detect_event_types(question: str):
    """识别问题涉及的事件类型；None 表示全部事件"""
    for keywords, types in EVENT_KEYWORDS:
        if any(k in question for k in keywords):
            return types
    return None


def detect_bed(question: str, patients: dict, default_bed: str) -> str:
    for bed_id, profile in patients.items():
        if bed_id in question or profile.get("name", "") in question:
            return bed_id
    for bed_id in ("B01", "B02", "B03"):
        if bed_id in question:
            return bed_id
    return default_bed


def fmt_local(iso: str) -> str:
    """UTC ISO -> 本地 MM-DD HH:MM 显示"""
    try:
        parsed = datetime.fromisoformat(str(iso).replace("Z", ""))
        parsed = parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
        return (parsed + timedelta(hours=8)).strftime("%m-%d %H:%M")
    except Exception:
        return str(iso)[:16]


class EdgeAgentService:
    """每床一个实例：封装交接班生成与问答（供脚本与 MQTT 命令复用）"""

    def __init__(self, node_id: str, bed_id: str, ward_id: str,
                 database: LocalDatabase = None, advisor: LLMAdvisor = None,
                 patient: dict = None):
        self.node_id = node_id
        self.bed_id = bed_id
        self.ward_id = ward_id
        self.db = database or LocalDatabase(f"data/edge_{node_id}.db")
        self.advisor = advisor or LLMAdvisor(node_id, bed_id, ward_id)
        self.patient = patient if patient is not None else \
            load_patients().get(bed_id, {})

    # ── 交接班生成 ──

    def generate_handover(self, shift_date: str = None,
                          shift_period: str = None) -> dict:
        """生成本床交接班记录：检索事件/统计/趋势/上次交接 -> LLM 生成 -> 入库"""
        shift_date = shift_date or datetime.now().strftime("%Y-%m-%d")
        shift_period = shift_period or default_period()
        start_utc, end_utc = compute_shift_window(shift_date, shift_period)

        events = self.db.get_events_between(start_utc, end_utc)
        bed_stats = self.db.get_bed_stats_between(start_utc, end_utc)
        env_stats = self.db.get_env_stats_between(start_utc, end_utc)
        activities = self.db.get_activity_between(start_utc, end_utc)
        activity_stats = LLMAdvisor.aggregate_activities(activities)

        end_dt = datetime.fromisoformat(end_utc.replace("Z", ""))
        trend_counts: dict = {}
        for e in self.db.get_events_between(
                (end_dt - timedelta(days=7)).isoformat() + "Z", end_utc):
            t = e.get("event_type", "")
            trend_counts[t] = trend_counts.get(t, 0) + 1
        trend = {"counts": trend_counts, "shifts": 7 * 3}

        previous = self.db.get_last_handover(self.bed_id, before_generated_at=start_utc)

        ho = self.advisor.generate_shift_handover(
            self.patient, events, shift_date, shift_period,
            window_start=start_utc, window_end=end_utc,
            env_stats=env_stats, bed_stats=bed_stats, activity_stats=activity_stats,
            trend=trend, previous_handover=previous,
        )

        generated_at = utc_now_iso()
        self.db.save_shift_handover({
            "node_id": self.node_id, "bed_id": self.bed_id,
            "shift_date": shift_date, "shift_period": shift_period,
            "window_start": start_utc, "window_end": end_utc,
            "event_count": ho.event_count, "p1_count": ho.p1_count,
            "patient": self.patient, "handover_text": ho.handover_text,
            "mode": ho.mode, "generated_at": generated_at,
            "watch_points": ho.watch_points,
        })

        return {
            "handover_text": ho.handover_text,
            "watch_points": ho.watch_points,
            "event_count": ho.event_count,
            "p1_count": ho.p1_count,
            "window_start": start_utc,
            "window_end": end_utc,
            "shift_date": shift_date,
            "shift_period": shift_period,
            "mode": ho.mode,
            "model_name": self.advisor.engine.MODEL_NAME,
            "model_version": self.advisor.engine.MODEL_VERSION,
            "generated_at": generated_at,
        }

    # ── 问答 ──

    def answer(self, question: str) -> dict:
        """回答护士自然语言问题：意图解析 -> SQLite 检索 -> LLM 作答"""
        start, end, range_label = detect_time_range(question)
        event_types = detect_event_types(question)

        events = self.db.get_events_between(start, end)
        if event_types:
            events = [e for e in events if e.get("event_type") in event_types]

        context_blocks = []
        wants_handover = any(k in question for k in ("交班", "交接"))
        wants_activity = any(k in question for k in ("活动", "姿势", "在做什么"))
        wants_bed = "在床" in question

        if wants_handover:
            handovers = self.db.list_shift_handovers(bed_id=self.bed_id, limit=1)
            if handovers:
                h = handovers[0]
                context_blocks.append(
                    f"最近一次交接班（{h['shift_date']} "
                    f"{PERIOD_CN.get(h['shift_period'], h['shift_period'])}）："
                    f"{h['handover_text'][:400]}")
            else:
                context_blocks.append("尚无交接班记录")

        if wants_activity:
            stats = LLMAdvisor.aggregate_activities(
                self.db.get_activity_between(start, end))
            context_blocks.append(
                f"{range_label}活动分布：{stats['dist_str']}，切换 {stats['switches']} 次")

        if wants_bed:
            bed_stats = self.db.get_bed_stats_between(start, end)
            if bed_stats.get("samples"):
                context_blocks.append(
                    f"{range_label}在床率 {bed_stats['occupied_ratio']:.0%}"
                    f"（采样 {bed_stats['samples']} 次）")

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

        answer = self.advisor.answer_question(question, context_blocks, self.patient)
        return {
            "answer": answer,
            "context_blocks": context_blocks,
            "time_range": range_label,
            "bed_id": self.bed_id,
            "mode": self.advisor.engine.mode,
            "model_name": self.advisor.engine.MODEL_NAME,
            "model_version": self.advisor.engine.MODEL_VERSION,
        }
