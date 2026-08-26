#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MQTT 抓包（容错集成测试专用，默认连本地隧道 1883）。

订阅边端 request/response/event/health 主题，落盘 JSONL。

用法:
    python scripts/capture_mqtt_fault.py <输出文件> [--broker localhost] [--port 1883]
"""
import argparse
import json
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

DEFAULT_TOPICS = [
    "ward/W-01/node/EDGE-W01-B02/inference/request",
    "node/EDGE-W01-B02/inference/response",
    "ward/W-01/node/EDGE-W01-B02/event",
    "ward/W-01/node/EDGE-W01-B02/health",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--broker", default="localhost")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--node", default="EDGE-W01-B02")
    parser.add_argument("--ward", default="W-01")
    args = parser.parse_args()

    topics = [t.replace("EDGE-W01-B02", args.node).replace("W-01", args.ward)
              for t in DEFAULT_TOPICS]
    f = open(args.output, "a", encoding="utf-8")

    def on_connect(client, userdata, flags, reason_code, properties=None):
        rc = getattr(reason_code, "value", reason_code)
        print(f"[capture] connected rc={rc}", flush=True)
        for t in topics:
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
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        f.flush()
        print(f"[capture] {msg.topic}", flush=True)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id="capture-fault-test")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(args.broker, args.port, 60)
    client.loop_forever()


if __name__ == "__main__":
    main()
