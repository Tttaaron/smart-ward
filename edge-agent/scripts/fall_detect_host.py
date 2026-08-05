"""宿主机摄像头跌倒检测与 MQTT 上报

在 Windows 宿主机读取 USB 摄像头，用 YOLOv8n-pose 提取人体关键点，
通过躯干倾角 + 持续时间规则判断疑似跌倒，并将结果发送到云端。

运行示例：
    .venv-fall\\Scripts\\python.exe scripts\\fall_detect_host.py
    .venv-fall\\Scripts\\python.exe scripts\\fall_detect_host.py --camera 1 --no-display

宿主机脚本模拟 EDGE-W01-B01，不依赖容器内 edge-agent 的摄像头透传。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import uuid4


WARD_ID = "W-01"
BED_ID = "B01"
NODE_ID = "EDGE-W01-B01"
MODEL_NAME = "yolov8n-pose"
MODEL_VERSION = "8.0.0"
EVENT_TOPIC = f"ward/{WARD_ID}/node/{NODE_ID}/event"
HEALTH_TOPIC = f"ward/{WARD_ID}/node/{NODE_ID}/health"

# COCO 17-keypoint indices: left/right shoulder and hip.
LEFT_SHOULDER, RIGHT_SHOULDER = 5, 6
LEFT_HIP, RIGHT_HIP = 11, 12


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def torso_angle(keypoints: Iterable[Iterable[float]]) -> Optional[float]:
    """Return torso angle from vertical in degrees, or None for invalid points."""
    points = list(keypoints)
    if len(points) <= RIGHT_HIP:
        return None
    try:
        shoulder = (
            (float(points[LEFT_SHOULDER][0]) + float(points[RIGHT_SHOULDER][0])) / 2,
            (float(points[LEFT_SHOULDER][1]) + float(points[RIGHT_SHOULDER][1])) / 2,
        )
        hip = (
            (float(points[LEFT_HIP][0]) + float(points[RIGHT_HIP][0])) / 2,
            (float(points[LEFT_HIP][1]) + float(points[RIGHT_HIP][1])) / 2,
        )
    except (IndexError, TypeError, ValueError):
        return None

    dx = hip[0] - shoulder[0]
    dy = hip[1] - shoulder[1]
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return None
    return math.degrees(math.atan2(abs(dx), abs(dy)))


def point_confidence(confidences: Any) -> float:
    """Use the four torso points as the minimum reliable confidence."""
    try:
        values = [
            float(confidences[LEFT_SHOULDER]),
            float(confidences[RIGHT_SHOULDER]),
            float(confidences[LEFT_HIP]),
            float(confidences[RIGHT_HIP]),
        ]
        return min(values)
    except (IndexError, TypeError, ValueError):
        return 0.0


def classify_posture(angle: Optional[float]) -> Tuple[str, float]:
    if angle is None:
        return "unknown", 0.0
    fall_score = min(angle / 90.0, 1.0)
    if angle > 60.0:
        return "falling", fall_score
    if angle < 30.0:
        return "standing", fall_score
    return "sitting", fall_score


def envelope(payload: Dict[str, Any], event_id: Optional[str] = None) -> Dict[str, Any]:
    return {
        "message_id": str(uuid4()),
        "event_id": event_id,
        "schema_version": "v1",
        "occurred_at": utc_now(),
        "source": "edge:host-cam",
        "trace_id": str(uuid4()),
        "payload": payload,
    }


def json_keypoints(points: Any) -> List[List[float]]:
    try:
        return [[round(float(value), 5) for value in point[:2]] for point in points]
    except (TypeError, ValueError):
        return []


class HostFallDetector:
    """YOLO pose detector with temporal fall-event de-duplication."""

    def __init__(self, model: Any, mqtt_client: Any, min_duration: float = 1.0):
        self.model = model
        self.mqtt = mqtt_client
        self.min_duration = min_duration
        self.falling_since: Optional[float] = None
        self.event_sent = False
        self.last_inference_ms = 0.0
        self.frames = 0
        self.started_at = time.monotonic()

    def process(self, frame: Any) -> Tuple[Any, Dict[str, Any]]:
        started = time.perf_counter()
        results = self.model.predict(frame, verbose=False)
        inference_ms = (time.perf_counter() - started) * 1000
        self.last_inference_ms = inference_ms
        self.frames += 1

        best: Optional[Dict[str, Any]] = None
        result = results[0] if results else None
        if result is not None and getattr(result, "keypoints", None) is not None:
            keypoint_xy = result.keypoints.xy
            keypoint_conf = result.keypoints.conf
            count = len(keypoint_xy)
            for person_index in range(count):
                points = keypoint_xy[person_index].tolist()
                confidences = (
                    keypoint_conf[person_index].tolist()
                    if keypoint_conf is not None
                    else []
                )
                angle = torso_angle(points)
                posture, score = classify_posture(angle)
                confidence = point_confidence(confidences)
                if confidence < 0.35:
                    posture, score = "unknown", 0.0
                candidate = {
                    "posture": posture,
                    "fall_score": score,
                    "torso_angle": angle,
                    "keypoints": json_keypoints(points),
                    "keypoint_confidence": confidence,
                    "person_index": person_index,
                }
                if best is None or candidate["fall_score"] > best["fall_score"]:
                    best = candidate

        state = best or {
            "posture": "unknown",
            "fall_score": 0.0,
            "torso_angle": None,
            "keypoints": [],
            "keypoint_confidence": 0.0,
            "person_index": None,
        }
        now = time.monotonic()
        if state["posture"] == "falling":
            if self.falling_since is None:
                self.falling_since = now
            duration = now - self.falling_since
            if duration >= self.min_duration and not self.event_sent:
                self._publish_event(state, duration)
                self.event_sent = True
        else:
            self.falling_since = None
            self.event_sent = False
            duration = 0.0

        state["falling_duration"] = duration
        state["inference_ms"] = inference_ms
        return self._annotate(frame, result, state), state

    def _publish_event(self, state: Dict[str, Any], duration: float) -> None:
        event_id = str(uuid4())
        now = utc_now()
        payload = {
            "event_id": event_id,
            "ward_id": WARD_ID,
            "node_id": NODE_ID,
            "bed_id": BED_ID,
            "event_type": "fall_suspected",
            "priority": "P1",
            "state": "new",
            "occurred_at": now,
            "detected_at": now,
            "confidence": round(float(state["fall_score"]), 4),
            "model": {
                "model_name": MODEL_NAME,
                "model_version": MODEL_VERSION,
                "inference_ms": max(0, int(round(self.last_inference_ms))),
            },
            "evidence_refs": [
                {"kind": "pose_keypoints", "ref": f"host-camera://{event_id}"}
            ],
            "rule_hits": [
                "posture=falling",
                f"torso_angle={state['torso_angle']:.1f}>60",
                f"duration={duration:.1f}s>=1.0s",
            ],
            "details": {
                "posture": state["posture"],
                "fall_score": round(float(state["fall_score"]), 4),
                "torso_angle": round(float(state["torso_angle"]), 2),
                "falling_duration": round(duration, 2),
                "keypoints": state["keypoints"],
                "keypoint_confidence": round(float(state["keypoint_confidence"]), 4),
            },
        }
        publish(self.mqtt, EVENT_TOPIC, envelope(payload, event_id))
        print(
            f"[{NODE_ID}] 上报疑似跌倒: event_id={event_id} "
            f"angle={state['torso_angle']:.1f} score={state['fall_score']:.2f}"
        )

    @staticmethod
    def _annotate(frame: Any, result: Any, state: Dict[str, Any]) -> Any:
        if result is None:
            return frame
        try:
            annotated = result.plot()
            import cv2

            text = (
                f"{state['posture']} angle="
                f"{state['torso_angle']:.1f} "
                if state["torso_angle"] is not None
                else f"{state['posture']} angle=n/a "
            )
            text += f"score={state['fall_score']:.2f}"
            if state["falling_duration"] > 0:
                text += f" duration={state['falling_duration']:.1f}s"
            cv2.putText(
                annotated, text, (20, 35), cv2.FONT_HERSHEY_SIMPLEX,
                0.8, (0, 0, 255) if state["posture"] == "falling" else (0, 180, 0), 2,
            )
            return annotated
        except Exception:
            return frame


def publish(client: Any, topic: str, payload: Dict[str, Any]) -> None:
    info = client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=1)
    if getattr(info, "rc", 0) != 0:
        print(f"MQTT 发布失败: topic={topic} rc={info.rc}")


def health_payload(started_at: float, inference_ms: float, frames: int) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {
        "inference_ms_avg": round(inference_ms, 1),
        "fps": round(frames / max(time.monotonic() - started_at, 1e-6), 2),
    }
    try:
        import psutil

        metrics["cpu_percent"] = psutil.cpu_percent(interval=None)
        metrics["mem_percent"] = psutil.virtual_memory().percent
    except ImportError:
        pass
    return {
        "node_id": NODE_ID,
        "ward_id": WARD_ID,
        "status": "online",
        "timestamp": utc_now(),
        "model_version": f"{MODEL_NAME}:{MODEL_VERSION}",
        "buffered_events": 0,
        "uptime_seconds": int(time.monotonic() - started_at),
        "metrics": metrics,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="宿主机 YOLOv8n-pose 跌倒检测")
    parser.add_argument("--camera", type=int, default=0, help="摄像头索引，默认 0")
    parser.add_argument("--model", default="yolov8n-pose.pt", help="YOLO 姿态模型路径")
    parser.add_argument("--broker", default=os.getenv("MQTT_BROKER", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1884")))
    parser.add_argument("--interval", type=float, default=1.0, help="推理间隔秒数")
    parser.add_argument("--fall-duration", type=float, default=1.0, help="跌倒持续确认秒数")
    parser.add_argument("--no-display", action="store_true", help="不打开实时画面窗口")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    import cv2
    import paho.mqtt.client as mqtt
    from ultralytics import YOLO

    print(f"加载模型: {args.model}")
    model = YOLO(args.model)
    camera = cv2.VideoCapture(args.camera)
    if not camera.isOpened():
        print(f"无法打开摄像头索引 {args.camera}，可用 --camera 1/2 重试")
        return 2

    client = mqtt.Client(client_id=f"host-cam-{uuid4().hex[:8]}")
    connected = False
    try:
        client.connect(args.broker, args.port, keepalive=60)
        client.loop_start()
        connected = True
        print(f"MQTT 已连接: {args.broker}:{args.port}")
    except Exception as exc:
        print(f"MQTT 连接失败: {exc}")
        camera.release()
        return 3

    started_at = time.monotonic()
    detector = HostFallDetector(model, client, min_duration=args.fall_duration)
    last_health = 0.0
    running = True

    def stop_handler(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop_handler)

    publish(client, HEALTH_TOPIC, envelope(health_payload(started_at, 0.0, 0)))
    try:
        while running:
            ok, frame = camera.read()
            if not ok:
                print("摄像头读取失败，退出")
                break
            annotated, state = detector.process(frame)
            now = time.monotonic()
            if now - last_health >= 30.0:
                publish(client, HEALTH_TOPIC, envelope(
                    health_payload(started_at, detector.last_inference_ms, detector.frames)
                ))
                last_health = now

            if not args.no_display:
                cv2.imshow("smart-ward host fall detection", annotated)
                if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                    break
            time.sleep(max(0.0, args.interval))
    finally:
        publish(client, HEALTH_TOPIC, envelope({
            **health_payload(started_at, detector.last_inference_ms, detector.frames),
            "status": "offline",
            "timestamp": utc_now(),
        }))
        camera.release()
        if not args.no_display:
            cv2.destroyAllWindows()
        if connected:
            client.loop_stop()
            client.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
