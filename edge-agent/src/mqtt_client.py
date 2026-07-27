"""MQTT 客户端通信模块（病房版）

负责边缘节点与云端之间的 MQTT 通信，主题树对齐方案书 §4.3 与 contracts/。

上行主题：
- ward/{ward_id}/node/{node_id}/observation   多源观测
- ward/{ward_id}/node/{node_id}/event         安全事件
- ward/{ward_id}/node/{node_id}/health        节点健康

下行主题（订阅）：
- ward/{ward_id}/alert/+/ack                  告警确认指令
- node/{node_id}/config/set                   节点配置
- node/{node_id}/model/deploy                 模型下发
- node/{node_id}/model/rollback               模型回滚

所有消息外层符合 envelope.json 信封结构。
"""

import json
import time
import threading
import os
from uuid import uuid4
from datetime import datetime, timezone
import paho.mqtt.client as mqtt


def _envelope(source: str, payload: dict, event_id: str = None) -> dict:
    """构造通用消息信封"""
    return {
        "message_id": str(uuid4()),
        "event_id": event_id,
        "schema_version": "v1",
        "occurred_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": source,
        "trace_id": str(uuid4()),
        "payload": payload,
    }


class MqttClient:
    """MQTT 客户端（病房主题树）"""

    def __init__(self, ward_id: str, node_id: str, broker: str, port: int = 1883):
        self.ward_id = ward_id
        self.node_id = node_id
        self.broker = broker
        self.port = port
        self.connected = False
        self.client = mqtt.Client(client_id=f"edge-{node_id}")
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        # 下行指令回调（由 main.py 注册）
        self.ack_callback = None
        self.config_callback = None
        self.model_deploy_callback = None

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            print(f"[{self.node_id}] MQTT 连接成功 (broker={self.broker}:{self.port})")
            # 订阅下行主题
            topics = [
                (f"ward/{self.ward_id}/alert/+/ack", 1),
                (f"node/{self.node_id}/config/set", 1),
                (f"node/{self.node_id}/model/deploy", 1),
                (f"node/{self.node_id}/model/rollback", 1),
            ]
            for topic, qos in topics:
                client.subscribe(topic, qos=qos)
                print(f"[{self.node_id}] 订阅主题: {topic}")
            self.publish_online()
        else:
            print(f"[{self.node_id}] MQTT 连接失败, 返回码: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        if rc != 0:
            print(f"[{self.node_id}] MQTT 意外断开 (rc={rc})")
        else:
            print(f"[{self.node_id}] MQTT 正常断开")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            topic_parts = msg.topic.split("/")
            print(f"[{self.node_id}] 收到消息: topic={msg.topic}")

            # ward/{ward_id}/alert/{event_id}/ack
            if len(topic_parts) == 5 and topic_parts[0] == "ward" and topic_parts[3] == "alert" and topic_parts[4] == "ack":
                if self.ack_callback:
                    self.ack_callback(payload)
            # node/{node_id}/config/set
            elif len(topic_parts) == 3 and topic_parts[0] == "node" and topic_parts[2] == "config":
                if self.config_callback:
                    self.config_callback(payload)
            # node/{node_id}/model/deploy  或  node/{node_id}/model/rollback
            # 主题结构：["node", "{node_id}", "model", "deploy"|"rollback"]，共 4 段
            elif (len(topic_parts) == 4 and topic_parts[0] == "node"
                  and topic_parts[2] == "model" and topic_parts[3] in ("deploy", "rollback")):
                action = topic_parts[3]  # "deploy" 或 "rollback"
                if self.model_deploy_callback:
                    self.model_deploy_callback(payload, action=action)
        except Exception as e:
            print(f"[{self.node_id}] 解析消息失败: {e}")

    def connect(self) -> None:
        def _connect_loop():
            while not self.connected:
                try:
                    self.client.connect(self.broker, self.port, keepalive=60)
                    self.client.loop_start()
                    break
                except Exception as e:
                    print(f"[{self.node_id}] MQTT 连接失败，5秒后重试: {e}")
                    time.sleep(5)
        threading.Thread(target=_connect_loop, daemon=True).start()

    def _publish(self, topic: str, payload: dict, source: str = None) -> bool:
        """发布带信封的消息"""
        if not self.connected:
            return False
        src = source or f"edge:{self.node_id}"
        envelope = _envelope(src, payload)
        self.client.publish(topic, json.dumps(envelope, ensure_ascii=False), qos=1)
        return True

    def publish_observation(self, obs_payload: dict) -> bool:
        """发布观测数据到 ward/{ward_id}/node/{node_id}/observation"""
        topic = f"ward/{self.ward_id}/node/{self.node_id}/observation"
        return self._publish(topic, obs_payload)

    def publish_event(self, event_payload: dict) -> bool:
        """发布安全事件到 ward/{ward_id}/node/{node_id}/event"""
        topic = f"ward/{self.ward_id}/node/{self.node_id}/event"
        return self._publish(topic, event_payload, source=f"edge:{self.node_id}")

    def publish_health(self, health_payload: dict) -> bool:
        """发布健康心跳到 ward/{ward_id}/node/{node_id}/health"""
        topic = f"ward/{self.ward_id}/node/{self.node_id}/health"
        return self._publish(topic, health_payload)

    def publish_online(self) -> None:
        """节点上线通知"""
        topic = f"ward/{self.ward_id}/node/{self.node_id}/health"
        self._publish(topic, {
            "node_id": self.node_id,
            "ward_id": self.ward_id,
            "status": "online",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        })

    def publish_offline(self) -> None:
        topic = f"ward/{self.ward_id}/node/{self.node_id}/health"
        self._publish(topic, {
            "node_id": self.node_id,
            "ward_id": self.ward_id,
            "status": "offline",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        })

    def set_ack_callback(self, callback) -> None:
        self.ack_callback = callback

    def set_config_callback(self, callback) -> None:
        self.config_callback = callback

    def set_model_deploy_callback(self, callback) -> None:
        self.model_deploy_callback = callback

    def disconnect(self) -> None:
        self.publish_offline()
        self.client.loop_stop()
        self.client.disconnect()
        print(f"[{self.node_id}] MQTT 已断开连接")
