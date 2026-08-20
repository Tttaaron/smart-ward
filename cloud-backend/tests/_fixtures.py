"""cloud-backend 单元测试共享设施

- 将 cloud-backend/ 加入 sys.path（与 edge-agent/tests 相同的轻量方式）
- 无 paho 环境注入假模块，保证本机轻量环境可跑
  （同 edge-agent/tests/test_mqtt_client.py 的兜底模式）
- 用 SQLite 内存库替换 MySQL SessionLocal，测试无需真实 MySQL/MQTT
"""

import os
import sys
import types

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# ─── 假 paho（无 paho 环境可跑）───
try:
    import paho.mqtt.client  # noqa: F401
    _PAHO_OK = True
except ModuleNotFoundError:
    _PAHO_OK = False

if not _PAHO_OK:
    paho_module = types.ModuleType("paho")
    mqtt_module = types.ModuleType("paho.mqtt.client")

    class _FakeMqttClient:
        """最小可用假客户端：不联网，publish 记录到 _published"""

        def __init__(self, *args, **kwargs):
            self._published = []

        def is_connected(self):
            return False

        def publish(self, topic, payload, qos=0):
            self._published.append((topic, payload, qos))
            return types.SimpleNamespace(rc=0)

        def connect(self, *a, **k):
            pass

        def disconnect(self, *a, **k):
            pass

        def loop_start(self, *a, **k):
            pass

        def loop_stop(self, *a, **k):
            pass

        def subscribe(self, *a, **k):
            pass

        def reconnect_delay_set(self, *a, **k):
            pass

    mqtt_module.Client = _FakeMqttClient
    mqtt_module.MQTT_ERR_SUCCESS = 0
    mqtt_package = types.ModuleType("paho.mqtt")
    mqtt_package.client = mqtt_module
    paho_module.mqtt = mqtt_package
    sys.modules["paho"] = paho_module
    sys.modules["paho.mqtt"] = mqtt_package
    sys.modules["paho.mqtt.client"] = mqtt_module

# ─── 假 pymysql（database.py 导入时 create_engine 仅 import dbapi，不实际连接）───
try:
    import pymysql  # noqa: F401
except ModuleNotFoundError:
    _fake_pymysql = types.ModuleType("pymysql")
    _fake_pymysql.paramstyle = "pyformat"
    _fake_pymysql.version_info = (1, 1, 0)
    sys.modules["pymysql"] = _fake_pymysql

# ─── SQLite 内存库替换 ───
from sqlalchemy import create_engine, event, BigInteger  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import database as db_module  # noqa: E402


# SQLite 中只有 INTEGER PRIMARY KEY 才自动递增，BIGINT 主键（MySQL
# 下 AUTO_INCREMENT）在 SQLite 不会自增，导致 NOT NULL 失败。
# 用 before_insert 事件为测试库的 BigInteger 主键生成自增 id，
# 不改动生产代码（生产走 MySQL 无此问题）。
_bigint_ids: dict = {}


@event.listens_for(db_module.Base, "before_insert", propagate=True)
def _auto_bigint_pk(mapper, connection, target):
    for col in mapper.persist_selectable.c:
        if col.primary_key and col.autoincrement and isinstance(col.type, BigInteger):
            if getattr(target, col.name) is None:
                key = (mapper.local_table.name, col.name)
                _bigint_ids[key] = _bigint_ids.get(key, 0) + 1
                setattr(target, col.name, _bigint_ids[key])


def install_test_db():
    """将 app 的 SessionLocal 指向全新 SQLite 内存库并建表

    mqtt_handler 在 import 时 `from .database import SessionLocal` 已绑定旧引用，
    因此此处需同步覆盖该模块属性；main 的 get_db 依赖按模块全局名查找，自动生效。
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db_module.SessionLocal = test_session

    from app import mqtt_handler as mh
    mh.SessionLocal = test_session

    db_module.Base.metadata.create_all(engine)
    return test_session()  # 返回现成 session 实例，测试直接 db.query(...)


def clear_all_tables(session):
    """清空全部表（测试方法间数据隔离；SQLite 无外键约束，直接删除即可）"""
    for table in reversed(db_module.Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()


class FakeWS:
    """记录 broadcast_sync 消息的假 WebSocket 管理器"""

    def __init__(self):
        self.messages = []

    def broadcast_sync(self, message: dict):
        self.messages.append(message)
