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

# ===== 连接配置 =====
# 优先级：DATABASE_URL 显式指定 > MYSQL_HOST（兼容原部署）> 默认 SQLite（零依赖演示）
DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    if os.getenv("MYSQL_HOST"):
        MYSQL_HOST = os.getenv("MYSQL_HOST")
        MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
        MYSQL_USER = os.getenv("MYSQL_USER", "smart_ward")
        MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "smartward_pass")
        MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "smart_ward")
        DATABASE_URL = (
            f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}"
            f"/{MYSQL_DATABASE}?charset=utf8mb4"
        )
    else:
        # 默认 SQLite：单文件落盘（cloud-backend/data/smart_ward.db），SQLITE_PATH 可覆盖
        _SQLITE_PATH = os.getenv("SQLITE_PATH") or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "smart_ward.db")
        os.makedirs(os.path.dirname(os.path.abspath(_SQLITE_PATH)), exist_ok=True)
        DATABASE_URL = f"sqlite:///{os.path.abspath(_SQLITE_PATH)}"

IS_SQLITE = DATABASE_URL.startswith("sqlite")

_engine_kwargs = {}
if IS_SQLITE:
    # FastAPI 线程池 / paho 回调线程共用连接，需关闭同线程检查
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs.update(pool_pre_ping=True, pool_recycle=3600)

engine = create_engine(DATABASE_URL, **_engine_kwargs)

if IS_SQLITE:
    # SQLite 下 BIGINT 主键不走 rowid 自增：方言降级为 INTEGER（原生 AUTO_INCREMENT）
    from sqlalchemy import event as _sa_event

    @_sa_event.listens_for(engine, "connect")
    def _sqlite_pragma(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# BigInteger 主键在 SQLite 方言下降级为 INTEGER（rowid 自增），MySQL 行为不变
BigIntPK = BigInteger().with_variant(Integer(), "sqlite")


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
    patient_alias = Column(String(50))  # 演示用匿名别名，不存真实姓名
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
    id = Column(BigIntPK, primary_key=True, autoincrement=True)
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
    id = Column(BigIntPK, primary_key=True, autoincrement=True)
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
    id = Column(BigIntPK, primary_key=True, autoincrement=True)
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
    id = Column(BigIntPK, primary_key=True, autoincrement=True)
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
    id = Column(BigIntPK, primary_key=True, autoincrement=True)
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
    id = Column(BigIntPK, primary_key=True, autoincrement=True)
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
    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    action = Column(String(30), nullable=False)
    target_type = Column(String(20))
    target_id = Column(String(64), index=True)
    operator_id = Column(String(50))
    detail = Column(Text)                          # JSON
    occurred_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ShiftSummary(Base):
    """交接班摘要"""
    __tablename__ = "shift_summaries"
    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    ward_id = Column(String(10), nullable=False, index=True)
    shift_date = Column(DateTime, nullable=False)  # 日期
    shift_period = Column(String(10), nullable=False)  # day/evening/night
    operator_id = Column(String(50))
    summary_text = Column(Text, nullable=False)
    event_count = Column(Integer, default=0)
    p1_count = Column(Integer, default=0)
    p2_count = Column(Integer, default=0)
    resolved_count = Column(Integer, default=0)
    false_positive_count = Column(Integer, default=0)
    avg_response_seconds = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class EdgeShiftHandover(Base):
    """边缘 LLM 生成的自然交接班记录（云端镜像，由 agent/response 写入）"""
    __tablename__ = "edge_shift_handovers"
    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    node_id = Column(String(30), nullable=False, index=True)
    ward_id = Column(String(10), nullable=False, index=True)
    bed_id = Column(String(10), nullable=False, index=True)
    shift_date = Column(DateTime, nullable=False)
    shift_period = Column(String(10), nullable=False)
    window_start = Column(DateTime)
    window_end = Column(DateTime)
    event_count = Column(Integer, default=0)
    p1_count = Column(Integer, default=0)
    patient = Column(Text)                         # JSON 患者档案
    handover_text = Column(Text, nullable=False)
    watch_points = Column(Text)                    # JSON 结构化交班注意
    model_name = Column(String(50))
    model_version = Column(String(50))
    mode = Column(String(10), default="mock")
    trace_id = Column(String(64), index=True)
    generated_at = Column(DateTime)


class EdgeAgentMessage(Base):
    """边缘 Agent 消息审计（问答 / 实时播报）"""
    __tablename__ = "edge_agent_messages"
    id = Column(BigIntPK, primary_key=True, autoincrement=True)
    request_id = Column(String(64), index=True)
    node_id = Column(String(30), index=True)
    ward_id = Column(String(10))
    bed_id = Column(String(10))
    action = Column(String(20))                    # ask / broadcast
    question = Column(Text)
    answer = Column(Text)                          # 回答或播报文本
    status = Column(String(20), default="ok")
    model_name = Column(String(50))
    trace_id = Column(String(64), index=True)
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
    """初始化数据库表，带重试等待数据库就绪；空库时写入演示基础数据"""
    for i in range(max_retries):
        try:
            Base.metadata.create_all(bind=engine)
            _seed_demo_data_if_empty()
            logger.info("数据库表初始化完成")
            return
        except OperationalError as e:
            logger.warning(f"等待数据库就绪 ({i+1}/{max_retries}): {e}")
            time.sleep(retry_interval)
    raise RuntimeError(f"数据库连接失败，已重试 {max_retries} 次")


def _seed_demo_data_if_empty():
    """空库时写入演示基础数据（对齐 init.sql 初始数据；有数据则跳过）"""
    db = SessionLocal()
    try:
        if db.query(Ward).first():
            return
        db.add(Ward(id="W-01", name="普通病房 W-01", ward_type="general",
                    location="三楼东侧", status="online"))
        for bed_id, name, alias in [("B01", "1床", "张阿姨"),
                                    ("B02", "2床", "李伯伯"),
                                    ("B03", "3床", "王奶奶")]:
            db.add(Bed(id=bed_id, ward_id="W-01", name=name,
                       patient_alias=alias, status="idle"))
            db.add(EdgeNode(id=f"EDGE-W01-{bed_id}", ward_id="W-01",
                            bed_id=bed_id, status="offline"))
        db.commit()
        logger.info("已写入演示基础数据（1 病区 / 3 床位 / 3 边缘节点）")
    except Exception as exc:
        db.rollback()
        logger.warning(f"演示数据写入跳过: {exc}")
    finally:
        db.close()
