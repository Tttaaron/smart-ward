"""MQTT 抓包：订阅边端 inference 请求/响应/事件/健康主题，落盘 JSONL。

用法（在 smart-ward 根目录）：
    python docs/evidence/20260823_vllm_real_link/capture_mqtt.py <输出文件>
"""
import json
import sys
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

OUT = sys.argv[1] if len(sys.argv) > 1 else "capture.jsonl"
BROKER = "127.0.0.1"
PORT = 1884

TOPICS = [
    "ward/W-01/node/EDGE-W01-B02/inference/request",
    "node/EDGE-W01-B02/inference/response",
    "ward/W-01/node/EDGE-W01-B02/event",
    "ward/W-01/node/EDGE-W01-B02/health",
]

f = open(OUT, "a", encoding="utf-8")


def on_connect(client, userdata, flags, reason_code, properties=None):
    rc = getattr(reason_code, "value", reason_code)
    print(f"[capture] connected rc={rc}", flush=True)
    for t in TOPICS:
        client.subscribe(t, qos=1)


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except Exception:
        payload = {"raw": msg.payload.decode("utf-8", "replace")}
    record = {
        "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "topic": msg.topic,
        "qos": msg.qos,
        "payload": payload,
    }
    line = json.dumps(record, ensure_ascii=False, sort_keys=True)
    f.write(line + "\n")
    f.flush()
    print(f"[capture] {msg.topic}", flush=True)


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="capture-real-vllm")
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, 60)
client.loop_forever()
