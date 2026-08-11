"""Data contracts for the cloud LLM service."""

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


Judgment = Literal["confirm", "reject", "escalate"]
Priority = Literal["P0", "P1", "P2", "P3"]
RequestMode = Literal["cloud", "hybrid"]


class InferenceRequest(BaseModel):
    """Inference request sent by an edge node over MQTT."""

    event_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    request_mode: RequestMode = "cloud"
    timeout_ms: int = Field(default=30000, ge=1)
    requested_at: str = ""
    event_type: str = Field(..., min_length=1)
    priority: Priority = "P2"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    ward_id: str = "W-01"
    node_id: str = ""
    bed_id: str = "B01"
    model_name: str = ""
    model_version: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)
    llm_prompt: Optional[str] = None


class InferenceResponse(BaseModel):
    """Inference response returned from the cloud to an edge node."""

    event_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    judgment: Judgment
    confidence: float = Field(..., ge=0.0, le=1.0)
    advice: str = Field(..., min_length=1)
    latency_ms: float = Field(..., ge=0.0)
    model_name: str = "Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4"
    model_version: str = "gptq-int4"


class MqttEnvelope(BaseModel):
    """Common MQTT envelope used by edge-agent and cloud services."""

    message_id: str = ""
    event_id: Optional[str] = None
    schema_version: str = "v1"
    occurred_at: str = ""
    source: str = ""
    trace_id: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
