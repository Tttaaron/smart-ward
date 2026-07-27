"""智慧病房云端事件中心 API

从教室"状态查询"改造为病房"事件中心"（对齐方案书 §6.2）：
- 新建事件状态机：new -> notified -> acknowledged -> resolved/false_positive/escalated
- 提供病区/床位/事件/告警确认/模型版本/节点健康 API
- WebSocket 推送增量事件，REST 用于查询和处置命令

复用 edge/main.py 的 startup/shutdown 钩子、ws_manager.loop 赋值、
/ws 端点形状、异常处理结构。
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from .database import (
    init_db, get_db,
    Ward, Bed, EdgeNode, Observation, SafetyEvent, AlertTask,
    EventDisposition, ModelVersion, ModelDeployment, AuditLog, ShiftSummary,
)
from .mqtt_handler import MqttHandler
from .websocket_manager import WebSocketManager
from .schemas import AckRequest, ModelDeployRequest, EnvControlRequest, ShiftSummaryRequest
from .logger import get_logger

logger = get_logger(__name__)

app = FastAPI(title="智慧病房事件中心 API", version="0.1.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ws_manager = WebSocketManager()
mqtt_handler = MqttHandler(ws_manager)


@app.on_event("startup")
async def startup():
    init_db()
    ws_manager.loop = asyncio.get_event_loop()
    mqtt_handler.connect()
    logger.info("云端事件中心启动完成")


@app.on_event("shutdown")
async def shutdown():
    mqtt_handler.disconnect()
    logger.info("云端事件中心已关闭")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": exc.detail, "data": None}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"未处理异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": "服务器内部错误", "data": None}
    )


# ===================== 病区与床位 =====================

@app.get("/api/wards")
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
        result.append({
            "id": ward.id,
            "name": ward.name,
            "ward_type": ward.ward_type,
            "location": ward.location,
            "status": ward.status,
            "beds": [{"id": b.id, "name": b.name, "status": b.status} for b in beds],
            "nodes": [{"id": n.id, "status": n.status, "bed_id": n.bed_id,
                       "last_heartbeat": n.last_heartbeat.isoformat() + "Z" if n.last_heartbeat else None,
                       "buffered_events": n.buffered_events} for n in nodes],
            "pending_alerts": pending_count,
        })
    return {"code": 0, "message": "success", "data": result}


@app.get("/api/wards/{ward_id}")
def get_ward(ward_id: str, db: Session = Depends(get_db)):
    """获取病区详情"""
    ward = db.query(Ward).filter_by(id=ward_id).first()
    if not ward:
        raise HTTPException(status_code=404, detail="病区不存在")
    beds = db.query(Bed).filter_by(ward_id=ward_id).all()
    return {
        "code": 0, "message": "success",
        "data": {
            "id": ward.id, "name": ward.name, "ward_type": ward.ward_type,
            "location": ward.location, "status": ward.status,
            "beds": [{"id": b.id, "name": b.name, "status": b.status} for b in beds],
        }
    }


# ===================== 安全事件 =====================

@app.get("/api/events")
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

    start = datetime.now(timezone.utc) - timedelta(hours=hours)
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


@app.get("/api/events/{event_id}")
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


@app.post("/api/events/{event_id}/ack")
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
        "occurred_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    # MQTT 下发到边缘端
    mqtt_handler.publish_ack(event.ward_id, event_id, ack_payload)
    # 本地直接处理（边缘端收到后会再次上报，但前端不应等待）
    mqtt_handler._handle_ack(ack_payload)
    return {"code": 0, "message": "success", "data": {"event_id": event_id, "action": body.action}}


# ===================== 节点健康 =====================

@app.get("/api/nodes")
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


# ===================== 观测数据查询 =====================

@app.get("/api/observations")
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
    start = datetime.now(timezone.utc) - timedelta(hours=hours)
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


# ===================== 模型管理 =====================

@app.get("/api/models")
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


@app.post("/api/models/deploy")
def deploy_model(body: ModelDeployRequest, node_id: str = Query(...), db: Session = Depends(get_db)):
    """下发模型到指定节点"""
    deploy_payload = {
        "model_name": body.model_name,
        "model_version": body.model_version,
        "artifact_url": body.artifact_url,
        "checksum": body.checksum,
        "runtime": body.runtime,
        "target_device": body.target_device,
        "occurred_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
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

@app.get("/api/stats")
def get_system_stats(db: Session = Depends(get_db)):
    """获取系统全局统计"""
    total_wards = db.query(func.count(Ward.id)).scalar() or 0
    total_beds = db.query(func.count(Bed.id)).scalar() or 0
    online_nodes = db.query(func.count(EdgeNode.id)).filter(EdgeNode.status == "online").scalar() or 0
    total_nodes = db.query(func.count(EdgeNode.id)).scalar() or 0

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
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
            "online_nodes": online_nodes,
            "total_nodes": total_nodes,
            "events_today": events_today,
            "pending_events": pending_events,
            "p1_pending": p1_pending,
        }
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "智慧病房事件中心 API 运行中"}


# ===================== 交接班摘要 =====================

@app.get("/api/shift-summaries")
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


@app.post("/api/shift-summaries/generate")
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

    # 本地时间（+08:00）转 UTC 查询（事件 occurred_at 存的是 UTC）
    from datetime import timezone as _tz
    local_tz = _tz(timedelta(hours=8))
    start_time = local_start.replace(tzinfo=local_tz).astimezone(_tz.utc).replace(tzinfo=None)
    end_time = local_end.replace(tzinfo=local_tz).astimezone(_tz.utc).replace(tzinfo=None)

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

    # 事件类型分布
    type_dist = {}
    for e in events:
        type_dist[e.event_type] = type_dist.get(e.event_type, 0) + 1
    type_summary = "；".join(f"{k}={v}次" for k, v in sorted(type_dist.items(), key=lambda x: -x[1]))

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
        occurred_at=datetime.now(timezone.utc),
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


# ===================== 床位占用可视化 =====================

@app.get("/api/beds/occupancy")
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


# ===================== 环境控制 =====================

@app.post("/api/env/control")
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
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(audit)
    db.commit()

    return {
        "code": 0, "message": "success",
        "data": {"node_id": body.node_id, "device": body.device, "action": body.action}
    }


# ===================== WebSocket =====================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            try:
                data = json.loads(msg)
                if data.get("type") == "pong":
                    await ws_manager.handle_pong(websocket)
            except (json.JSONDecodeError, Exception):
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
