"""交接班摘要的查询、生成与删除。"""

import asyncio
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from ..database import (
    get_db,
    Ward, Bed, EdgeNode, Observation, SafetyEvent, AlertTask,
    EventDisposition, ModelVersion, ModelDeployment, AuditLog, ShiftSummary,
)
from ..deps import ws_manager, mqtt_handler
from ..schemas import (
    AckRequest, ModelDeployRequest, EnvControlRequest,
    ShiftSummaryRequest, InjectionRequest,
)
from ..logger import get_logger
from ..timeutil import utc_now, utc_now_iso

logger = get_logger(__name__)

router = APIRouter()


# ===================== 交接班摘要 =====================

@router.get("/api/shift-summaries")
def list_shift_summaries(
    ward_id: str = Query(None),
    shift_date: str = Query(None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """查询交接班摘要列表"""
    q = db.query(ShiftSummary)
    if ward_id:
        q = q.filter(ShiftSummary.ward_id == ward_id)
    if shift_date:
        try:
            d = datetime.fromisoformat(shift_date)
            q = q.filter(ShiftSummary.shift_date >= d)
        except ValueError:
            pass
    records = q.order_by(desc(ShiftSummary.created_at)).limit(limit).all()
    data = [{
        "id": r.id,
        "ward_id": r.ward_id,
        "shift_date": r.shift_date.strftime("%Y-%m-%d") if r.shift_date else None,
        "shift_period": r.shift_period,
        "operator_id": r.operator_id,
        "summary_text": r.summary_text,
        "event_count": r.event_count,
        "p1_count": r.p1_count,
        "p2_count": r.p2_count,
        "resolved_count": r.resolved_count,
        "false_positive_count": r.false_positive_count,
        "avg_response_seconds": r.avg_response_seconds,
    } for r in records]
    return {"code": 0, "message": "success", "data": data, "total": len(data)}


@router.post("/api/shift-summaries/generate")
def generate_shift_summary(body: ShiftSummaryRequest, db: Session = Depends(get_db)):
    """生成交接班摘要（按日期+班次聚合事件）"""
    try:
        d = datetime.fromisoformat(body.shift_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="shift_date 格式无效，应为 YYYY-MM-DD")

    # 班次时段（本地时间，东八区）：day 08-16 / evening 16-24 / night 00-08
    period_hours = {"day": (8, 16), "evening": (16, 24), "night": (0, 8)}
    start_h, end_h = period_hours.get(body.shift_period, (0, 24))
    local_start = d.replace(hour=start_h, minute=0, second=0, microsecond=0)
    if end_h == 24:
        local_end = (d.replace(hour=0, minute=0, second=0) + timedelta(days=1))
    else:
        local_end = d.replace(hour=end_h, minute=0, second=0, microsecond=0)

    # 本地时间（+08:00）转 naive UTC 查询（事件 occurred_at 存的是 naive UTC）
    local_tz = timezone(timedelta(hours=8))
    start_time = local_start.replace(tzinfo=local_tz).astimezone(timezone.utc).replace(tzinfo=None)
    end_time = local_end.replace(tzinfo=local_tz).astimezone(timezone.utc).replace(tzinfo=None)

    # 查询该时段事件
    events = db.query(SafetyEvent).filter(
        SafetyEvent.ward_id == body.ward_id,
        SafetyEvent.occurred_at >= start_time,
        SafetyEvent.occurred_at < end_time,
    ).all()

    event_count = len(events)
    p1_count = sum(1 for e in events if e.priority == "P1")
    p2_count = sum(1 for e in events if e.priority == "P2")
    resolved_count = sum(1 for e in events if e.state == "resolved")
    false_positive_count = sum(1 for e in events if e.state == "false_positive")

    # 平均响应时长（occurred_at -> acknowledged_at）
    response_times = []
    for e in events:
        if e.acknowledged_at and e.occurred_at:
            response_times.append(int((e.acknowledged_at - e.occurred_at).total_seconds()))
    avg_response = int(sum(response_times) / len(response_times)) if response_times else 0

    # 事件类型分布（中文映射）
    EVENT_CN = {
        "fall_suspected": "疑似跌倒", "nurse_call": "护士呼叫", "bed_leave": "离床",
        "door_departure": "门区异常", "night_wandering": "夜间徘徊", "environment_anomaly": "环境异常",
        "node_offline": "节点失联", "fall_prediction": "坠床预警", "long_still": "长时间静止",
        "abnormal_posture": "异常体态", "seizure": "抽搐检测", "bedsore_risk": "压疮预防",
        "device_fault": "设备故障",
    }
    type_dist = {}
    for e in events:
        type_dist[e.event_type] = type_dist.get(e.event_type, 0) + 1
    type_summary = "；".join(f"{EVENT_CN.get(k, k)}={v}次" for k, v in sorted(type_dist.items(), key=lambda x: -x[1]))

    period_cn = {"day": "白班", "evening": "晚班", "night": "夜班"}.get(body.shift_period, body.shift_period)
    summary_text = (
        f"{body.shift_date} {period_cn}交接班摘要："
        f"共发生 {event_count} 起事件（P1 {p1_count} 起，P2 {p2_count} 起），"
        f"已处置 {resolved_count} 起，误报 {false_positive_count} 起。"
        f"平均响应时长 {avg_response} 秒。"
        f"事件分布：{type_summary or '无'}。"
    )

    # 幂等：同 ward+date+period 覆盖
    existing = db.query(ShiftSummary).filter_by(
        ward_id=body.ward_id, shift_date=d, shift_period=body.shift_period
    ).first()
    if existing:
        existing.operator_id = body.operator_id
        existing.summary_text = summary_text
        existing.event_count = event_count
        existing.p1_count = p1_count
        existing.p2_count = p2_count
        existing.resolved_count = resolved_count
        existing.false_positive_count = false_positive_count
        existing.avg_response_seconds = avg_response
        summary = existing
    else:
        summary = ShiftSummary(
            ward_id=body.ward_id,
            shift_date=d,
            shift_period=body.shift_period,
            operator_id=body.operator_id,
            summary_text=summary_text,
            event_count=event_count,
            p1_count=p1_count,
            p2_count=p2_count,
            resolved_count=resolved_count,
            false_positive_count=false_positive_count,
            avg_response_seconds=avg_response,
        )
        db.add(summary)

    audit = AuditLog(
        action="shift_summary_generate",
        target_type="shift_summary",
        target_id=str(summary.id),
        operator_id=body.operator_id,
        detail=json.dumps({"ward_id": body.ward_id, "date": body.shift_date, "period": body.shift_period}, ensure_ascii=False),
        occurred_at=utc_now(),
    )
    db.add(audit)
    db.commit()

    # WS 广播
    if ws_manager:
        ws_manager.broadcast_sync({
            "type": "shift_summary",
            "ward_id": body.ward_id,
            "shift_date": body.shift_date,
            "shift_period": body.shift_period,
            "summary_text": summary_text,
            "event_count": event_count,
        })

    return {
        "code": 0, "message": "success",
        "data": {
            "summary_text": summary_text,
            "event_count": event_count,
            "p1_count": p1_count,
            "p2_count": p2_count,
            "resolved_count": resolved_count,
            "false_positive_count": false_positive_count,
            "avg_response_seconds": avg_response,
        }
    }


@router.delete("/api/shift-summaries/{summary_id}")
def delete_shift_summary(summary_id: int, db: Session = Depends(get_db)):
    """删除指定交接班摘要"""
    summary = db.query(ShiftSummary).filter(ShiftSummary.id == summary_id).first()
    if not summary:
        raise HTTPException(status_code=404, detail="摘要不存在")
    db.delete(summary)
    db.commit()
    logger.info(f"删除交接班摘要: id={summary_id}")
    return {"code": 0, "message": "success", "data": None}
