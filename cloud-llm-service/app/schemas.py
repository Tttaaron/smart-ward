"""云端LLM服务数据模型

对齐 edge-agent MQTT 契约:
  - 订阅: ward/{ward_id}/node/{node_id}/inference/request
  - 发布: node/{node_id}/inference/response
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from uuid import uuid4


class InferenceRequest(BaseModel):
    """边缘端发来的推理请求"""
    event_id: str
    trace_id: str = ""
    request_mode: str = "cloud"          # cloud | hybrid
    timeout_ms: int = 30000
    requested_at: str = ""
    # 事件数据
    event_type: str = ""
    priority: str = "P2"
    confidence: float = 0.0
    ward_id: str = "W-01"
    node_id: str = ""
    bed_id: str = "B01"
    model_name: str = ""
    model_version: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)
    llm_prompt: Optional[str] = None     # 边缘 LLM 预处理后的 prompt


class InferenceResponse(BaseModel):
    """云端返回的推理结果"""
    event_id: str
    trace_id: str
    judgment: str                         # confirm | reject | escalate
    confidence: float
    advice: str
    latency_ms: float
    model_name: str = "qwen2.5-14b"
    model_version: str = "awq-int4"


class MqttEnvelope(BaseModel):
    """MQTT 消息信封（对齐 edge-agent mqtt_client._envelope）"""
    message_id: str = ""
    event_id: Optional[str] = None
    schema_version: str = "v1"
    occurred_at: str = ""
    source: str = ""
    trace_id: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
