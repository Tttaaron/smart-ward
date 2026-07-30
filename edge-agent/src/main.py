"""智慧病房边缘代理主程序（云边协同增强版）

整合采集适配器、推理引擎、事件融合、轻量LLM决策、云边协同路由、
本地缓存和 MQTT 客户端，实现边缘自治 + 云边协同工作流：

正常模式（边缘自治 + LLM 增强）：
  采集适配器 -> 推理 -> 融合 -> LLM语义增强 -> 任务路由 -> 本地/云端 -> MQTT 上报

协同推理模式（云边协同）：
  低置信度事件 -> TaskRouter判定卸载 -> MQTT推理请求 -> 云端大模型研判 -> 结果回传

离线模式（边缘自治 + LLM 离线决策）：
  采集适配器 -> 推理 -> 融合 -> LLM离线决策 -> 本地缓存（标记未同步）

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
  LLM_MODE           LLM 模式 mock/real（默认 mock）
  LLM_MODEL_PATH     GGUF 模型路径（real 模式）
"""

import os
import time
import signal
import sys
import json
from datetime import datetime, timezone

from adapters.camera import CameraAdapter
from adapters.bed_sensor import BedSensorAdapter
from adapters.environment import EnvironmentAdapter
from inference import InferenceEngine
from fusion import FusionEngine
from database import LocalDatabase
from mqtt_client import MqttClient
from scenario import ScenarioDriver
from llm_advisor import LLMAdvisor
from task_router import TaskRouter, ComputeTarget


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
            EnvironmentAdapter(self.node_id, self.bed_id, self.scenario),
        ]

        # 推理引擎与融合引擎
        self.inference = InferenceEngine()
        self.fusion = FusionEngine(self.ward_id, self.node_id, self.bed_id)

        # ━━━ 云边协同增强组件 ━━━
        # LLM 智能决策顾问（轻量模型语义增强 + 护理建议 + 离线决策）
        self.llm_advisor = LLMAdvisor(self.node_id, self.bed_id, self.ward_id)
        # 云边协同任务路由器（动态决定边缘/云端处理）
        self.task_router = TaskRouter(self.node_id)

        # 本地数据库（容器内持久化路径）
        db_dir = "/app/data" if os.path.exists("/app/data") else "data"
        self.db = LocalDatabase(f"{db_dir}/edge_{self.node_id}.db")

        # MQTT 客户端
        self.mqtt = MqttClient(self.ward_id, self.node_id, self.broker, self.port)
        self.mqtt.set_ack_callback(self.handle_ack)
        self.mqtt.set_model_deploy_callback(self.handle_model_deploy)
        self.mqtt.set_config_callback(self.handle_config)
        self.mqtt.set_inference_response_callback(self.handle_inference_response)

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        print(f"[{self.node_id}] 边缘代理初始化完成 (ward={self.ward_id}, bed={self.bed_id})")
        print(f"[{self.node_id}] 场景配置: {self.scenario.scene_types or '无'}")
        print(f"[{self.node_id}] MQTT: {self.broker}:{self.port}")
        print(f"[{self.node_id}] LLM: mode={self.llm_advisor.engine.mode}, "
              f"model={self.llm_advisor.engine.MODEL_NAME}@{self.llm_advisor.engine.MODEL_VERSION}")
        print(f"[{self.node_id}] TaskRouter: threshold={self.task_router.edge_threshold}")

    def _signal_handler(self, signum, frame):
        print(f"\n[{self.node_id}] 收到停止信号，正在关闭...")
        self.running = False

    def handle_ack(self, envelope: dict) -> None:
        """处理云端下发的告警确认指令"""
        payload = envelope.get("payload", envelope)
        print(f"[{self.node_id}] 收到告警确认: event_id={payload.get('event_id')}, action={payload.get('action')}")

    def handle_model_deploy(self, envelope: dict, action: str = "deploy") -> None:
        """处理云端下发的模型部署/回滚指令

        对齐需求 §2.1.5 模型下发与灰度：
        - deploy：切换到新版本，失败自动回退到上一版本
        - rollback：回滚到上一稳定版本
        加载后立即上报 health，携带新 model_version，供云端 model_deployments 表更新状态。
        """
        payload = envelope.get("payload", envelope)
        model_name = payload.get("model_name")
        model_version = payload.get("model_version")

        if action == "rollback":
            ok = self.inference.rollback()
            print(f"[{self.node_id}] 模型回滚: {'成功' if ok else '失败（无上一版本）'} -> {self.inference.model_version}")
        else:
            # deploy：真实接入时此处应下载 artifact_url、校验 checksum
            ok = self.inference.load_model(model_name, model_version)
            print(f"[{self.node_id}] 模型部署: {model_name}@{model_version} {'成功' if ok else '失败已回退'}")

        # 立即上报 health，携带当前 model_version 与模型状态
        # 云端 _handle_health 会更新 edge_nodes.model_version，完成灰度发布闭环
        self._publish_health()

    def handle_config(self, envelope: dict) -> None:
        """处理云端下发的环境控制指令（node/{node_id}/config/set）

        用于环境自适应与空气质量联动：
        - 夜间离床开夜灯
        - CO₂ 超阈值开新风
        演示阶段仅打印日志，不真实控制空调/新风设备。
        """
        payload = envelope.get("payload", envelope)
        device = payload.get("device")   # ac/light/fresh_air
        action = payload.get("action")   # on/off
        reason = payload.get("reason", "")
        print(f"[{self.node_id}] 收到环境控制: {device} -> {action} (原因: {reason})")
        # TODO: 接入真实设备网关后，将指令转发到 GPIO/Modbus/MQTT 网关

    def handle_inference_response(self, envelope: dict) -> None:
        """处理云端大模型推理响应（协同推理闭环）

        云端对边缘卸载的事件进行二次研判后，通过此主题回传结果。
        边缘端根据云端结果更新事件状态或触发额外动作。
        """
        payload = envelope.get("payload", envelope)
        event_id = payload.get("event_id", "unknown")
        cloud_judgment = payload.get("judgment", "")  # confirm/reject/escalate
        cloud_confidence = payload.get("confidence", 0.0)
        cloud_advice = payload.get("advice", "")
        latency_ms = payload.get("latency_ms", 0)

        # 记录云端结果到路由器（用于动态调整策略）
        self.task_router.record_cloud_result(event_id, success=True, latency_ms=latency_ms)

        print(f"[{self.node_id}] 云端研判结果: event={event_id}, "
              f"judgment={cloud_judgment}, conf={cloud_confidence:.2f}")
        if cloud_advice:
            print(f"[{self.node_id}] 云端建议: {cloud_advice}")

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

    def _publish_events(self, events: list, observations: list = None) -> None:
        """发布融合引擎产出的安全事件（含 LLM 增强 + 协同路由）

        新增流程：
          1. 对每个事件调用 LLM 语义增强（补充描述+建议）
          2. TaskRouter 决定边缘/云端/混合处理
          3. 需要云端处理的事件发送推理请求
          4. 检测多事件冲突
        """
        obs_dicts = [o.to_dict() for o in observations] if observations else []

        for event in events:
            event_dict = event.to_dict()

            # ━━ Step 1: LLM 语义增强 ━━
            enhancement = self.llm_advisor.enhance_event(event_dict, obs_dicts)
            if enhancement.enhanced:
                event_dict["details"]["llm_summary"] = enhancement.summary
                event_dict["details"]["llm_advice"] = enhancement.advice
                event_dict["details"]["llm_ttft_ms"] = round(
                    enhancement.llm_response.ttft_ms, 1) if enhancement.llm_response else 0

            # ━━ Step 2: 冲突检测 ━━
            conflict = self.task_router.detect_conflict(event_dict)
            if conflict:
                event_dict["details"]["conflict"] = conflict
                print(f"[{self.node_id}] ⚠️ 决策冲突: {conflict['event_a']} vs {conflict['event_b']}")

            # ━━ Step 3: 任务路由 ━━
            routing = self.task_router.route(event_dict)
            event_dict["details"]["routing"] = routing.to_dict()

            if routing.target == ComputeTarget.CLOUD and self.mqtt.connected:
                # 卸载到云端大模型
                self.mqtt.publish_inference_request({
                    "event_id": event_dict["event_id"],
                    "event_type": event_dict["event_type"],
                    "confidence": event_dict["confidence"],
                    "priority": event_dict["priority"],
                    "bed_id": self.bed_id,
                    "node_id": self.node_id,
                    "reason": routing.reason,
                    "observations_summary": obs_dicts[:2],  # 只发摘要
                })
                print(f"[{self.node_id}] ☁️ 卸载云端: {event.event_type} ({routing.reason})")
            elif routing.target == ComputeTarget.HYBRID and self.mqtt.connected:
                # 混合模式：边缘先响应，同时请求云端复核
                self.mqtt.publish_inference_request({
                    "event_id": event_dict["event_id"],
                    "event_type": event_dict["event_type"],
                    "confidence": event_dict["confidence"],
                    "priority": event_dict["priority"],
                    "bed_id": self.bed_id,
                    "node_id": self.node_id,
                    "reason": routing.reason,
                    "mode": "review",  # 复核模式
                })

            # ━━ Step 4: 保存 + 上报 ━━
            synced = self.mqtt.connected
            self.db.save_event(event_dict, synced=synced)
            if synced:
                self.mqtt.publish_event(event_dict)
                route_tag = {"edge": "🟢", "cloud": "☁️", "hybrid": "🔀"}.get(
                    routing.target.value, "")
                print(f"[{self.node_id}] {route_tag} 上报事件: {event.event_type} "
                      f"[{event.priority}] conf={event.confidence:.2f} "
                      f"route={routing.target.value} "
                      f"ttft={enhancement.llm_response.ttft_ms:.0f}ms" if enhancement.llm_response else "")
            else:
                print(f"[{self.node_id}] 离线缓存事件: {event.event_type} (待补传)")

    def _publish_health(self) -> None:
        """发布节点健康心跳（含 LLM 与路由器状态）"""
        buffered = self.db.get_buffered_event_count()
        health = {
            "node_id": self.node_id,
            "ward_id": self.ward_id,
            "status": "online" if self.mqtt.connected else "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "metrics": {
                "buffered_events": buffered,
            },
            "model_name": self.inference.model_name,
            "model_version": self.inference.model_version,
            "model_status": self.inference.model_status,  # ok/degraded/loading
            "buffered_events": buffered,
            # ━━ 云边协同增强指标 ━━
            "llm": self.llm_advisor.get_status(),
            "task_router": self.task_router.get_status(),
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
        """主运行循环（云边协同增强版）"""
        print(f"[{self.node_id}] 边缘代理启动运行（tick={self.tick_seconds}s）")
        print(f"[{self.node_id}] 工作流: 采集->推理->融合->LLM增强->任务路由->上报")
        self.mqtt.connect()
        time.sleep(2)

        cycle = 0
        while self.running:
            try:
                # 1. 推进场景状态机
                self.scenario.tick()

                # 2. 更新网络状态（TaskRouter 感知）
                self.task_router.update_network_state(self.mqtt.connected)

                # 3. 采集观测（自动保存+上报）
                observations = self._collect_observations()

                # 4. 摄像头推理
                cam_obs = next((o for o in observations if o.source_type == "camera"), None)
                inference_result = self.inference.run(cam_obs)

                # 5. 事件融合
                events = self.fusion.fuse(observations, inference_result)

                # 6. 发布事件（LLM增强 + 任务路由 + 保存 + 上报）
                self._publish_events(events, observations)

                # 7. 离线时调用 LLM 离线决策
                if not self.mqtt.connected and events:
                    pending = self.db.get_unsynced_events(limit=5)
                    if pending:
                        pending_dicts = [json.loads(p[1]) for p in pending]
                        decision = self.llm_advisor.offline_decision(pending_dicts)
                        if decision.emergency_actions:
                            print(f"[{self.node_id}] 🚨 离线应急: {decision.emergency_actions}")

                # 8. 每 10 周期发布一次健康心跳
                cycle += 1
                if cycle % 10 == 0:
                    self._publish_health()

                # 9. 同步离线缓存
                self.sync_offline_data()

                # 10. 定期清理旧观测数据
                if cycle % 100 == 0:
                    self.db.cleanup_old_data(keep_count=1000)

                # 状态摘要（含路由与 LLM 信息）
                active_scene = self.scenario._active_scene()
                scene_str = f"[scene:{active_scene.scene_type}/{active_scene.phase}]" if active_scene else "[scene:idle]"
                mqtt_str = "[MQTT OK]" if self.mqtt.connected else "[MQTT OFF]"
                event_str = f"+{len(events)}event" if events else ""
                llm_str = f"[LLM:{self.llm_advisor.engine.mode}]"
                conflict_ratio = self.task_router.get_conflict_ratio()
                conflict_str = f"[conflict:{conflict_ratio:.1%}]" if conflict_ratio > 0 else ""
                print(f"[{self.node_id}] {scene_str} {mqtt_str} {llm_str} "
                      f"bed={self.bed_id} {event_str} {conflict_str}")

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
