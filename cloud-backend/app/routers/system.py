"""边缘节点健康、模型版本管理、系统统计与环境控制。"""

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


# ===================== 节点健康 =====================


@router.get("/api/nodes")
def get_nodes(ward_id: str = Query(None), db: Session = Depends(get_db)):
    """获取边缘节点列表及健康状态"""
    q = db.query(EdgeNode)
    if ward_id:
        q = q.filter(EdgeNode.ward_id == ward_id)
    nodes = q.all()
    data = [{
        "id": n.id,
        "ward_id": n.ward_id,
        "bed_id": n.bed_id,
        "status": n.status,
        "model_version": n.model_version,
        "last_heartbeat": n.last_heartbeat.isoformat() + "Z" if n.last_heartbeat else None,
        "buffered_events": n.buffered_events,
    } for n in nodes]
    return {"code": 0, "message": "success", "data": data}


# ===================== 模型管理 =====================

@router.get("/api/models")
def list_models(db: Session = Depends(get_db)):
    """列出所有模型版本"""
    models = db.query(ModelVersion).order_by(desc(ModelVersion.created_at)).all()
    data = [{
        "id": m.id,
        "model_name": m.model_name,
        "model_version": m.model_version,
        "runtime": m.runtime,
        "target_device": m.target_device,
        "status": m.status,
        "created_at": m.created_at.isoformat() + "Z" if m.created_at else None,
    } for m in models]
    return {"code": 0, "message": "success", "data": data}


@router.post("/api/models/deploy")
def deploy_model(body: ModelDeployRequest, node_id: str = Query(...), db: Session = Depends(get_db)):
    """下发模型到指定节点"""
    deploy_payload = {
        "model_name": body.model_name,
        "model_version": body.model_version,
        "artifact_url": body.artifact_url,
        "checksum": body.checksum,
        "runtime": body.runtime,
        "target_device": body.target_device,
        "model_kind": body.model_kind,
        "occurred_at": utc_now_iso(),
    }
    mqtt_handler.publish_model_deploy(node_id, deploy_payload)

    # 记录部署
    deployment = ModelDeployment(
        model_name=body.model_name,
        model_version=body.model_version,
        node_id=node_id,
        action="deploy",
        status="pending",
    )
    db.add(deployment)
    db.commit()
    return {"code": 0, "message": "success", "data": {"node_id": node_id, "model": f"{body.model_name}@{body.model_version}"}}


# ===================== 系统统计 =====================

@router.get("/api/stats")
def get_system_stats(db: Session = Depends(get_db)):
    """获取系统全局统计"""
    total_wards = db.query(func.count(Ward.id)).scalar() or 0
    total_beds = db.query(func.count(Bed.id)).scalar() or 0
    online_nodes = db.query(func.count(EdgeNode.id)).filter(EdgeNode.status == "online").scalar() or 0
    total_nodes = db.query(func.count(EdgeNode.id)).scalar() or 0

    occupied_beds = db.query(func.count(Bed.id)).filter(Bed.status == "occupied").scalar() or 0
    leave_beds = db.query(func.count(SafetyEvent.id)).filter(
        SafetyEvent.event_type == "bed_leave",
        SafetyEvent.state.in_(["new", "notified", "acknowledged"]),
    ).scalar() or 0

    today = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
    events_today = db.query(func.count(SafetyEvent.id)).filter(SafetyEvent.occurred_at >= today).scalar() or 0
    pending_events = db.query(func.count(SafetyEvent.id)).filter(
        SafetyEvent.state.in_(["new", "notified", "acknowledged"])
    ).scalar() or 0
    p1_pending = db.query(func.count(SafetyEvent.id)).filter(
        SafetyEvent.priority == "P1",
        SafetyEvent.state.in_(["new", "notified", "acknowledged"]),
    ).scalar() or 0

    return {
        "code": 0, "message": "success",
        "data": {
            "total_wards": total_wards,
            "total_beds": total_beds,
            "occupied_beds": occupied_beds,
            "leave_beds": leave_beds,
            "online_nodes": online_nodes,
            "total_nodes": total_nodes,
            "events_today": events_today,
            "pending_events": pending_events,
            "p1_pending": p1_pending,
        }
    }


# ===================== 环境控制 =====================

@router.post("/api/env/control")
def trigger_env_control(body: EnvControlRequest, db: Session = Depends(get_db)):
    """手动触发环境控制（下发到边缘端 node/{node_id}/config/set）"""
    # 校验节点存在
    node = db.query(EdgeNode).filter_by(id=body.node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="边缘节点不存在")

    control_payload = {
        "node_id": body.node_id,
        "device": body.device,     # ac/light/fresh_air
        "action": body.action,     # on/off
        "reason": body.reason or "manual_trigger",
    }
    mqtt_handler.publish_env_control(body.node_id, control_payload)

    audit = AuditLog(
        action="env_control",
        target_type="edge_node",
        target_id=body.node_id,
        operator_id="cloud",
        detail=json.dumps(control_payload, ensure_ascii=False),
        occurred_at=utc_now(),
    )
    db.add(audit)
    db.commit()

    return {
        "code": 0, "message": "success",
        "data": {"node_id": body.node_id, "device": body.device, "action": body.action}
    }


