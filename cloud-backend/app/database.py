"""云端数据库 ORM 模型（病房事件中心）

对齐方案书 §4.2，将教室的 Room/SensorData/DeviceStatus/ControlLog/AlarmLog
替换为病房的 Ward/Bed/EdgeNode/Observation/SafetyEvent/AlertTask/
EventDisposition/ModelVersion/ModelDeployment/AuditLog。

复用 edge/ 的 engine/session/Base 构造、init_db 重试、get_db 依赖模式。
"""

import os
import time
from datetime import datetime

from sqlalchemy import create_engine, Column, String, Integer, BigInteger, Float, DateTime, Text, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError

from .logger import get_logger

logger = get_logger(__name__)

# ===== 连接配置（与 .env / docker-compose 对齐）=====
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_USER = os.getenv("MYSQL_USER", "smart_ward")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "smartward_pass")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "smart_ward")

DATABASE_URL = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}"
    f"/{MYSQL_DATABASE}?charset=utf8mb4"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ============================================================
# ORM 模型（10 张表）
# ============================================================

class Ward(Base):
    """病区"""
    __tablename__ = "wards"
    id = Column(String(10), primary_key=True)
    name = Column(String(50), nullable=False)
    ward_type = Column(String(20), default="general")
    location = Column(String(100))
    status = Column(String(20), default="online")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Bed(Base):
    """床位"""
    __tablename__ = "beds"
    id = Column(String(10), primary_key=True)
    ward_id = Column(String(10), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    status = Column(String(20), default="idle")  # idle/occupied/alert/maintenance
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EdgeNode(Base):
    """边缘节点"""
    __tablename__ = "edge_nodes"
    id = Column(String(30), primary_key=True)
    ward_id = Column(String(10), nullable=False, index=True)
    bed_id = Column(String(10), index=True)
    status = Column(String(20), default="offline")  # online/degraded/offline
    model_version = Column(String(50))
    last_heartbeat = Column(DateTime)
    buffered_events = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Observation(Base):
    """多源观测数据"""
    __tablename__ = "observations"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ward_id = Column(String(10), nullable=False)
    node_id = Column(String(30), nullable=False)
    bed_id = Column(String(10), nullable=False)
    source_type = Column(String(20), nullable=False)
    data = Column(Text, nullable=False)          # JSON
    quality = Column(Text)                        # JSON
    timestamp = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SafetyEvent(Base):
    """安全事件（核心）"""
    __tablename__ = "safety_events"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_id = Column(String(64), nullable=False, unique=True, index=True)
    ward_id = Column(String(10), nullable=False)
    node_id = Column(String(30), nullable=False)
    bed_id = Column(String(10), nullable=False)
    event_type = Column(String(30), nullable=False, index=True)
    priority = Column(String(5), nullable=False)
    state = Column(String(20), nullable=False, default="new")
    confidence = Column(Float, nullable=False)
    model_name = Column(String(50), nullable=False)
    model_version = Column(String(50), nullable=False)
    inference_ms = Column(Integer, default=0)
    evidence_refs = Column(Text)                   # JSON
    rule_hits = Column(Text)                       # JSON
    details = Column(Text)                         # JSON
    occurred_at = Column(DateTime, nullable=False)
    detected_at = Column(DateTime)
    acknowledged_at = Column(DateTime)
    resolved_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class AlertTask(Base):
    """告警任务"""
    __tablename__ = "alert_tasks"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_id = Column(String(64), nullable=False, index=True)
    ward_id = Column(String(10), nullable=False)
    bed_id = Column(String(10), nullable=False)
    priority = Column(String(5), nullable=False)
    channel = Column(String(20), default="ws")
    notified_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class EventDisposition(Base):
    """事件处置记录"""
    __tablename__ = "event_dispositions"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_id = Column(String(64), nullable=False, index=True)
    action = Column(String(20), nullable=False)
    operator_id = Column(String(50), nullable=False)
    operator_name = Column(String(50))
    operator_role = Column(String(20))
    result = Column(String(200))
    note = Column(Text)
    occurred_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ModelVersion(Base):
    """模型版本"""
    __tablename__ = "model_versions"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_name = Column(String(50), nullable=False)
    model_version = Column(String(50), nullable=False, unique=True)
    artifact_url = Column(String(500), nullable=False)
    checksum = Column(String(128))
    runtime = Column(String(20), default="onnx")
    target_device = Column(String(10), default="cpu")
    config = Column(Text)                          # JSON
    status = Column(String(20), default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)


class ModelDeployment(Base):
    """模型部署记录"""
    __tablename__ = "model_deployments"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_name = Column(String(50), nullable=False)
    model_version = Column(String(50), nullable=False)
    node_id = Column(String(30), nullable=False, index=True)
    ward_id = Column(String(10))
    action = Column(String(20), nullable=False)   # deploy/rollback
    status = Column(String(20), default="pending")
    deployed_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """审计日志"""
    __tablename__ = "audit_logs"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    action = Column(String(30), nullable=False)
    target_type = Column(String(20))
    target_id = Column(String(64), index=True)
    operator_id = Column(String(50))
    detail = Column(Text)                          # JSON
    occurred_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# 会话与初始化（复用 edge/ 模式）
# ============================================================

def get_db():
    """FastAPI 依赖：获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(max_retries: int = 30, retry_interval: int = 2):
    """初始化数据库表，带重试等待 MySQL 就绪"""
    for i in range(max_retries):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("数据库表初始化完成")
            return
        except OperationalError as e:
            logger.warning(f"等待数据库就绪 ({i+1}/{max_retries}): {e}")
            time.sleep(retry_interval)
    raise RuntimeError(f"数据库连接失败，已重试 {max_retries} 次")
