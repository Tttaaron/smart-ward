#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""P1 侧：重复 request 去重测试发送脚本（阶段1）。

使用同一个 event_id/trace_id，向正常 inference/request 主题连续发送
count 次完全相同的 request（qos=1），模拟边缘端重复上报。

用法:
    python scripts/send_duplicate_requests.py --count 20 \
        --broker localhost --port 1883 --node EDGE-W01-B02
"""
import argparse
import json
import time
import uuid
from datetime import datetime, timezone

import paho.mqtt.client as mqtt


def build_request(event_id, trace_id, node_id, ward_id):
    """构造与 edge-agent 一致的推理请求信封。"""
    return {
        "message_id": f"m-{uuid.uuid4().hex[:6]}",
        "schema_version": "v1",
        "occurred_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": "edge:EDGE-W01-B02",
        "event_id": event_id,
        "trace_id": trace_id,
        "payload": {
            "event_id": event_id,
            "trace_id": trace_id,
            "event_type": "fall_suspected",
            "priority": "P1",
            "confidence": 0.78,
            "bed_id": "B02",
            "node_id": node_id,
            "ward_id": ward_id,
            "reason": "P1重复request去重测试(阶段1)",
            "request_mode": "cloud",
            "timeout_ms": 10000,
            "requested_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "observations_summary": [],
            "event_details": {},
            "evidence_refs": [],
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--broker", default="localhost")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--node", default="EDGE-W01-B02")
    parser.add_argument("--ward", default="W-01")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--interval", type=float, default=0.05)
    args = parser.parse_args()

    event_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    topic = f"ward/{args.ward}/node/{args.node}/inference/request"

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"dup-send-{uuid.uuid4().hex[:6]}")
    client.connect(args.broker, args.port, 60)
    client.loop_start()
    time.sleep(0.3)

    payload = build_request(event_id, trace_id, args.node, args.ward)
    body = json.dumps(payload, ensure_ascii=False)

    print(f"===== 重复 request 去重测试 =====")
    print(f"event_id = {event_id}")
    print(f"trace_id = {trace_id}")
    print(f"topic    = {topic}")
    print(f"count    = {args.count}")
    print()

    for i in range(1, args.count + 1):
        info = client.publish(topic, body, qos=1)
        print(f"[{i:2d}/{args.count}] publish rc={info.rc} event={event_id[:8]} trace={trace_id[:8]}")
        time.sleep(args.interval)

    time.sleep(1.0)
    client.loop_stop()
    client.disconnect()
    print(f"\n===== 完成：{args.count} 次完全相同 request 已发送 =====")


if __name__ == "__main__":
    main()
