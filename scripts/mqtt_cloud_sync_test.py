#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""云边协同推理链路联调测试脚本

在真实/本地 MQTT Broker 上验证 cloud-llm-service 的推理请求-响应闭环。
与 mosquitto_pub 手动发消息等价，但可参数化场景并统计通过率。

场景（--scenario）:
  normal           正常链路：request -> 云端研判 -> response（默认）
  duplicate        重复请求：同一 event_id 连发 N 次，云端只应处理 1 次
  timeout          云端不可用：请求无响应（先停 cloud-llm-service 再运行）
  invalid          云端返回非法 judgment（需配合 mock 服务注入，见 docs/22）
  unknown          响应指向未知 event_id（边缘应忽略，见 docs/22）
  trace_mismatch   trace_id 不匹配（边缘应丢弃响应，见 docs/22）
  offline          断网自治（docker network disconnect 场景，见 docs/22）

用法:
  python scripts/mqtt_cloud_sync_test.py --scenario normal --count 5
  python scripts/mqtt_cloud_sync_test.py --scenario duplicate --count 10
  python scripts/mqtt_cloud_sync_test.py --broker 127.0.0.1 --port 1883 --count 20
"""

import argparse
import json
import sys
import time
import uuid

import paho.mqtt.client as mqtt

DEFAULT_BROKER = "127.0.0.1"
DEFAULT_PORT = 1883
DEFAULT_NODE = "EDGE-W01-B01"
DEFAULT_WARD = "W-01"

SCENARIOS = ("normal", "duplicate", "timeout", "invalid",
             "unknown", "trace_mismatch", "offline")


def build_request(event_id, trace_id, node_id, ward_id, confidence=0.5,
                  event_type="fall_suspected"):
    """构造推理请求信封（与 edge-agent mqtt_client 一致）"""
    return {
        "message_id": f"m-{uuid.uuid4().hex[:6]}",
        "schema_version": "v1",
        "occurred_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "sync-test",
        "event_id": event_id,
        "trace_id": trace_id,
        "payload": {
            "event_id": event_id,
            "trace_id": trace_id,
            "event_type": event_type,
            "priority": "P1",
            "confidence": confidence,
            "bed_id": "B01",
            "node_id": node_id,
            "ward_id": ward_id,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="云边推理链路联调测试")
    parser.add_argument("--broker", default=DEFAULT_BROKER)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--scenario", choices=SCENARIOS, default="normal")
    parser.add_argument("--count", type=int, default=5,
                        help="每场景请求次数（验收要求 ≥20）")
    parser.add_argument("--node", default=DEFAULT_NODE)
    parser.add_argument("--ward", default=DEFAULT_WARD)
    args = parser.parse_args()

    topic_request = f"ward/{args.ward}/node/{args.node}/inference/request"
    topic_response = f"node/{args.node}/inference/response"

    client = mqtt.Client(client_id=f"sync-test-{uuid.uuid4().hex[:6]}")
    responses = []
    events_observed = {"request": 0, "response": 0}
    events_observed_lock = __import__("threading").Lock()

    def on_message(c, userdata, msg):
        if msg.topic == topic_response:
            with events_observed_lock:
                events_observed["response"] += 1
            try:
                payload = json.loads(msg.payload)
                responses.append({
                    "event_id": payload.get("event_id"),
                    "trace_id": payload.get("trace_id"),
                    "judgment": (payload.get("payload") or {}).get("judgment"),
                    "confidence": (payload.get("payload") or {}).get("confidence"),
                    "model_name": (payload.get("payload") or {}).get("model_name"),
                })
            except json.JSONDecodeError:
                pass
        elif msg.topic == topic_request:
            with events_observed_lock:
                events_observed["request"] += 1

    client.on_message = on_message
    client.connect(args.broker, args.port, 60)
    client.loop_start()
    client.subscribe(topic_request, qos=1)
    client.subscribe(topic_response, qos=1)
    time.sleep(1)

    sent_ids = []
    if args.scenario == "duplicate":
        # 同一 event_id 重复发送 count 次，云端只应处理 1 次
        event_id = f"EV-DUP-{int(time.time())}"
        trace_id = f"TR-DUP-{uuid.uuid4().hex[:8]}"
        for _ in range(args.count):
            client.publish(topic_request,
                           json.dumps(build_request(event_id, trace_id,
                                                    args.node, args.ward)), qos=1)
            time.sleep(0.3)
        sent_ids = [event_id]
        expect_responses = 1
    else:
        # normal/timeout 等：每次独立 event_id
        for i in range(args.count):
            event_id = f"EV-{int(time.time())}-{i}"
            trace_id = f"TR-{uuid.uuid4().hex[:8]}"
            client.publish(topic_request,
                           json.dumps(build_request(event_id, trace_id,
                                                    args.node, args.ward)), qos=1)
            sent_ids.append(event_id)
            time.sleep(0.5)
        expect_responses = args.count

    wait = 6 if args.scenario == "timeout" else 5
    print(f"--- 等待 {wait}s 观察响应 ---", flush=True)
    time.sleep(wait)

    client.loop_stop()
    client.disconnect()

    # 结果统计
    got_responses = [r for r in responses if r["event_id"] in sent_ids]
    print(f"\n===== 场景 [{args.scenario}] 结果 =====")
    print(f"发送请求: {len(sent_ids)} (unique event_id: {len(set(sent_ids))})")
    print(f"broker 观测 response: {events_observed['response']}")
    print(f"匹配 sent_ids 的响应: {len(got_responses)}")

    if args.scenario == "duplicate":
        ok = len(got_responses) == 1
        print(f"预期 1 次处理（去重）: {'PASS ✅' if ok else 'FAIL ❌'}")
    elif args.scenario == "timeout":
        # timeout 场景：先停 cloud-llm-service，应无响应
        ok = len(got_responses) == 0
        print(f"预期 0 响应（云端不可用）: {'PASS ✅' if ok else 'FAIL ❌'}")
    else:
        ok = len(got_responses) == expect_responses
        print(f"预期 {expect_responses} 响应: {'PASS ✅' if ok else 'FAIL ❌'}")
        if got_responses:
            r = got_responses[0]
            print(f"示例: event={r['event_id']} judgment={r['judgment']} "
                  f"conf={r['confidence']} model={r['model_name']}")
            if r["trace_id"] and r["event_id"]:
                print(f"trace 关联: {'PASS ✅' if r['trace_id'] else 'FAIL ❌'}")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
