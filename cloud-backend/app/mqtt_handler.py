"""MQTT 消息处理器（病房事件中心）

订阅病房主题树，将边缘端上报的 observation/event/health
写入数据库并推送到 WebSocket。

复用 edge/ 的 MqttHandler 类骨架、重连退避、latest_state 缓存、
broadcast_sync 桥接模式；主题树和字段按方案书 §4.3 重做。
"""

import os
import json
import uuid
import paho.mqtt.client as mqtt

from .database import SessionLocal, EdgeNode, Observation, SafetyEvent, AlertTask, AuditLog
from .logger import get_logger
from .timeutil import parse_ts, utc_now, utc_now_iso

logger = get_logger(__name__)

MQTT_RECONNECT_MIN = 2
MQTT_RECONNECT_MAX = 60

# 兼容别名：时间工具已统一到 app/timeutil.py
_parse_ts = parse_ts


class MqttHandler:
    """MQTT 消息处理器（病房主题树）"""

    def __init__(self, ws_manager=None):
        self.broker = os.getenv("MQTT_BROKER", "localhost")
        self.port = int(os.getenv("MQTT_PORT", "1883"))
        self.ws_manager = ws_manager
        self.client = mqtt.Client(client_id=f"cloud-backend-{uuid.uuid4().hex[:8]}")
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        # 让 paho 自动管理重连退避：首次 MQTT_RECONNECT_MIN 秒，最大 MQTT_RECONNECT_MAX 秒，
        # 避免在回调线程里手动 sleep 阻塞网络循环。
        self.client.reconnect_delay_set(min_delay=MQTT_RECONNECT_MIN, max_delay=MQTT_RECONNECT_MAX)
        # 内存缓存：node_id -> 最近状态
        self.latest_state = {}
        self._reconnect_delay = MQTT_RECONNECT_MIN

    # ─── 连接回调 ───

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._reconnect_delay = MQTT_RECONNECT_MIN
            logger.info(f"MQTT 连接成功 (broker={self.broker}:{self.port})")
            # 订阅病房主题树（通配）
            topics = [
                ("ward/+/node/+/observation", 1),
                ("ward/+/node/+/event", 1),
                ("ward/+/node/+/health", 1),
                ("ward/+/alert/+/ack", 1),
            ]
            for topic, qos in topics:
                client.subscribe(topic, qos=qos)
                logger.info(f"订阅主题: {topic}")
        else:
            logger.error(f"MQTT 连接失败, 返回码: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        # 仅记录日志，重连由 paho 的 reconnect_delay_set 自动处理，
        # 不在此 sleep 或手动 reconnect，以免阻塞网络循环线程。
        if rc != 0:
            logger.warning(f"MQTT 意外断开 (rc={rc})，paho 将自动重连")
        else:
            logger.info("MQTT 正常断开")

    def _on_message(self, client, userdata, msg):
        """消息路由：按主题分发到对应处理器"""
        try:
            payload = json.loads(msg.payload.decode())
            # 解包信封：payload 实际在 envelope.payload 字段
            business_payload = payload.get("payload", payload)
            topic_parts = msg.topic.split("/")

            # ward/{ward_id}/node/{node_id}/observation
            if (len(topic_parts) == 5 and topic_parts[0] == "ward"
                    and topic_parts[2] == "node" and topic_parts[4] == "observation"):
                self._handle_observation(business_payload, envelope=payload)

            # ward/{ward_id}/node/{node_id}/event
            elif (len(topic_parts) == 5 and topic_parts[0] == "ward"
                  and topic_parts[2] == "node" and topic_parts[4] == "event"):
                self._handle_event(business_payload, envelope=payload)

            # ward/{ward_id}/node/{node_id}/health
            elif (len(topic_parts) == 5 and topic_parts[0] == "ward"
                  and topic_parts[2] == "node" and topic_parts[4] == "health"):
                self._handle_health(business_payload, envelope=payload)

            # ward/{ward_id}/alert/{event_id}/ack
            elif (len(topic_parts) == 5 and topic_parts[0] == "ward"
                  and topic_parts[2] == "alert" and topic_parts[4] == "ack"):
                self.apply_ack(business_payload, envelope=payload)

        except Exception as e:
            logger.error(f"消息处理失败: {e}, topic={msg.topic}", exc_info=True)

    # ─── 消息处理器 ───

    def _handle_observation(self, data: dict, envelope: dict = None):
        """处理观测数据：写库 + WS 广播"""
        node_id = data.get("node_id")
        ward_id = data.get("ward_id")
        bed_id = data.get("bed_id")
        ts = parse_ts(data.get("timestamp"))

        # 更新内存缓存
        if node_id not in self.latest_state:
            self.latest_state[node_id] = {"ward_id": ward_id, "bed_id": bed_id}
        self.latest_state[node_id].update({
            "last_observation": data.get("timestamp"),
            "last_update": data.get("timestamp"),
        })

        # 逐源写入 observations 表
        db = SessionLocal()
        try:
            for src in data.get("sources", []):
                obs = Observation(
                    ward_id=ward_id, node_id=node_id, bed_id=bed_id,
                    source_type=src.get("source_type"),
                    data=json.dumps(src.get("data", {}), ensure_ascii=False),
                    quality=json.dumps(src.get("quality", {}), ensure_ascii=False),
                    timestamp=ts,
                )
                db.add(obs)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"观测数据入库失败: {e}")
        finally:
            db.close()

        # WS 广播
        if self.ws_manager:
            self.ws_manager.broadcast_sync({
                "type": "observation",
                "ward_id": ward_id,
                "node_id": node_id,
                "bed_id": bed_id,
                "data": data,
                "timestamp": data.get("timestamp"),
            })

    def _handle_event(self, data: dict, envelope: dict = None):
        """处理安全事件：写库 + 创建告警任务 + WS 广播"""
        event_id = data.get("event_id")
        if not event_id:
            logger.warning("事件缺少 event_id，已丢弃")
            return

        db = SessionLocal()
        try:
            # 幂等：event_id 唯一约束
            existing = db.query(SafetyEvent).filter_by(event_id=event_id).first()
            if existing:
                # 首达入库；再次上报仅当携带云端研判回写时更新
                # （边缘端收到云端 judgment 后重报事件，details.cloud_inference
                #   携带 judgment/advice/置信度，state 为映射后的状态）
                new_details = data.get("details") or {}
                cloud_inference = new_details.get("cloud_inference")
                if cloud_inference:
                    old_details = json.loads(existing.details) if existing.details else {}
                    old_details["cloud_inference"] = cloud_inference
                    existing.details = json.dumps(old_details, ensure_ascii=False)
                    new_state = data.get("state")
                    valid_states = ("new", "notified", "acknowledged",
                                    "resolved", "false_positive", "escalated")
                    if new_state in valid_states:
                        existing.state = new_state
                    db.commit()
                    logger.info(
                        f"云端研判回写: {event_id} -> "
                        f"{cloud_inference.get('judgment')} (state={existing.state})")
                    if self.ws_manager:
                        self.ws_manager.broadcast_sync({
                            "type": "event_update",
                            "event_id": event_id,
                            "state": existing.state,
                            "cloud_inference": cloud_inference,
                        })
                else:
                    logger.debug(f"事件已存在，跳过: {event_id}")
                return

            occurred_at = parse_ts(data.get("occurred_at"))
            detected_at = parse_ts(data.get("detected_at"))

            event = SafetyEvent(
                event_id=event_id,
                ward_id=data["ward_id"],
                node_id=data["node_id"],
                bed_id=data["bed_id"],
                event_type=data["event_type"],
                priority=data["priority"],
                state="notified",  # 云端收到即标记为已通知
                confidence=data["confidence"],
                model_name=data.get("model", {}).get("model_name", "unknown"),
                model_version=data.get("model", {}).get("model_version", "unknown"),
                inference_ms=data.get("model", {}).get("inference_ms", 0),
                evidence_refs=json.dumps(data.get("evidence_refs", []), ensure_ascii=False),
                rule_hits=json.dumps(data.get("rule_hits", []), ensure_ascii=False),
                details=json.dumps(data.get("details", {}), ensure_ascii=False),
                occurred_at=occurred_at,
                detected_at=detected_at,
            )
            db.add(event)
            # flush 让 event 立即持久化，满足 alert_tasks 外键约束
            db.flush()

            # 创建告警任务（P1/P2 需通知）
            task = AlertTask(
                event_id=event_id,
                ward_id=data["ward_id"],
                bed_id=data["bed_id"],
                priority=data["priority"],
                channel="ws",
                notified_at=utc_now(),
            )
            db.add(task)

            # 审计日志
            audit = AuditLog(
                action="event_create",
                target_type="safety_event",
                target_id=event_id,
                operator_id=data.get("node_id"),
                detail=json.dumps({"event_type": data["event_type"], "priority": data["priority"]}, ensure_ascii=False),
                occurred_at=utc_now(),
            )
            db.add(audit)
            db.commit()

            # 更新床位状态为告警
            self.latest_state.setdefault(data["node_id"], {}).update({
                "ward_id": data["ward_id"],
                "bed_id": data["bed_id"],
                "last_event": data["event_type"],
                "last_update": data.get("occurred_at"),
            })

            logger.info(f"事件入库: {data['event_type']} [{data['priority']}] bed={data['bed_id']}")

        except Exception as e:
            db.rollback()
            logger.error(f"事件入库失败: {e}", exc_info=True)
        finally:
            db.close()

        # WS 广播
        if self.ws_manager:
            self.ws_manager.broadcast_sync({
                "type": "safety_event",
                "event_id": event_id,
                "ward_id": data.get("ward_id"),
                "node_id": data.get("node_id"),
                "bed_id": data.get("bed_id"),
                "event_type": data.get("event_type"),
                "priority": data.get("priority"),
                "state": "notified",
                "confidence": data.get("confidence"),
                "occurred_at": data.get("occurred_at"),
                "data": data,
            })

    def _handle_health(self, data: dict, envelope: dict = None):
        """处理节点健康心跳：更新 edge_nodes 表 + WS 广播"""
        node_id = data.get("node_id")
        if not node_id:
            return

        status = data.get("status", "online")
        ts = parse_ts(data.get("timestamp"))

        db = SessionLocal()
        try:
            node = db.query(EdgeNode).filter_by(id=node_id).first()
            if node:
                node.status = status
                node.last_heartbeat = ts
                node.buffered_events = data.get("buffered_events", node.buffered_events)
                node.model_version = data.get("model_version") or node.model_version
            else:
                # 自动注册新节点
                node = EdgeNode(
                    id=node_id,
                    ward_id=data.get("ward_id", "W-01"),
                    bed_id=data.get("bed_id"),
                    status=status,
                    last_heartbeat=ts,
                    buffered_events=data.get("buffered_events", 0),
                    model_version=data.get("model_version"),
                )
                db.add(node)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"健康状态更新失败: {e}")
        finally:
            db.close()

        self.latest_state.setdefault(node_id, {}).update({
            "status": status,
            "last_heartbeat": data.get("timestamp"),
            "buffered_events": data.get("buffered_events", 0),
        })

        if self.ws_manager:
            self.ws_manager.broadcast_sync({
                "type": "node_health",
                "node_id": node_id,
                "ward_id": data.get("ward_id"),
                "status": status,
                "timestamp": data.get("timestamp"),
            })

    def apply_ack(self, data: dict, envelope: dict = None):
        """处理告警确认：更新事件状态 + 处置记录 + 审计。

        两个调用来源：
          1. REST `/api/events/{id}/ack` 直接调用（envelope=None），保证前端不必等待
             MQTT 往返；
          2. `ward/+/alert/+/ack` 订阅回调。

        云端自己也订阅该主题，因此 publish_ack 发出的消息会回环到本进程。
        若不拦截，一次确认会写出两条 event_dispositions 与两条 audit_logs。
        这里按信封 source 识别自投递并跳过（真实外部来源的 ack 仍正常处理）。
        """
        event_id = data.get("event_id")
        action = data.get("action")
        if not event_id or not action:
            return

        if envelope and envelope.get("source") == "cloud":
            logger.debug(f"跳过云端自投递的 ack 回环: {event_id}")
            return

        db = SessionLocal()
        try:
            event = db.query(SafetyEvent).filter_by(event_id=event_id).first()
            if not event:
                logger.warning(f"确认的目标事件不存在: {event_id}")
                return

            now = utc_now()
            state_map = {
                "acknowledge": "acknowledged",
                "resolve": "resolved",
                "false_positive": "false_positive",
                "escalate": "escalated",
            }
            event.state = state_map.get(action, event.state)
            if action == "acknowledge":
                event.acknowledged_at = now
            elif action == "resolve":
                event.resolved_at = now

            # 处置记录
            op = data.get("operator", {})
            from .database import EventDisposition
            disp = EventDisposition(
                event_id=event_id,
                action=action,
                operator_id=op.get("id", "unknown"),
                operator_name=op.get("name"),
                operator_role=op.get("role"),
                result=data.get("result"),
                note=data.get("note"),
                occurred_at=now,
            )
            db.add(disp)

            # 审计
            audit = AuditLog(
                action="event_ack",
                target_type="safety_event",
                target_id=event_id,
                operator_id=op.get("id", "unknown"),
                detail=json.dumps({"action": action}, ensure_ascii=False),
                occurred_at=now,
            )
            db.add(audit)
            db.commit()
            logger.info(f"事件处置: {event_id} -> {action}")

        except Exception as e:
            db.rollback()
            logger.error(f"事件确认失败: {e}", exc_info=True)
        finally:
            db.close()

        if self.ws_manager:
            self.ws_manager.broadcast_sync({
                "type": "event_ack",
                "event_id": event_id,
                "action": action,
                "operator": data.get("operator"),
            })

    # 兼容别名：原私有名，保留给既有测试与订阅回调调用方
    _handle_ack = apply_ack

    # ─── 发布辅助（云端 -> 边缘）──

    def publish_ack(self, ward_id: str, event_id: str, ack_payload: dict):
        """发布告警确认指令到 ward/{ward_id}/alert/{event_id}/ack"""
        if not self.client.is_connected():
            return False
        topic = f"ward/{ward_id}/alert/{event_id}/ack"
        envelope = {
            "message_id": str(uuid.uuid4()),
            "event_id": event_id,
            "schema_version": "v1",
            "occurred_at": utc_now_iso(),
            "source": "cloud",
            "trace_id": str(uuid.uuid4()),
            "payload": ack_payload,
        }
        self.client.publish(topic, json.dumps(envelope, ensure_ascii=False), qos=1)
        return True

    def publish_model_deploy(self, node_id: str, deploy_payload: dict):
        """发布模型下发指令到 node/{node_id}/model/deploy"""
        if not self.client.is_connected():
            return False
        topic = f"node/{node_id}/model/deploy"
        envelope = {
            "message_id": str(uuid.uuid4()),
            "event_id": None,
            "schema_version": "v1",
            "occurred_at": utc_now_iso(),
            "source": "cloud",
            "trace_id": str(uuid.uuid4()),
            "payload": deploy_payload,
        }
        self.client.publish(topic, json.dumps(envelope, ensure_ascii=False), qos=1)
        return True

    def publish_env_control(self, node_id: str, control_payload: dict):
        """发布环境控制指令到 node/{node_id}/config/set

        用于环境自适应（夜间离床开夜灯）与空气质量联动（CO₂ 超阈值开新风）。
        """
        if not self.client.is_connected():
            return False
        topic = f"node/{node_id}/config/set"
        envelope = {
            "message_id": str(uuid.uuid4()),
            "event_id": None,
            "schema_version": "v1",
            "occurred_at": utc_now_iso(),
            "source": "cloud",
            "trace_id": str(uuid.uuid4()),
            "payload": control_payload,
        }
        self.client.publish(topic, json.dumps(envelope, ensure_ascii=False), qos=1)
        logger.info(f"环境控制下发: node={node_id} {control_payload.get('device')} -> {control_payload.get('action')}")
        return True

    def get_latest_state(self, node_id: str) -> dict:
        """获取节点最近状态"""
        return self.latest_state.get(node_id, {})

    # ─── 生命周期 ───

    def connect(self):
        try:
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"MQTT 连接失败: {e}")

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
