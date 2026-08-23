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
import threading
from uuid import uuid4
from datetime import datetime, timezone

from adapters.camera import CameraAdapter
from adapters.yolo_camera import YoloCameraAdapter
from adapters.bed_sensor import BedSensorAdapter
from adapters.environment import EnvironmentAdapter
from inference import InferenceEngine
from fusion import FusionEngine
from database import LocalDatabase
from mqtt_client import MqttClient
from scenario import ScenarioDriver
from llm_advisor import LLMAdvisor
from task_router import TaskRouter, ComputeTarget
from inference_tracker import InferenceTracker, PendingInference


class EdgeAgent:
    """智慧病房边缘代理主程序"""

    def __init__(self):
        self.ward_id = os.getenv("WARD_ID", "W-01")
        self.bed_id = os.getenv("BED_ID", "B01")
        self.node_id = os.getenv("EDGE_NODE_ID", f"EDGE-{self.ward_id}-{self.bed_id}")
        self.broker = os.getenv("MQTT_BROKER", "localhost")
        self.port = int(os.getenv("MQTT_PORT", "1883"))
        self.tick_seconds = float(os.getenv("TICK_SECONDS", "3"))
        self.running = True

        # 云端超时独立定时机制（不依赖主循环 tick，主循环阻塞时仍能及时回退）
        self._cloud_timeout_check_interval = float(
            os.getenv("CLOUD_TIMEOUT_CHECK_INTERVAL", "0.2"))
        self._cloud_response_grace_s = max(
            0.0, float(os.getenv("CLOUD_RESPONSE_GRACE_S", "1.0")))
        self._cloud_timeout_stop = threading.Event()
        self._cloud_timeout_thread = None

        # 场景驱动器（注入到各适配器）
        self.scenario = ScenarioDriver()

        # 采集适配器。默认仍使用场景模拟器；真实摄像头通过 CAMERA_MODE=yolo 显式启用。
        camera_mode = os.getenv("CAMERA_MODE", "mock").lower()
        if camera_mode in {"yolo", "real"}:
            self.camera_adapter = YoloCameraAdapter(
                self.node_id,
                self.bed_id,
                model_path=os.getenv("YOLO_MODEL_PATH", "/app/models/yolo11n-pose.pt"),
                source=os.getenv("CAMERA_SOURCE", "0"),
                confidence_threshold=float(os.getenv("YOLO_CONFIDENCE", "0.35")),
                device=os.getenv("YOLO_DEVICE") or None,
                tracker_iou=float(os.getenv("YOLO_TRACKER_IOU", "0.3")),
                tracker_max_missed=int(os.getenv("YOLO_TRACKER_MAX_MISSED", "8")),
                history_size=int(os.getenv("BEHAVIOR_HISTORY_SIZE", "24")),
                save_evidence=os.getenv("YOLO_SAVE_EVIDENCE", "false").lower() in {"1", "true", "yes"},
                evidence_dir=os.getenv("EVIDENCE_DIR", "/app/evidence"),
            )
        else:
            self.camera_adapter = CameraAdapter(self.node_id, self.bed_id, self.scenario)

        self.adapters = [
            self.camera_adapter,
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
        self.inference_tracker = InferenceTracker()

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
        print(f"[{self.node_id}] Camera: mode={camera_mode}")
        print(f"[{self.node_id}] LLM: mode={self.llm_advisor.engine.mode}, "
              f"model={self.llm_advisor.engine.MODEL_NAME}@{self.llm_advisor.engine.MODEL_VERSION}")
        print(f"[{self.node_id}] TaskRouter: threshold={self.task_router.edge_threshold}")

    def _signal_handler(self, signum, frame):
        print(f"\n[{self.node_id}] 收到停止信号，正在关闭...")
        self.running = False

    def handle_ack(self, envelope: dict) -> None:
        """处理云端下发的告警确认指令

        同时把当前恢复中的场景推进到人工确认(confirmed)阶段，
        完成 scenario 四阶段生命周期：开始 -> 持续 -> 恢复 -> 人工确认。
        """
        payload = envelope.get("payload", envelope)
        print(f"[{self.node_id}] 收到告警确认: event_id={payload.get('event_id')}, action={payload.get('action')}")
        if self.scenario.confirm():
            print(f"[{self.node_id}] 场景已人工确认，等待复位")

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
        event_id = payload.get("event_id") or envelope.get("event_id")
        trace_id = payload.get("trace_id") or envelope.get("trace_id")
        if not event_id:
            print(f"[{self.node_id}] 云端响应缺少 event_id，已忽略")
            return

        # 云端超时响应（status=timeout）：优先于 pending 状态检查，
        # 无论边端是否已本地超时，都识别云端超时信号并保持边缘判断
        if str(payload.get("status", "")).lower() == "timeout":
            print(f"[{self.node_id}] 识别云端推理超时: event={event_id}, "
                  f"trace={trace_id}, timeout_ms={payload.get('timeout_ms', '?')}, "
                  f"保留边缘原始判断")
            resolution = self.inference_tracker.resolve(event_id, trace_id)
            if resolution.status == "completed":
                self.task_router.record_cloud_result(
                    event_id, success=False,
                    latency_ms=float(payload.get("latency_ms") or 0))
                self._apply_cloud_failure(resolution.request, "timeout")
            else:
                print(f"[{self.node_id}] 本地已按超时回退，与云端信号一致 "
                      f"(pending={resolution.status})")
            return

        resolution = self.inference_tracker.resolve(event_id, trace_id)
        if resolution.status != "completed":
            print(f"[{self.node_id}] 忽略云端响应: event={event_id}, "
                  f"status={resolution.status}")
            return

        request = resolution.request
        judgment = str(payload.get("judgment", "")).lower()
        valid_judgments = {"confirm", "reject", "escalate"}
        latency_ms = float(payload.get("latency_ms") or 0)
        if latency_ms <= 0 and request:
            latency_ms = (time.monotonic() - request.sent_at) * 1000

        if judgment not in valid_judgments:
            self.task_router.record_cloud_result(event_id, success=False, latency_ms=latency_ms)
            self._apply_cloud_failure(request, "invalid_judgment")
            return

        if payload.get("status") == "timeout":
            self.task_router.record_cloud_result(event_id, success=False, latency_ms=latency_ms)
            event_payload = dict(request.event_payload)
            details = dict(event_payload.get("details") or {})
            details["cloud_inference"] = {
                "status": "timeout",
                "reason": "cloud_timeout",
                "mode": request.mode,
                "judgment": judgment,
                "confidence": float(payload.get("confidence") or 0),
                "advice": payload.get("advice", ""),
                "latency_ms": round(latency_ms, 1),
                "trace_id": trace_id,
                "received_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            event_payload["details"] = details
            self._persist_cloud_update(event_payload)
            print(f"[{self.node_id}] 云端超时，保留边缘结果: event={event_id}")
            return

        self.task_router.record_cloud_result(event_id, success=True, latency_ms=latency_ms)
        event_payload = dict(request.event_payload)
        event_payload["state"] = {
            "confirm": "notified",
            "reject": "false_positive",
            "escalate": "escalated",
        }[judgment]
        details = dict(event_payload.get("details") or {})
        details["cloud_inference"] = {
            "status": "completed",
            "judgment": judgment,
            "confidence": float(payload.get("confidence") or 0),
            "advice": payload.get("advice", ""),
            "latency_ms": round(latency_ms, 1),
            "trace_id": trace_id,
            "received_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        event_payload["details"] = details
        self._persist_cloud_update(event_payload)

        print(f"[{self.node_id}] 云端研判结果: event={event_id}, "
              f"judgment={judgment}, conf={float(payload.get('confidence') or 0):.2f}")
        if payload.get("advice"):
            print(f"[{self.node_id}] 云端建议: {payload['advice']}")

    def _persist_cloud_update(self, event_payload: dict) -> None:
        """保存云端结果并尽力上报更新后的事件。"""
        published = self.mqtt.publish_event(event_payload) if self.mqtt.connected else False
        if not self.db.update_event(event_payload, synced=published):
            self.db.save_event(event_payload, synced=published)

    def _apply_cloud_failure(self, request: PendingInference, reason: str) -> None:
        """云端失败时记录原因，继续使用已生成的边缘结果。"""
        if not request:
            return
        event_payload = dict(request.event_payload)
        details = dict(event_payload.get("details") or {})
        details["cloud_inference"] = {
            "status": "fallback_edge",
            "reason": reason,
            "mode": request.mode,
            "trace_id": request.trace_id,
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        event_payload["details"] = details
        self._persist_cloud_update(event_payload)
        print(f"[{self.node_id}] 云端不可用，回退边缘: event={request.event_id}, reason={reason}")

    def _send_cloud_inference(self, request_payload: dict, target: ComputeTarget,
                              mode: str, event_payload: dict = None) -> None:
        """登记 pending 后发送请求，发送失败立即回退边缘。"""
        event_id = request_payload["event_id"]
        trace_id = str(uuid4())
        request_payload = dict(request_payload)
        request_payload.update({
            "trace_id": trace_id,
            "request_mode": mode,
            "timeout_ms": round(self.task_router.cloud_timeout_s * 1000),
            "requested_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        })
        pending = self.inference_tracker.register(
            event_id=event_id,
            trace_id=trace_id,
            target=target.value,
            mode=mode,
            event_payload=event_payload or request_payload,
            # Leave a small transport window for a cloud timeout response.
            timeout_s=self.task_router.cloud_timeout_s + self._cloud_response_grace_s,
        )
        if pending is None:
            print(f"[{self.node_id}] 跳过重复云端请求: event={event_id}")
            return

        if not self.mqtt.publish_inference_request(request_payload, trace_id=trace_id):
            self.inference_tracker.cancel(event_id, trace_id)
            self.task_router.record_cloud_result(event_id, success=False, latency_ms=0)
            self._apply_cloud_failure(pending, "publish_failed")

    def _expire_cloud_inferences(self) -> None:
        """定期清理超时请求并触发边缘兜底。"""
        for request in self.inference_tracker.expire():
            self.task_router.record_cloud_result(request.event_id, success=False, latency_ms=0)
            self._apply_cloud_failure(request, "timeout")

    def _start_cloud_timeout_worker(self) -> None:
        """启动独立守护线程，按固定间隔检查云端请求超时。

        与主循环 tick 解耦：CLOUD_TIMEOUT_CHECK_INTERVAL 默认 0.2s，
        即使主循环被 YOLO/LLM 推理阻塞，超时回退仍能及时触发，
        且不阻塞后续事件处理。
        """
        self._cloud_timeout_stop.clear()
        self._cloud_timeout_thread = threading.Thread(
            target=self._cloud_timeout_worker,
            name="cloud-timeout",
            daemon=True,
        )
        self._cloud_timeout_thread.start()

    def _cloud_timeout_worker(self) -> None:
        while not self._cloud_timeout_stop.wait(self._cloud_timeout_check_interval):
            try:
                self._expire_cloud_inferences()
            except Exception as exc:
                print(f"[{self.node_id}] 云端超时检查异常: {exc}")

    @staticmethod
    def _compact_behavior(behavior: dict) -> dict:
        """Keep LLM/cloud context small while retaining behavior evidence."""
        if not isinstance(behavior, dict):
            return {}
        keys = (
            "track_id", "action", "posture", "posture_sequence",
            "position_duration", "fall_score", "tremor_score", "motion",
        )
        return {key: behavior[key] for key in keys if key in behavior}

    @classmethod
    def _compact_observations(cls, observations: list) -> list:
        compact = []
        for observation in observations:
            source_type = observation.get("source_type", "")
            data = observation.get("data", {}) or {}
            if source_type == "camera":
                compact_data = {
                    key: data.get(key)
                    for key in ("presence", "person_count", "posture", "fall_score", "tremor_score", "position_duration", "track_id")
                    if key in data
                }
                if data.get("behavior"):
                    compact_data["behavior"] = cls._compact_behavior(data["behavior"])
            elif source_type == "bed_sensor":
                compact_data = {
                    key: data.get(key)
                    for key in ("occupied", "bed_state", "absence_seconds")
                    if key in data
                }
            else:
                compact_data = {
                    key: data.get(key)
                    for key in ("temperature", "humidity", "co2", "light", "door_open")
                    if key in data
                }
            compact.append({
                "source_type": source_type,
                "data": compact_data,
                "quality": observation.get("quality", {}),
                "timestamp": observation.get("timestamp", ""),
            })
        return compact

    @classmethod
    def _compact_event_details(cls, details: dict) -> dict:
        if not isinstance(details, dict):
            return {}
        compact = {key: value for key, value in details.items() if key != "behavior"}
        if details.get("behavior"):
            compact["behavior"] = cls._compact_behavior(details["behavior"])
        return compact

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
        compact_obs_dicts = self._compact_observations(obs_dicts)

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

            cloud_request = None
            cloud_mode = ""
            if routing.target == ComputeTarget.CLOUD and self.mqtt.connected:
                # 先构造请求，事件落库后再实际发送，避免响应竞态。
                cloud_request = {
                    "event_id": event_dict["event_id"],
                    "event_type": event_dict["event_type"],
                    "confidence": event_dict["confidence"],
                    "priority": event_dict["priority"],
                    "bed_id": self.bed_id,
                    "node_id": self.node_id,
                    "reason": routing.reason,
                    "observations_summary": compact_obs_dicts[:2],
                    "event_details": self._compact_event_details(event_dict.get("details", {})),
                    "evidence_refs": event_dict.get("evidence_refs", []),
                }
                cloud_mode = "cloud"
                print(f"[{self.node_id}] ☁️ 卸载云端: {event.event_type} ({routing.reason})")
            elif routing.target == ComputeTarget.HYBRID and self.mqtt.connected:
                # 混合模式：边缘先响应，同时请求云端复核
                cloud_request = {
                    "event_id": event_dict["event_id"],
                    "event_type": event_dict["event_type"],
                    "confidence": event_dict["confidence"],
                    "priority": event_dict["priority"],
                    "bed_id": self.bed_id,
                    "node_id": self.node_id,
                    "reason": routing.reason,
                    "mode": "hybrid",  # 对齐 inference_request 契约的 request_mode 枚举
                    "event_details": self._compact_event_details(event_dict.get("details", {})),
                    "evidence_refs": event_dict.get("evidence_refs", []),
                }
                cloud_mode = "hybrid"

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

            if cloud_request:
                self._send_cloud_inference(
                    cloud_request, routing.target, cloud_mode, event_payload=event_dict)

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
            "cloud_inference": self.inference_tracker.get_status(),
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
        self._start_cloud_timeout_worker()

        cycle = 0
        while self.running:
            try:
                # 1. 推进场景状态机
                self.scenario.tick()

                # 2. 更新网络状态（TaskRouter 感知）
                self.task_router.update_network_state(self.mqtt.connected)
                self._expire_cloud_inferences()

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
        self._cloud_timeout_stop.set()
        if self._cloud_timeout_thread and self._cloud_timeout_thread.is_alive():
            self._cloud_timeout_thread.join(timeout=2.0)
        close = getattr(self.camera_adapter, "close", None)
        if close:
            close()
        self.mqtt.disconnect()
        print(f"[{self.node_id}] 边缘代理已停止")


if __name__ == "__main__":
    node = EdgeAgent()
    node.run()
    sys.exit(0)
