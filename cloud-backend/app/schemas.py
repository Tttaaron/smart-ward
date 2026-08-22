"""Pydantic 请求模型（病房事件中心）

复用 edge/ 的 Pydantic v2 + Field(pattern) 模式。
病房设备/操作词表替换教室的 ac/light。
"""

from pydantic import BaseModel, Field


class AckRequest(BaseModel):
    """告警确认请求"""
    action: str = Field(..., pattern="^(acknowledge|resolve|false_positive|escalate)$")
    operator_id: str = Field(..., min_length=1, max_length=50)
    operator_name: str = Field(None, max_length=50)
    operator_role: str = Field(None, pattern="^(nurse|charge_nurse|admin|observer)$")
    result: str = Field(None, max_length=200)
    note: str = Field(None, max_length=2000)


class ModelDeployRequest(BaseModel):
    """模型下发请求"""
    model_name: str = Field(..., max_length=50)
    model_version: str = Field(..., max_length=50)
    artifact_url: str = Field(..., max_length=500)
    checksum: str = Field(None, max_length=128)
    runtime: str = Field("onnx", pattern="^(onnx|openvino|tensorrt|pytorch|gguf)$")
    target_device: str = Field("cpu", pattern="^(cpu|gpu|npu|auto)$")
    # 模型类型：vision（默认，视觉推理引擎）/ llm（边缘 LLM GGUF 运行时切换）
    model_kind: str = Field("vision", pattern="^(vision|llm)$")


class EnvControlRequest(BaseModel):
    """环境控制请求（手动触发环境联动）"""
    node_id: str = Field(..., max_length=30)
    device: str = Field(..., pattern="^(ac|light|fresh_air)$")
    action: str = Field(..., pattern="^(on|off)$")
    reason: str = Field(None, max_length=200)


class ShiftSummaryRequest(BaseModel):
    """交接班摘要生成请求"""
    ward_id: str = Field(..., max_length=10)
    shift_date: str = Field(..., description="日期 YYYY-MM-DD")
    shift_period: str = Field("day", pattern="^(day|evening|night)$")
    operator_id: str = Field("auto", max_length=50)


class EdgeHandoverRequest(BaseModel):
    """边缘 Agent 交接班生成请求（命令下发到边端本地 LLM）"""
    node_id: str = Field(..., max_length=30)
    ward_id: str = Field("W-01", max_length=10)
    bed_id: str = Field(..., max_length=10)
    shift_date: str = Field("", description="日期 YYYY-MM-DD，留空取边端今天")
    shift_period: str = Field("day", pattern="^(day|evening|night)$")
    wait_seconds: int = Field(25, ge=1, le=60, description="等待边缘响应秒数")


class EdgeAskRequest(BaseModel):
    """边缘 Agent 问答请求（自然语言查本床历史）"""
    node_id: str = Field(..., max_length=30)
    ward_id: str = Field("W-01", max_length=10)
    bed_id: str = Field(..., max_length=10)
    question: str = Field(..., min_length=1, max_length=500)
    wait_seconds: int = Field(20, ge=1, le=60, description="等待边缘响应秒数")


class InjectionRequest(BaseModel):
    """手动事件注入请求（演示/调试用）"""
    ward_id: str = Field("W-01", max_length=10)
    bed_id: str = Field("B01", max_length=10)
    node_id: str = Field(None, max_length=30)
    event_type: str = Field("nurse_call", max_length=30)
    priority: str = Field(None, pattern="^(P1|P2|P3)$")
    confidence: float = Field(0.9, ge=0.0, le=1.0)
