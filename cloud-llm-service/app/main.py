"""云端LLM协同推理服务 — FastAPI

职责:
  - MQTT 订阅边缘端推理请求
  - 调用 Qwen2.5-14B (mock/vLLM) 二次研判
  - 回传推理结果到边缘端

端点:
  GET  /health         服务健康检查
  GET  /stats          请求统计
  POST /infer          直接推理（调试用，跳过MQTT）
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .llm_client import LLMClient
from .mqtt_handler import CloudMqttHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

llm_mode = os.getenv("LLM_MODE", "mock")
llm_client = LLMClient(mode=llm_mode)
mqtt_handler = CloudMqttHandler(llm_client)


@asynccontextmanager
async def lifespan(app: FastAPI):
    mqtt_handler.connect()
    logger.info(f"cloud-llm-service started (mode={llm_mode})")
    yield
    mqtt_handler.disconnect()
    logger.info("cloud-llm-service stopped")


app = FastAPI(
    title="智慧病房云端LLM推理服务",
    description="Qwen2.5-14B 云端二次研判，协同推理闭环",
    version="0.1.0",
    lifespan=lifespan,
)


# ─── 请求模型 ───

class DirectInferRequest(BaseModel):
    event_id: str = Field(..., description="事件ID")
    trace_id: str = Field(default="", description="追踪ID")
    event_type: str = Field(..., description="事件类型")
    priority: str = Field(default="P2")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    bed_id: str = Field(default="B01")
    node_id: str = Field(default="EDGE-W01-B01")
    details: dict = Field(default_factory=dict)
    llm_prompt: str = Field(default="")


# ─── 端点 ───

@app.get("/health")
async def health():
    """服务健康检查"""
    return {
        "status": "ok",
        "service": "cloud-llm-service",
        "version": "0.1.0",
        "llm_mode": llm_client.mode,
        "model": llm_client.model_name,
    }


@app.get("/stats")
async def stats():
    """请求统计"""
    return {"code": 0, "data": mqtt_handler.get_stats()}


@app.post("/infer")
async def direct_infer(req: DirectInferRequest):
    """直接推理（绕过MQTT，用于调试和测试）

    返回与 MQTT response payload 一致的研判结果。
    """
    result = llm_client.infer(req.model_dump())
    return {
        "code": 0,
        "data": {
            "event_id": result["event_id"],
            "trace_id": result["trace_id"] or req.trace_id,
            "judgment": result["judgment"],
            "confidence": result["confidence"],
            "advice": result["advice"],
            "latency_ms": result["latency_ms"],
            "model_name": result["model_name"],
            "model_version": result["model_version"],
        },
    }


@app.get("/")
async def root():
    return {
        "service": "智慧病房云端LLM推理服务",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "stats": "/stats",
            "infer": "/infer (POST)",
        },
    }
