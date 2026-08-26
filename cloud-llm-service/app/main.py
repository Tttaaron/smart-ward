"""FastAPI entrypoint for the cloud LLM inference service."""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .llm_client import LLMClient
from .mqtt_handler import CloudMqttHandler
from .schemas import InferenceResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

llm_mode = os.getenv("CLOUD_LLM_MODE", os.getenv("LLM_MODE", "mock"))
llm_client = LLMClient(mode=llm_mode)
mqtt_handler = CloudMqttHandler(llm_client)


@asynccontextmanager
async def lifespan(app: FastAPI):
    mqtt_handler.connect()
    logger.info("cloud-llm-service started (mode=%s)", llm_client.mode)
    yield
    mqtt_handler.disconnect()
    logger.info("cloud-llm-service stopped")


app = FastAPI(
    title="智慧病房云端 LLM 推理服务",
    description="订阅边缘 inference/request，调用 Qwen2.5-14B 或 mock adapter，并回传 inference/response。",
    version="0.1.0",
    lifespan=lifespan,
)


class DirectInferRequest(BaseModel):
    event_id: str = Field(..., min_length=1, description="事件 ID")
    trace_id: str = Field(default="", description="追踪 ID")
    event_type: str = Field(..., min_length=1, description="事件类型")
    priority: str = Field(default="P2", description="优先级 P0/P1/P2/P3")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="边缘置信度")
    bed_id: str = Field(default="B01", description="床位 ID")
    ward_id: str = Field(default="W-01", description="病区 ID")
    node_id: str = Field(default="EDGE-W01-B01", description="边缘节点 ID")
    details: Dict[str, Any] = Field(default_factory=dict, description="事件详情")
    llm_prompt: str = Field(default="", description="可选云端提示词")


@app.get("/health")
async def health():
    backend = llm_client.readiness()
    return {
        "status": "ok" if backend["ready"] else "degraded",
        "service": "cloud-llm-service",
        "version": "0.1.0",
        "llm_mode": llm_client.mode,
        "model": llm_client.model_name,
        "model_version": llm_client.model_version,
        "backend": backend,
    }


@app.get("/ready")
async def ready():
    backend = llm_client.readiness()
    if not backend["ready"]:
        raise HTTPException(status_code=503, detail=backend)
    return {"status": "ready", "backend": backend}


@app.get("/stats")
async def stats():
    return {"code": 0, "data": mqtt_handler.get_stats()}


@app.post("/infer")
async def direct_infer(req: DirectInferRequest):
    result = llm_client.infer(req.model_dump())
    response = InferenceResponse(**result)
    return {"code": 0, "data": response.model_dump()}


@app.get("/")
async def root():
    return {
        "service": "智慧病房云端 LLM 推理服务",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "ready": "/ready",
            "stats": "/stats",
            "infer": "/infer (POST)",
        },
    }
