#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""受控响应器 — 阶段 3/4/5 异常场景取证专用

用于向边缘端注入"非法 judgment / 未知 event_id / trace 不匹配"三类异常响应，
配合 mqtt_cloud_sync_test.py 的 request 侧一起构成完整取证链路。

使用前必须先停止正常 cloud-llm-service 对相应事件的响应
（或让本脚本抢先发布，因为边缘端按 event_id+trace_id 幂等，
先到的响应生效，重复的会被忽略）。

模式（--mode）:
  invalid         对指定 event_id/trace_id 发布 judgment=bogus 的响应
  unknown         对不存在的 event_id 发布响应（边缘应忽略）
  wrongtrace      对存在的 event_id 但错误的 trace_id 发布响应（边缘应丢弃）

用法:
  # 阶段3 非法judgment：先用 mqtt_cloud_sync_test.py --scenario normal 发起请求拿到 event_id/trace_id，
  # 或本脚本自带 --auto-request 一并发起
  python scripts/controlled_responder.py --mode invalid --count 26 --auto-request

  # 阶段4 未知event：直接发响应，不需要真实请求
  python scripts/controlled_responder.py --mode unknown --count 25

  # 阶段5 trace不匹配：自动发起请求，responder 用错误 trace_id 回
  python scripts/controlled_responder.py --mode wrongtrace --count 28 --auto-request
"""

import argparse
import json
import time
import uuid

import paho.mqtt.client as mqtt

DEFAULT_BROKER = "127.0.0.1"
DEFAULT_PORT = 1883
DEFAULT_NODE = "EDGE-W01-B01"
DEFAULT_WARD = "W-01"


def build_request(event_id, trace_id, node_id, ward_id, confidence=0.5,
                   event_type="fall_suspected"):
    """构造推理请求信封（与 mqtt_cloud_sync_test.py / edge-agent 一致）"""
    return {
        "message_id": f"m-{uuid.uuid4().hex[:6]}",
        "schema_version": "v1",
        "occurred_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "controlled-responder",
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


def build_response(event_id, trace_id, judgment="confirm", advice="controlled-test"):
    """构造推理响应信封（与 cloud-llm-service mqtt_handler._publish_response 一致）"""
    return {
        "message_id": f"m-{uuid.uuid4().hex[:6]}",
        "schema_version": "v1",
        "occurred_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "controlled-responder",
        "event_id": event_id,
        "trace_id": trace_id,
        "payload": {
            "event_id": event_id,
            "trace_id": trace_id,
            "judgment": judgment,
            "confidence": 0.9,
            "advice": advice,
            "latency_ms": 1,
            "model_name": "controlled-responder",
            "model_version": "test",
        },
    }


def main():
    parser = argparse.ArgumentParser(description="受控响应器：注入异常响应用于取证")
    parser.add_argument("--broker", default=DEFAULT_BROKER)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--node", default=DEFAULT_NODE)
    parser.add_argument("--ward", default=DEFAULT_WARD)
    parser.add_argument("--mode", choices=["invalid", "unknown", "wrongtrace"], required=True)
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--auto-request", action="store_true",
                        help="是否先发起真实请求（invalid/wrongtrace 需要；unknown 不需要）")
    parser.add_argument("--interval", type=float, default=0.3)
    parser.add_argument("--log", default=None, help="输出 JSONL 日志文件路径")
    args = parser.parse_args()

    topic_request = f"ward/{args.ward}/node/{args.node}/inference/request"
    topic_response = f"node/{args.node}/inference/response"

    client = mqtt.Client(client_id=f"controlled-responder-{uuid.uuid4().hex[:6]}")
    client.connect(args.broker, args.port, 60)
    client.loop_start()

    records = []
    log_fp = open(args.log, "a", encoding="utf-8") if args.log else None

    print(f"===== 受控响应器 mode={args.mode} count={args.count} =====")
    print(f"broker={args.broker}:{args.port}  request_topic={topic_request}  response_topic={topic_response}")

    for i in range(args.count):
        event_id = f"controlled-{args.mode}-{uuid.uuid4().hex[:8]}"
        trace_id = f"trace-{uuid.uuid4().hex[:8]}"

        if args.mode == "invalid":
            # 需要真实请求存在，边缘端才有 pending 记录可对照
            if args.auto_request:
                req = build_request(event_id, trace_id, args.node, args.ward)
                client.publish(topic_request, json.dumps(req, ensure_ascii=False), qos=1)
                time.sleep(0.2)
            resp = build_response(event_id, trace_id, judgment="bogus", advice="INVALID_JUDGMENT_TEST")

        elif args.mode == "unknown":
            # 不需要真实请求：event_id 边缘端本来就没见过
            resp = build_response(event_id, trace_id, judgment="confirm", advice="UNKNOWN_EVENT_TEST")

        elif args.mode == "wrongtrace":
            # 请求用 trace-A，响应故意用 trace-B
            real_trace = trace_id
            wrong_trace = f"trace-{uuid.uuid4().hex[:8]}"
            if args.auto_request:
                req = build_request(event_id, real_trace, args.node, args.ward)
                client.publish(topic_request, json.dumps(req, ensure_ascii=False), qos=1)
                time.sleep(0.2)
            resp = build_response(event_id, wrong_trace, judgment="confirm", advice="TRACE_MISMATCH_TEST")
            trace_id = real_trace  # 记录真实 trace，wrong_trace 记录在 resp 内

        client.publish(topic_response, json.dumps(resp, ensure_ascii=False), qos=1)

        record = {
            "seq": i + 1,
            "mode": args.mode,
            "event_id": event_id,
            "trace_id": trace_id,
            "response_trace_id": resp["trace_id"],
            "judgment": resp["payload"]["judgment"],
            "published_at": resp["occurred_at"],
        }
        records.append(record)
        if log_fp:
            log_fp.write(json.dumps(record, ensure_ascii=False) + "\n")
            log_fp.flush()

        print(f"[{i+1}/{args.count}] event_id={event_id} trace={trace_id} judgment={resp['payload']['judgment']}")
        time.sleep(args.interval)

    if log_fp:
        log_fp.close()

    client.loop_stop()
    client.disconnect()

    print(f"\n===== 完成: 已发布 {len(records)} 条 {args.mode} 响应 =====")
    if args.log:
        print(f"日志已写入: {args.log}")
    print("请到边缘端核对 SQLite 中对应 event_id 的 status，确认未进入正常 completed 路径。")


if __name__ == "__main__":
    main()
