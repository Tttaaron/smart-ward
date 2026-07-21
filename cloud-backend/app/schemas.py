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
    runtime: str = Field("onnx", pattern="^(onnx|openvino|tensorrt|pytorch)$")
    target_device: str = Field("cpu", pattern="^(cpu|gpu|npu|auto)$")


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
