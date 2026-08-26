"""边缘 Agent（交接班/问答）：命令下发、记录与审计查询。

端点从护士站前端发起：生成自然交接班 / 自然语言问答由云端经
MQTT 请求-响应（request_agent）转发到边缘本地 LLM，查询类端点
读取边缘上报后落库的 EdgeShiftHandover / EdgeAgentMessage。
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import (
    get_db,
    EdgeNode, AuditLog, EdgeShiftHandover, EdgeAgentMessage,
)
from ..deps import mqtt_handler
from ..schemas import EdgeHandoverRequest, EdgeAskRequest
from ..logger import get_logger
from ..timeutil import utc_now

logger = get_logger(__name__)

router = APIRouter()


def _check_agent_result(result: dict, fail_detail: str):
    """request_agent 结果的统一错误映射（离线/超时/失败）。"""
    if result.get("offline"):
        raise HTTPException(status_code=504, detail="边缘节点离线，请检查 MQTT/边端状态")
    if result.get("timeout"):
        raise HTTPException(status_code=504, detail="边缘 Agent 响应超时，请稍后重试")
    if result.get("status") != "ok":
        raise HTTPException(status_code=502, detail=f"{fail_detail}: {result.get('error', '未知错误')}")


# ===================== 边缘 Agent（交接班/问答） =====================

@router.post("/api/edge-agent/handover/generate")
def generate_edge_handover(body: EdgeHandoverRequest, db: Session = Depends(get_db)):
    """下发命令到边缘本地 LLM 生成自然交接班，等待并返回结果"""
    node = db.query(EdgeNode).filter_by(id=body.node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="边缘节点不存在")

    payload = {
        "action": "generate_handover",
        "ward_id": body.ward_id, "bed_id": body.bed_id,
        "shift_date": body.shift_date, "shift_period": body.shift_period,
        "requested_by": "nurse-station",
    }
    result = mqtt_handler.request_agent(body.node_id, payload, body.wait_seconds)
    _check_agent_result(result, "边端生成失败")

    audit = AuditLog(
        action="edge_handover_generate",
        target_type="edge_node", target_id=body.node_id,
        operator_id="nurse-station",
        detail=json.dumps({"bed_id": body.bed_id, "shift_date": body.shift_date,
                           "shift_period": body.shift_period}, ensure_ascii=False),
        occurred_at=utc_now(),
    )
    db.add(audit)
    db.commit()
    return {"code": 0, "message": "success", "data": result}


@router.get("/api/edge-agent/handovers")
def list_edge_handovers(
    ward_id: str = Query(None),
    bed_id: str = Query(None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """查询边缘 LLM 自然交接班记录"""
    q = db.query(EdgeShiftHandover)
    if ward_id:
        q = q.filter(EdgeShiftHandover.ward_id == ward_id)
    if bed_id:
        q = q.filter(EdgeShiftHandover.bed_id == bed_id)
    records = q.order_by(desc(EdgeShiftHandover.generated_at)).limit(limit).all()
    data = [{
        "id": r.id, "node_id": r.node_id, "ward_id": r.ward_id, "bed_id": r.bed_id,
        "shift_date": r.shift_date.strftime("%Y-%m-%d") if r.shift_date else None,
        "shift_period": r.shift_period,
        "event_count": r.event_count, "p1_count": r.p1_count,
        "handover_text": r.handover_text,
        "watch_points": json.loads(r.watch_points) if r.watch_points else [],
        "model_name": r.model_name, "model_version": r.model_version,
        "mode": r.mode, "trace_id": r.trace_id,
        "generated_at": r.generated_at.isoformat() + "Z" if r.generated_at else None,
    } for r in records]
    return {"code": 0, "message": "success", "data": data, "total": len(data)}


@router.post("/api/edge-agent/ask")
def ask_edge_agent(body: EdgeAskRequest, db: Session = Depends(get_db)):
    """向边缘 Agent 提问（自然语言查本床历史），等待并返回回答"""
    node = db.query(EdgeNode).filter_by(id=body.node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="边缘节点不存在")

    payload = {
        "action": "ask",
        "ward_id": body.ward_id, "bed_id": body.bed_id,
        "question": body.question,
        "requested_by": "nurse-station",
    }
    result = mqtt_handler.request_agent(body.node_id, payload, body.wait_seconds)
    _check_agent_result(result, "边端问答失败")

    audit = AuditLog(
        action="edge_agent_ask",
        target_type="edge_node", target_id=body.node_id,
        operator_id="nurse-station",
        detail=json.dumps({"bed_id": body.bed_id, "question": body.question[:100]},
                          ensure_ascii=False),
        occurred_at=utc_now(),
    )
    db.add(audit)
    db.commit()
    return {"code": 0, "message": "success", "data": result}


@router.get("/api/edge-agent/messages")
def list_edge_agent_messages(
    node_id: str = Query(None),
    action: str = Query(None, pattern="^(ask|broadcast)$"),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """查询边缘 Agent 消息（问答/播报审计）"""
    q = db.query(EdgeAgentMessage)
    if node_id:
        q = q.filter(EdgeAgentMessage.node_id == node_id)
    if action:
        q = q.filter(EdgeAgentMessage.action == action)
    records = q.order_by(desc(EdgeAgentMessage.created_at)).limit(limit).all()
    data = [{
        "id": r.id, "request_id": r.request_id, "node_id": r.node_id,
        "ward_id": r.ward_id, "bed_id": r.bed_id, "action": r.action,
        "question": r.question, "answer": r.answer, "status": r.status,
        "model_name": r.model_name, "trace_id": r.trace_id,
        "created_at": r.created_at.isoformat() + "Z" if r.created_at else None,
    } for r in records]
    return {"code": 0, "message": "success", "data": data, "total": len(data)}
