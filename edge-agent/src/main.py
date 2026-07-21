"""智慧病房边缘代理主程序

整合采集适配器、推理引擎、事件融合、本地缓存和 MQTT 客户端，
实现边缘自治工作流：

正常模式：
  采集适配器 -> 推理 -> 融合 -> 本地缓存 -> MQTT 上报云端

离线模式：
  采集适配器 -> 推理 -> 融合 -> 本地缓存（标记未同步）

恢复模式：
  检测连接 -> 读取未同步事件 -> 批量补传 -> 标记已同步

环境变量（docker-compose 已配置）：
  WARD_ID            病区 ID（如 W-01）
  BED_ID             床位 ID（如 B01）
  EDGE_NODE_ID       边缘节点 ID（如 EDGE-W01-B01）
  MQTT_BROKER        MQTT 服务器地址
  MQTT_PORT          MQTT 服务器端口（默认 1883）
  TICK_SECONDS       采集周期秒数（默认 3）
  SCENARIO_PROFILE   场景脚本（逗号分隔，如 fall,nurse_call）
  EVENT_DEDUPE_SECONDS 同类事件去重秒数（默认 30）
"""

import os
import time
import signal
import sys
import json
from datetime import datetime, timezone

from adapters.camera import CameraAdapter
from adapters.bed_sensor import BedSensorAdapter
from adapters.infusion import InfusionAdapter
from adapters.environment import EnvironmentAdapter
from inference import InferenceEngine
from fusion import FusionEngine
from database import LocalDatabase
from mqtt_client import MqttClient
from scenario import ScenarioDriver


class EdgeAgent:
    """智慧病房边缘代理主程序"""

    def __init__(self):
        self.ward_id = os.getenv("WARD_ID", "W-01")
        self.bed_id = os.getenv("BED_ID", "B01")
        self.node_id = os.getenv("EDGE_NODE_ID", f"EDGE-{self.ward_id}-{self.bed_id}")
        self.broker = os.getenv("MQTT_BROKER", "localhost")
        self.port = int(os.getenv("MQTT_PORT", "1883"))
        self.tick_seconds = int(os.getenv("TICK_SECONDS", "3"))
        self.running = True

        # 场景驱动器（注入到各适配器）
        self.scenario = ScenarioDriver()

        # 采集适配器
        self.adapters = [
            CameraAdapter(self.node_id, self.bed_id, self.scenario),
            BedSensorAdapter(self.node_id, self.bed_id, self.scenario),
            InfusionAdapter(self.node_id, self.bed_id, self.scenario),
            EnvironmentAdapter(self.node_id, self.bed_id, self.scenario),
        ]

        # 推理引擎与融合引擎
        self.inference = InferenceEngine()
        self.fusion = FusionEngine(self.ward_id, self.node_id, self.bed_id)

        # 本地数据库（容器内持久化路径）
        db_dir = "/app/data" if os.path.exists("/app/data") else "data"
        self.db = LocalDatabase(f"{db_dir}/edge_{self.node_id}.db")

        # MQTT 客户端
        self.mqtt = MqttClient(self.ward_id, self.node_id, self.broker, self.port)
        self.mqtt.set_ack_callback(self.handle_ack)
        self.mqtt.set_model_deploy_callback(self.handle_model_deploy)

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        print(f"[{self.node_id}] 边缘代理初始化完成 (ward={self.ward_id}, bed={self.bed_id})")
        print(f"[{self.node_id}] 场景配置: {self.scenario.scene_types or '无'}")
        print(f"[{self.node_id}] MQTT: {self.broker}:{self.port}")

    def _signal_handler(self, signum, frame):
        print(f"\n[{self.node_id}] 收到停止信号，正在关闭...")
        self.running = False

    def handle_ack(self, envelope: dict) -> None:
        """处理云端下发的告警确认指令"""
        payload = envelope.get("payload", envelope)
        print(f"[{self.node_id}] 收到告警确认: event_id={payload.get('event_id')}, action={payload.get('action')}")

    def handle_model_deploy(self, envelope: dict, action: str = "deploy") -> None:
        """处理云端下发的模型部署/回滚指令"""
        payload = envelope.get("payload", envelope)
        print(f"[{self.node_id}] 收到模型{action}: {payload.get('model_name')}@{payload.get('model_version')}")
        # TODO: 下载模型制品、校验 checksum、加载到 InferenceEngine

    def _collect_observations(self) -> list:
        """采集所有适配器的观测数据"""
        obs_list = []
        for adapter in self.adapters:
            obs = adapter.read()
            obs_list.append(obs)
            # 保存到本地数据库
            obs_dict = {
                "ward_id": self.ward_id,
                "node_id": self.node_id,
                "bed_id": self.bed_id,
                "source_type": obs.source_type,
                "data": obs.data,
                "quality": obs.quality.to_dict(),
                "timestamp": obs.timestamp,
            }
            synced = self.mqtt.connected
            self.db.save_observation(obs_dict, synced=synced)
            # 在线时实时上报观测
            if synced:
                self.mqtt.publish_observation({
                    "ward_id": self.ward_id,
                    "node_id": self.node_id,
                    "bed_id": self.bed_id,
                    "timestamp": obs.timestamp,
                    "sources": [{
                        "source_type": obs.source_type,
                        "data": obs.data,
                        "quality": obs.quality.to_dict(),
                    }],
                })
        return obs_list

    def _publish_events(self, events: list) -> None:
        """发布融合引擎产出的安全事件"""
        for event in events:
            event_dict = event.to_dict()
            synced = self.mqtt.connected
            self.db.save_event(event_dict, synced=synced)
            if synced:
                self.mqtt.publish_event(event_dict)
                print(f"[{self.node_id}] 上报事件: {event.event_type} [{event.priority}] conf={event.confidence:.2f}")
            else:
                print(f"[{self.node_id}] 离线缓存事件: {event.event_type} (待补传)")

    def _publish_health(self) -> None:
        """发布节点健康心跳"""
        health = {
            "node_id": self.node_id,
            "ward_id": self.ward_id,
            "status": "online" if self.mqtt.connected else "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "metrics": {
                "buffered_events": self.db.get_buffered_event_count(),
            },
            "model_version": self.inference.model_version,
            "buffered_events": self.db.get_buffered_event_count(),
        }
        self.db.save_health(health, synced=self.mqtt.connected)
        if self.mqtt.connected:
            self.mqtt.publish_health(health)

    def sync_offline_data(self) -> None:
        """同步离线缓存的安全事件到云端"""
        if not self.mqtt.connected:
            return
        rows = self.db.get_unsynced_events(limit=50)
        if not rows:
            return
        synced_ids = []
        for row_id, payload_json in rows:
            event_dict = json.loads(payload_json)
            if self.mqtt.publish_event(event_dict):
                synced_ids.append(row_id)
        self.db.mark_events_synced(synced_ids)
        if synced_ids:
            print(f"[{self.node_id}] 补传 {len(synced_ids)} 条离线事件")

    def run(self) -> None:
        """主运行循环"""
        print(f"[{self.node_id}] 边缘代理启动运行（tick={self.tick_seconds}s）")
        self.mqtt.connect()
        time.sleep(2)

        cycle = 0
        while self.running:
            try:
                # 1. 推进场景状态机
                self.scenario.tick()

                # 2. 采集观测（自动保存+上报）
                observations = self._collect_observations()

                # 3. 摄像头推理
                cam_obs = next((o for o in observations if o.source_type == "camera"), None)
                inference_result = self.inference.run(cam_obs)

                # 4. 事件融合
                events = self.fusion.fuse(observations, inference_result)

                # 5. 发布事件（保存+上报）
                self._publish_events(events)

                # 6. 每 10 周期发布一次健康心跳
                cycle += 1
                if cycle % 10 == 0:
                    self._publish_health()

                # 7. 同步离线缓存
                self.sync_offline_data()

                # 8. 定期清理旧观测数据
                if cycle % 100 == 0:
                    self.db.cleanup_old_data(keep_count=1000)

                # 状态摘要
                active_scene = self.scenario._active_scene()
                scene_str = f"[scene:{active_scene.scene_type}/{active_scene.phase}]" if active_scene else "[scene:idle]"
                mqtt_str = "[MQTT OK]" if self.mqtt.connected else "[MQTT OFF]"
                event_str = f"+{len(events)}event" if events else ""
                print(f"[{self.node_id}] {scene_str} {mqtt_str} bed={self.bed_id} {event_str}")

                time.sleep(self.tick_seconds)

            except KeyboardInterrupt:
                break
            except Exception as e:
                import traceback
                print(f"[{self.node_id}] 运行异常: {e}")
                traceback.print_exc()
                time.sleep(self.tick_seconds)

        self._cleanup()

    def _cleanup(self) -> None:
        print(f"[{self.node_id}] 正在清理资源...")
        self.mqtt.disconnect()
        print(f"[{self.node_id}] 边缘代理已停止")


if __name__ == "__main__":
    node = EdgeAgent()
    node.run()
    sys.exit(0)
