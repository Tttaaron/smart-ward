"""病区、床位与床位占用视图。"""

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


# ===================== 病区与床位 =====================

@router.get("/api/wards")
def get_wards(db: Session = Depends(get_db)):
    """获取所有病区及床位/节点状态"""
    wards = db.query(Ward).all()
    result = []
    for ward in wards:
        beds = db.query(Bed).filter_by(ward_id=ward.id).all()
        nodes = db.query(EdgeNode).filter_by(ward_id=ward.id).all()
        # 未确认的 P1/P2 事件数
        pending_count = db.query(func.count(SafetyEvent.id)).filter(
            SafetyEvent.ward_id == ward.id,
            SafetyEvent.priority.in_(["P1", "P2"]),
            SafetyEvent.state.in_(["new", "notified", "acknowledged"]),
        ).scalar() or 0
        
        beds_data = []
        for b in beds:
            bed_pending = db.query(func.count(SafetyEvent.id)).filter(
                SafetyEvent.bed_id == b.id,
                SafetyEvent.state.in_(["new", "notified", "acknowledged"]),
            ).scalar() or 0
            beds_data.append({
                "id": b.id,
                "name": b.name,
                "status": b.status,
                "patient_alias": b.patient_alias,
                "pending_events": bed_pending,
            })

        result.append({
            "id": ward.id,
            "name": ward.name,
            "ward_type": ward.ward_type,
            "location": ward.location,
            "status": ward.status,
            "beds": beds_data,
            "nodes": [{"id": n.id, "status": n.status, "bed_id": n.bed_id,
                       "last_heartbeat": n.last_heartbeat.isoformat() + "Z" if n.last_heartbeat else None,
                       "buffered_events": n.buffered_events} for n in nodes],
            "pending_alerts": pending_count,
        })
    return {"code": 0, "message": "success", "data": result}


@router.get("/api/wards/{ward_id}")
def get_ward(ward_id: str, db: Session = Depends(get_db)):
    """获取病区详情"""
    ward = db.query(Ward).filter_by(id=ward_id).first()
    if not ward:
        raise HTTPException(status_code=404, detail="病区不存在")
    beds = db.query(Bed).filter_by(ward_id=ward_id).all()
    
    beds_data = []
    for b in beds:
        bed_pending = db.query(func.count(SafetyEvent.id)).filter(
            SafetyEvent.bed_id == b.id,
            SafetyEvent.state.in_(["new", "notified", "acknowledged"]),
        ).scalar() or 0
        beds_data.append({
            "id": b.id,
            "name": b.name,
            "status": b.status,
            "patient_alias": b.patient_alias,
            "pending_events": bed_pending,
        })
        
    return {
        "code": 0, "message": "success",
        "data": {
            "id": ward.id, "name": ward.name, "ward_type": ward.ward_type,
            "location": ward.location, "status": ward.status,
            "beds": beds_data,
        }
    }


# ===================== 床位占用可视化 =====================

@router.get("/api/beds/occupancy")
def get_bed_occupancy(ward_id: str = Query(None), db: Session = Depends(get_db)):
    """获取床位占用情况（含患者别名 + 待处理事件数）"""
    q = db.query(Bed)
    if ward_id:
        q = q.filter(Bed.ward_id == ward_id)
    beds = q.all()
    data = []
    for bed in beds:
        pending = db.query(func.count(SafetyEvent.id)).filter(
            SafetyEvent.bed_id == bed.id,
            SafetyEvent.state.in_(["new", "notified", "acknowledged"]),
        ).scalar() or 0
        # 节点状态
        node = db.query(EdgeNode).filter_by(bed_id=bed.id).first()
        data.append({
            "bed_id": bed.id,
            "ward_id": bed.ward_id,
            "name": bed.name,
            "patient_alias": bed.patient_alias,
            "status": bed.status,
            "pending_events": pending,
            "node_status": node.status if node else "offline",
            "last_heartbeat": node.last_heartbeat.isoformat() + "Z" if node and node.last_heartbeat else None,
        })
    return {"code": 0, "message": "success", "data": data, "total": len(data)}
