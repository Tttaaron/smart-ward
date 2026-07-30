"""协同训练调度 API（空壳）

建鸿/振鑫填充实际算法后，前端可通过本 API 查看训练轮次、参与节点、
聚合结果与精度变化。

训练链路与实时告警业务隔离（独立主题 training/{job_id}/...），
不影响在线识别服务。
"""

from fastapi import FastAPI
from pydantic import BaseModel
from .scheduler import TrainingScheduler, Strategy, ClientUpdate

app = FastAPI(title="智慧病房协同训练调度", version="0.3.0")

# 全局调度器实例（演示阶段单例，生产环境需持久化）
scheduler = TrainingScheduler(strategy=Strategy.SYNC_FEDAVG)


# ===== 请求模型 =====

class StartRoundRequest(BaseModel):
    """启动训练轮次请求体"""
    participants: list[str]
    round_id: int = 1


class SubmitUpdateRequest(BaseModel):
    """边缘节点训练更新上报请求体"""
    node_id: str
    sample_count: int = 0


@app.get("/")
def root():
    return {"message": "智慧病房协同训练调度服务运行中（骨架）"}


@app.get("/health")
def health():
    return {"status": "ok", "strategy": scheduler.strategy.value, "rounds": len(scheduler.rounds)}


@app.post("/rounds/{job_id}")
def start_round(job_id: str, req: StartRoundRequest):
    """启动一轮训练（空壳）"""
    r = scheduler.start_round(job_id, req.participants, req.round_id)
    return {
        "code": 0, "message": "success",
        "data": {
            "job_id": r.job_id, "round_id": r.round_id,
            "strategy": r.strategy.value, "state": r.state.value,
            "participants": r.participants,
        }
    }


@app.get("/rounds/{job_id}/{round_id}")
def get_round(job_id: str, round_id: int):
    """查询训练轮次状态"""
    key = f"{job_id}-{round_id}"
    r = scheduler.rounds.get(key)
    if not r:
        return {"code": 404, "message": "轮次不存在", "data": None}
    return {
        "code": 0, "message": "success",
        "data": {
            "job_id": r.job_id, "round_id": r.round_id,
            "strategy": r.strategy.value, "state": r.state.value,
            "participants": r.participants,
            "updates_collected": len(r.updates),
            "min_participants": r.min_participants,
        }
    }


@app.post("/rounds/{job_id}/{round_id}/update")
def submit_update(job_id: str, round_id: int, req: SubmitUpdateRequest):
    """接收边缘节点训练更新上报（空壳，仅记录到达）"""
    update = ClientUpdate(
        node_id=req.node_id, round_id=round_id,
        weights_summary={}, sample_count=req.sample_count,
        training_seconds=0.0, loss=0.0, accuracy=0.0,
    )
    ready = scheduler.collect_update(job_id, round_id, update)
    return {"code": 0, "message": "success", "data": {"ready_to_aggregate": ready}}


@app.post("/rounds/{job_id}/{round_id}/aggregate")
def aggregate(job_id: str, round_id: int):
    """触发聚合（空壳，返回骨架结果）"""
    result = scheduler.aggregate(job_id, round_id)
    if not result:
        return {"code": 400, "message": "参与节点不足或轮次不存在", "data": None}
    return {"code": 0, "message": "success", "data": result}
