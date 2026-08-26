"""安全事件查询/处置/注入，以及观测数据读写。

注意路由注册顺序：/api/events/by-type 必须在 /api/events/{event_id} 之前，
否则 by-type 会被当作 event_id 匹配。"""

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


# ===================== 安全事件 =====================

@router.get("/api/events")
def get_events(
    ward_id: str = Query(None),
    bed_id: str = Query(None),
    priority: str = Query(None),
    state: str = Query(None),
    event_type: str = Query(None),
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """查询安全事件（支持多条件过滤）"""
    q = db.query(SafetyEvent)
    if ward_id:
        q = q.filter(SafetyEvent.ward_id == ward_id)
    if bed_id:
        q = q.filter(SafetyEvent.bed_id == bed_id)
    if priority:
        q = q.filter(SafetyEvent.priority == priority)
    if state:
        q = q.filter(SafetyEvent.state == state)
    if event_type:
        q = q.filter(SafetyEvent.event_type == event_type)

    start = utc_now() - timedelta(hours=hours)
    q = q.filter(SafetyEvent.occurred_at >= start)
    q = q.order_by(desc(SafetyEvent.occurred_at)).limit(limit)

    records = q.all()
    data = []
    for r in records:
        data.append({
            "event_id": r.event_id,
            "ward_id": r.ward_id,
            "node_id": r.node_id,
            "bed_id": r.bed_id,
            "event_type": r.event_type,
            "priority": r.priority,
            "state": r.state,
            "confidence": r.confidence,
            "model_name": r.model_name,
            "model_version": r.model_version,
            "inference_ms": r.inference_ms,
            "evidence_refs": json.loads(r.evidence_refs) if r.evidence_refs else [],
            "rule_hits": json.loads(r.rule_hits) if r.rule_hits else [],
            "details": json.loads(r.details) if r.details else {},
            "occurred_at": r.occurred_at.isoformat() + "Z" if r.occurred_at else None,
            "acknowledged_at": r.acknowledged_at.isoformat() + "Z" if r.acknowledged_at else None,
            "resolved_at": r.resolved_at.isoformat() + "Z" if r.resolved_at else None,
        })
    return {"code": 0, "message": "success", "data": data, "total": len(data)}


@router.get("/api/events/by-type")
def get_events_by_type(hours: int = Query(24, ge=1, le=168), db: Session = Depends(get_db)):
    """按事件类型统计最近 N 小时内的事件数量"""
    start = utc_now() - timedelta(hours=hours)
    results = db.query(
        SafetyEvent.event_type,
        func.count(SafetyEvent.id).label("count")
    ).filter(
        SafetyEvent.occurred_at >= start
    ).group_by(
        SafetyEvent.event_type
    ).all()

    data = {r.event_type: r.count for r in results}
    return {"code": 0, "message": "success", "data": data}


@router.get("/api/events/{event_id}")
def get_event(event_id: str, db: Session = Depends(get_db)):
    """获取事件详情（含处置记录）"""
    event = db.query(SafetyEvent).filter_by(event_id=event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    dispositions = db.query(EventDisposition).filter_by(event_id=event_id).all()
    return {
        "code": 0, "message": "success",
        "data": {
            "event_id": event.event_id,
            "ward_id": event.ward_id,
            "bed_id": event.bed_id,
            "event_type": event.event_type,
            "priority": event.priority,
            "state": event.state,
            "confidence": event.confidence,
            "model": {"name": event.model_name, "version": event.model_version, "inference_ms": event.inference_ms},
            "evidence_refs": json.loads(event.evidence_refs) if event.evidence_refs else [],
            "rule_hits": json.loads(event.rule_hits) if event.rule_hits else [],
            "details": json.loads(event.details) if event.details else {},
            "occurred_at": event.occurred_at.isoformat() + "Z" if event.occurred_at else None,
            "dispositions": [{
                "action": d.action,
                "operator_id": d.operator_id,
                "operator_name": d.operator_name,
                "result": d.result,
                "note": d.note,
                "occurred_at": d.occurred_at.isoformat() + "Z" if d.occurred_at else None,
            } for d in dispositions],
        }
    }


@router.post("/api/events/{event_id}/ack")
def ack_event(event_id: str, body: AckRequest, db: Session = Depends(get_db)):
    """确认/处置/升级事件（通过 MQTT 下发到边缘端，同时更新本地状态）"""
    event = db.query(SafetyEvent).filter_by(event_id=event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")

    ack_payload = {
        "event_id": event_id,
        "ward_id": event.ward_id,
        "action": body.action,
        "operator": {
            "id": body.operator_id,
            "name": body.operator_name,
            "role": body.operator_role,
        },
        "result": body.result,
        "note": body.note,
        "occurred_at": utc_now_iso(),
    }
    # MQTT 下发到边缘端
    mqtt_handler.publish_ack(event.ward_id, event_id, ack_payload)
    # 本地直接处理，前端不必等待 MQTT 往返；
    # 回环到本进程的同一条 ack 会被 apply_ack 按信封 source 跳过，不会重复入库。
    mqtt_handler.apply_ack(ack_payload)
    return {"code": 0, "message": "success", "data": {"event_id": event_id, "action": body.action}}


@router.post("/api/events")
def inject_event(payload: dict, db: Session = Depends(get_db)):
    """手动注入安全事件，供演示或调试面板使用"""
    import uuid
    event_id = payload.get("event_id") or str(uuid.uuid4())
    ward_id = payload.get("ward_id") or "W-01"
    node_id = payload.get("node_id") or f"EDGE-{ward_id}-{payload.get('bed_id', 'B01')}"
    bed_id = payload.get("bed_id") or "B01"
    event_type = payload.get("event_type") or "nurse_call"
    
    priority_map = {
        "fall_suspected": "P1",
        "nurse_call": "P1",
        "fall_prediction": "P1",
        "seizure": "P1",
        "bed_leave": "P2",
        "door_departure": "P2",
        "night_wandering": "P2",
        "long_still": "P2",
        "abnormal_posture": "P2",
        "environment_anomaly": "P3",
        "node_offline": "P3",
        "bedsore_risk": "P3",
        "device_fault": "P3"
    }
    priority = payload.get("priority") or priority_map.get(event_type, "P3")
    now_str = utc_now_iso()
    
    business_payload = {
        "event_id": event_id,
        "ward_id": ward_id,
        "node_id": node_id,
        "bed_id": bed_id,
        "event_type": event_type,
        "priority": priority,
        "state": "new",
        "confidence": payload.get("confidence") or 0.9,
        "occurred_at": payload.get("occurred_at") or now_str,
        "detected_at": payload.get("detected_at") or now_str,
        "model": payload.get("model") or {
            "model_name": "rule-fusion-v1",
            "model_version": "0.1.0-mock",
            "inference_ms": 5
        },
        "evidence_refs": payload.get("evidence_refs") or [],
        "rule_hits": payload.get("rule_hits") or [],
        "details": payload.get("details") or {}
    }
    
    mqtt_handler._handle_event(business_payload)
    return {"code": 0, "message": "success", "data": {"event_id": event_id}}


@router.post("/api/observations")
def inject_observation(payload: dict, db: Session = Depends(get_db)):
    """手动注入观测数据（含活动状态），供活动日志面板演示或调试

    payload 形状与边缘端 MQTT 上报一致：
        {
            "ward_id": "W-01",
            "node_id": "EDGE-W01-B01",
            "bed_id": "B01",
            "timestamp": "2026-08-11T08:30:00Z",
            "sources": [{"source_type": "camera",
                         "data": {"activity": {"label": "sitting", ...}, ...},
                         "quality": {}}]
        }

    复用 mqtt_handler._handle_observation：写 observations 表 + WS 广播，
    使前端活动日志面板实时刷新（与真实边缘上报走同一条链路）。
    """
    import uuid
    ward_id = payload.get("ward_id") or "W-01"
    bed_id = payload.get("bed_id") or "B01"
    node_id = payload.get("node_id") or f"EDGE-{ward_id}-{bed_id}"
    now_str = utc_now_iso()

    business_payload = {
        "ward_id": ward_id,
        "node_id": node_id,
        "bed_id": bed_id,
        "timestamp": payload.get("timestamp") or now_str,
        "sources": payload.get("sources") or [],
    }

    mqtt_handler._handle_observation(business_payload)
    return {"code": 0, "message": "success", "data": {"bed_id": bed_id, "node_id": node_id}}


# ===================== 观测数据查询 =====================

@router.get("/api/observations")
def get_observations(
    bed_id: str = Query(None),
    source_type: str = Query(None),
    hours: int = Query(default=1, ge=1, le=168),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """查询观测历史数据"""
    q = db.query(Observation)
    if bed_id:
        q = q.filter(Observation.bed_id == bed_id)
    if source_type:
        q = q.filter(Observation.source_type == source_type)
    start = utc_now() - timedelta(hours=hours)
    q = q.filter(Observation.timestamp >= start)
    q = q.order_by(desc(Observation.timestamp)).limit(limit)
    records = q.all()
    data = [{
        "ward_id": r.ward_id,
        "node_id": r.node_id,
        "bed_id": r.bed_id,
        "source_type": r.source_type,
        "data": json.loads(r.data) if r.data else {},
        "quality": json.loads(r.quality) if r.quality else {},
        "timestamp": r.timestamp.isoformat() + "Z" if r.timestamp else None,
    } for r in records]
    return {"code": 0, "message": "success", "data": data, "total": len(data)}
