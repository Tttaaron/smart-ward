"""YOLOv8n-pose 跌倒检测（宿主机版）

架构：宿主机用 OpenCV 读摄像头 -> YOLOv8n-pose 推理 -> 关键点几何判跌倒
     -> 通过 MQTT(localhost:1884) 发安全事件到云端容器 -> 护士站告警

用法：
    python scripts/fall_detect_host.py              # 默认摄像头 0
    python scripts/fall_detect_host.py --camera 1   # 指定摄像头索引
    python scripts/fall_detect_host.py --no-mqtt    # 仅预览推理，不发 MQTT
按 q 退出。

环境依赖：edge-agent/.venv-fall  (ultralytics + opencv-python + paho-mqtt)
"""

import os
import sys
import time
import json
import uuid
import argparse
import threading
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

import cv2
import numpy as np
import paho.mqtt.client as mqtt


# ===== 配置常量 =====

# 边缘节点身份（模拟 B01 床位的边缘节点）
WARD_ID = "W-01"
BED_ID = "B01"
NODE_ID = "EDGE-W01-B01"

# 模型信息（上报到云端，护士站会显示）
MODEL_NAME = "yolov8n-pose"
MODEL_VERSION = "8.0.0"

# MQTT broker（Docker 映射到宿主 1884）
MQTT_HOST = "localhost"
MQTT_PORT = 1884

# 跌倒判定阈值
FALL_ANGLE_THRESHOLD = 55      # 躯干倾角 > 55° 视为跌倒姿态
STAND_ANGLE_THRESHOLD = 25      # 躯干倾角 < 25° 视为站立
FALL_CONFIRM_SECONDS = 0.8     # 跌倒姿态持续超过此秒数才触发事件（防误报）
FALL_DEBOUNCE_SECONDS = 8       # 两次跌倒事件最小间隔（防刷屏）
KP_CONF_THRESHOLD = 0.15        # 关键点置信度门槛（降低以提升召回）

# 健康心跳间隔
HEARTBEAT_INTERVAL = 30

# MJPEG 推流服务端口（供护士站 LiveMonitor <img> 接收）
MJPEG_PORT = 8090

# COCO 17 关键点索引
KP_LEFT_SHOULDER = 5
KP_RIGHT_SHOULDER = 6
KP_LEFT_HIP = 11
KP_RIGHT_HIP = 12


# ===== 工具函数 =====

def now_iso():
    """当前 UTC 时间 ISO 8601（Z 结尾，对齐后端契约）"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_envelope(payload: dict, event_id=None):
    """构造 MQTT 信封（对齐 contracts/envelope.json）"""
    return {
        "message_id": str(uuid.uuid4()),
        "event_id": event_id,
        "schema_version": "v1",
        "occurred_at": now_iso(),
        "source": f"edge:{NODE_ID}",
        "trace_id": str(uuid.uuid4()),
        "payload": payload,
    }


# ===== MJPEG 推流服务 =====
# 共享最新一帧（带 YOLO 标注），供 HTTP 推流线程读取
_latest_frame = None
_frame_lock = threading.Lock()


def update_frame(frame):
    """主循环每帧调用，更新共享画面"""
    global _latest_frame
    with _frame_lock:
        _latest_frame = frame


class MJPEGHandler(BaseHTTPRequestHandler):
    """MJPEG 流响应：multipart/x-mixed-replace"""

    def do_GET(self):
        if self.path != "/stream":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            while True:
                with _frame_lock:
                    frame = _latest_frame
                if frame is not None:
                    ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    if ok:
                        jpg_bytes = jpg.tobytes()
                        self.wfile.write(b"--frame\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(jpg_bytes)}\r\n\r\n".encode())
                        self.wfile.write(jpg_bytes)
                        self.wfile.write(b"\r\n")
                time.sleep(0.05)  # ~20fps
        except (BrokenPipeError, ConnectionResetError):
            pass  # 客户端断开

    def log_message(self, *args):
        pass  # 静默 HTTP 日志


def start_mjpeg_server(port):
    """在后台线程启动 MJPEG 推流服务"""
    server = HTTPServer(("0.0.0.0", port), MJPEGHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[mjpeg] 推流服务已启动 http://localhost:{port}/stream")
    return server


# ===== MQTT 上报 =====

class MqttReporter:
    """向云端 broker 上报事件与健康心跳"""

    def __init__(self, enabled=True):
        self.enabled = enabled
        self.client = None
        if enabled:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                      client_id=f"fall-host-{NODE_ID}")
            self.client.connect(MQTT_HOST, MQTT_PORT, 60)
            self.client.loop_start()
            print(f"[mqtt] 已连接 {MQTT_HOST}:{MQTT_PORT}")

    def publish(self, topic: str, envelope: dict):
        if not self.enabled or not self.client:
            return
        self.client.publish(topic, json.dumps(envelope, ensure_ascii=False), qos=1)

    def report_event(self, posture: str, fall_score: float, torso_angle: float,
                     inference_ms: int, keypoints):
        """上报跌倒安全事件"""
        event_id = str(uuid.uuid4())
        occurred_at = now_iso()

        payload = {
            "event_id": event_id,
            "ward_id": WARD_ID,
            "node_id": NODE_ID,
            "bed_id": BED_ID,
            "event_type": "fall_suspected",
            "priority": "P1",
            "state": "new",
            "occurred_at": occurred_at,
            "detected_at": occurred_at,
            "confidence": round(fall_score, 3),
            "model": {
                "model_name": MODEL_NAME,
                "model_version": MODEL_VERSION,
                "inference_ms": inference_ms,
            },
            "evidence_refs": [],
            "rule_hits": [f"torso_angle={torso_angle:.1f}>{FALL_ANGLE_THRESHOLD}",
                          f"fall_score={fall_score:.2f}"],
            "details": {
                "posture": posture,
                "fall_score": round(fall_score, 3),
                "torso_angle": round(torso_angle, 1),
                "keypoints_count": len(keypoints) if keypoints is not None else 0,
            },
        }
        envelope = make_envelope(payload, event_id=event_id)
        topic = f"ward/{WARD_ID}/node/{NODE_ID}/event"
        self.publish(topic, envelope)
        print(f"[事件] fall_suspected P1 已上报 (confidence={fall_score:.2f}, "
              f"angle={torso_angle:.1f}°, {inference_ms}ms)")

    def report_health(self, status="online", buffered=0):
        """上报节点健康心跳"""
        payload = {
            "node_id": NODE_ID,
            "ward_id": WARD_ID,
            "status": status,
            "timestamp": now_iso(),
            "model_version": f"{MODEL_NAME}:{MODEL_VERSION}",
            "buffered_events": buffered,
        }
        envelope = make_envelope(payload)
        topic = f"ward/{WARD_ID}/node/{NODE_ID}/health"
        self.publish(topic, envelope)
        print(f"[心跳] {status} model={MODEL_NAME}:{MODEL_VERSION}")

    def close(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()


# ===== 跌倒判定 =====

def compute_torso_angle(keypoints):
    """计算躯干与垂直方向的夹角（度）

    躯干线 = 双肩中点 -> 双髋中点
    站立时该线接近垂直，夹角接近 0°
    跌倒时该线接近水平，夹角接近 90°

    Args:
        keypoints: YOLO 输出的关键点数组 [17, 3] 或 [17, 2]，(x, y[, conf])

    Returns:
        (angle_deg, shoulder_mid, hip_mid) 或 (None, None, None) 当关键点不可用时
    """
    if keypoints is None:
        return None, None, None

    kp = np.asarray(keypoints)
    # 取置信度过滤（若有关键点置信度列）
    if kp.shape[-1] >= 3:
        conf = kp[:, 2]
        if conf[KP_LEFT_SHOULDER] < KP_CONF_THRESHOLD or conf[KP_RIGHT_SHOULDER] < KP_CONF_THRESHOLD:
            return None, None, None
        if conf[KP_LEFT_HIP] < KP_CONF_THRESHOLD or conf[KP_RIGHT_HIP] < KP_CONF_THRESHOLD:
            return None, None, None

    try:
        l_shoulder = kp[KP_LEFT_SHOULDER][:2]
        r_shoulder = kp[KP_RIGHT_SHOULDER][:2]
        l_hip = kp[KP_LEFT_HIP][:2]
        r_hip = kp[KP_RIGHT_HIP][:2]

        shoulder_mid = (l_shoulder + r_shoulder) / 2
        hip_mid = (l_hip + r_hip) / 2
        torso_vec = hip_mid - shoulder_mid  # 躯干向量

        dx = abs(torso_vec[0])
        dy = abs(torso_vec[1])
        if dy < 1e-3:
            return 90.0, shoulder_mid, hip_mid
        angle = np.degrees(np.arctan(dx / dy))
        return float(angle), shoulder_mid, hip_mid
    except (IndexError, TypeError):
        return None, None, None


def classify_posture(angle):
    """根据躯干倾角分类体态"""
    if angle is None:
        return "unknown", 0.0
    if angle > FALL_ANGLE_THRESHOLD:
        fall_score = min(angle / 90.0, 1.0)
        return "falling", round(fall_score, 3)
    if angle < STAND_ANGLE_THRESHOLD:
        return "standing", 0.0
    return "sitting", 0.0


# ===== 可视化 =====

COLOR_NORMAL = (0, 200, 0)
COLOR_FALL = (0, 0, 255)
COLOR_SKELETON = (255, 255, 0)

SKELETON_PAIRS = [
    (5, 6), (5, 11), (6, 12), (11, 12),  # 躯干
    (5, 7), (7, 9), (6, 8), (8, 10),     # 上肢
    (11, 13), (13, 15), (12, 14), (14, 16),  # 下肢
]


def draw_overlay(frame, results, angle, posture, fall_score, fps):
    """在画面上绘制检测标注"""
    annotated = frame.copy()

    if results and len(results) > 0:
        r = results[0]
        if r.keypoints is not None and len(r.keypoints.xy) > 0:
            kpts = r.keypoints.xy[0].cpu().numpy()  # [17, 2]
            # 绘制骨架
            for i, j in SKELETON_PAIRS:
                if i < len(kpts) and j < len(kpts):
                    p1 = (int(kpts[i][0]), int(kpts[i][1]))
                    p2 = (int(kpts[j][0]), int(kpts[j][1]))
                    if p1[0] > 0 and p2[0] > 0:
                        cv2.line(annotated, p1, p2, COLOR_SKELETON, 2)
            # 绘制关键点
            for pt in kpts:
                x, y = int(pt[0]), int(pt[1])
                if x > 0 and y > 0:
                    cv2.circle(annotated, (x, y), 4, (0, 255, 255), -1)

        # 绘制 person bbox
        if r.boxes is not None and len(r.boxes) > 0:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                color = COLOR_FALL if posture == "falling" else COLOR_NORMAL
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

    # 状态文字
    color = COLOR_FALL if posture == "falling" else COLOR_NORMAL
    angle_text = f"angle={angle:.0f}deg" if angle is not None else "angle=N/A"
    status_text = f"POSTURE: {posture.upper()}  {angle_text}  score={fall_score:.2f}  FPS={fps:.1f}"
    cv2.putText(annotated, status_text, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    # 跌倒时全屏红色边框警示
    if posture == "falling":
        cv2.putText(annotated, "*** FALL DETECTED ***", (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, COLOR_FALL, 3)
        cv2.rectangle(annotated, (0, 0),
                      (annotated.shape[1] - 1, annotated.shape[0] - 1),
                      COLOR_FALL, 6)

    cv2.imshow("Smart Ward - YOLOv8n-pose Fall Detection", annotated)


# ===== 主循环 =====

def main():
    parser = argparse.ArgumentParser(description="YOLOv8n-pose 跌倒检测（宿主机版）")
    parser.add_argument("--camera", type=int, default=0, help="摄像头索引（默认 0）")
    parser.add_argument("--no-mqtt", action="store_true", help="不发送 MQTT，仅预览推理")
    args = parser.parse_args()

    print(f"[init] 加载 YOLOv8n-pose 模型 ...（首次会自动下载 ~6MB）")
    from ultralytics import YOLO
    model = YOLO("yolov8n-pose.pt")
    print("[init] 模型加载完成")

    reporter = MqttReporter(enabled=not args.no_mqtt)

    # 启动 MJPEG 推流服务（供护士站 LiveMonitor 接收实时画面）
    mjpeg_server = start_mjpeg_server(MJPEG_PORT)

    print(f"[init] 打开摄像头 index={args.camera} ...")
    # Windows 上优先用 DSHOW 后端（实测该摄像头需 DSHOW 才能取到画面），
    # 带 DSHOW 重试 + 其他后端兜底
    cap = None
    for backend in [cv2.CAP_DSHOW, None]:  # 先 DSHOW，再默认
        for attempt in range(2):
            cap = cv2.VideoCapture(args.camera, backend) if backend else cv2.VideoCapture(args.camera)
            if cap.isOpened():
                # 验证能否真正取到帧（isOpened=True 但 read 黑帧的情况）
                ret, test_frame = cap.read()
                if ret and test_frame is not None and test_frame.mean() > 1:
                    backend_name = "DSHOW" if backend else "default"
                    print(f"[init] 摄像头已打开（{backend_name} 后端，第{attempt+1}次）")
                    break
            cap.release()
            print(f"[init] 第 {attempt+1} 次打开失败/黑帧，重试 ...")
            time.sleep(1)
        if cap and cap.isOpened():
            break
        cap = None
    if not cap or not cap.isOpened():
        print(f"[错误] 无法打开摄像头 index={args.camera}，请确认摄像头未被占用")
        reporter.close()
        sys.exit(1)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[init] 摄像头已打开 {width}x{height}，开始检测（按 q 退出）")
    print("[init] 站立 -> 正常；躺下/蹲下至身体接近水平 -> 触发跌倒告警")

    # 跌倒状态跟踪
    fall_state_start = None        # 跌倒姿态开始时间
    last_event_time = 0           # 上次发事件时间（去重）
    is_falling = False            # 当前是否处于已确认跌倒态
    debug_last = 0                 # 调试输出时间戳

    # 健康心跳
    last_heartbeat = time.time()

    # FPS 统计
    frame_count = 0
    fps_timer = time.time()
    fps = 0.0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[错误] 读取画面失败")
                break

            frame_count += 1

            # YOLO 推理（只检测 person，类别 0）
            t0 = time.time()
            results = model.predict(frame, classes=[0], verbose=False)
            inference_ms = int((time.time() - t0) * 1000)

            # 提取关键点并判定
            angle = None
            shoulder_mid = hip_mid = None
            posture = "unknown"
            fall_score = 0.0
            kpts = None

            if results and len(results) > 0 and results[0].keypoints is not None:
                if len(results[0].keypoints.xy) > 0:
                    kpts = results[0].keypoints.data[0].cpu().numpy()  # [17, 3]
                    angle, shoulder_mid, hip_mid = compute_torso_angle(kpts)
                    posture, fall_score = classify_posture(angle)

            # 跌倒状态机：确认逻辑 + 去重
            now = time.time()
            # 每秒打印一次调试状态，方便看实时角度
            if now - debug_last >= 1.0:
                ang_str = f"{angle:.0f}deg" if angle is not None else "N/A"
                print(f"[状态] posture={posture} angle={ang_str} score={fall_score:.2f} "
                      f"inf={inference_ms}ms fps={fps:.1f}", flush=True)
                debug_last = now
            if posture == "falling":
                if fall_state_start is None:
                    fall_state_start = now
                elapsed = now - fall_state_start
                if elapsed >= FALL_CONFIRM_SECONDS and not is_falling:
                    is_falling = True
                    if now - last_event_time >= FALL_DEBOUNCE_SECONDS:
                        reporter.report_event(posture, fall_score, angle or 0,
                                              inference_ms, kpts)
                        last_event_time = now
            else:
                # 恢复站立/坐姿，重置跌倒态
                if is_falling:
                    print(f"[恢复] 体态恢复为 {posture}，跌倒状态解除")
                fall_state_start = None
                is_falling = False

            # 健康心跳
            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                reporter.report_health(status="online")
                last_heartbeat = now

            # FPS 计算
            if now - fps_timer >= 1.0:
                fps = frame_count / (now - fps_timer)
                frame_count = 0
                fps_timer = now

            # 可视化（本地窗口 + MJPEG 推流）
            draw_overlay(frame, results, angle, posture, fall_score, fps)
            # 把标注后的画面共享给 MJPEG 推流线程
            update_frame(frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()
        reporter.close()
        print("[exit] 已退出")


if __name__ == "__main__":
    main()
