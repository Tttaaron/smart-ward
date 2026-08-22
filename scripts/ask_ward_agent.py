#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""边缘端问答小 agent -- 自然语言查询本床历史（薄封装）

核心逻辑见 edge-agent/src/agent_service.py（与主循环 MQTT 命令共用）：
意图解析（床位/时间范围/事件类型）-> SQLite 检索 -> LLMAdvisor.answer_question
（mock 确定性拼接 / real GGUF 自然回答，不编造数据）。

用法:
  python scripts/ask_ward_agent.py --bed B02 --question "今晚离床了几次？"
  python scripts/ask_ward_agent.py --question "李伯伯近7天发生了什么？"
"""

import argparse
import os
import sys

EDGE_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "edge-agent", "src")
if EDGE_SRC not in sys.path:
    sys.path.insert(0, os.path.abspath(EDGE_SRC))

from database import LocalDatabase  # noqa: E402
from agent_service import EdgeAgentService, detect_bed  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="边缘端问答小 agent（自然语言查历史）")
    parser.add_argument("--question", "-q", required=True, help="护士问题")
    parser.add_argument("--db", default="edge-agent/src/data/edge_EDGE-W01-B01.db")
    parser.add_argument("--patients", default="edge-agent/config/patients.json")
    parser.add_argument("--bed", default="B02", help="默认床位（问题中提及则覆盖）")
    parser.add_argument("--ward", default="W-01")
    parser.add_argument("--node", default="")
    args = parser.parse_args()

    patients = {}
    if os.path.exists(args.patients):
        import json
        with open(args.patients, encoding="utf-8") as f:
            patients = json.load(f)

    bed = detect_bed(args.question, patients, args.bed)
    node_id = args.node or f"EDGE-{args.ward}-{bed}"

    service = EdgeAgentService(node_id, bed, args.ward,
                               database=LocalDatabase(args.db))
    result = service.answer(args.question)
    print(f"[ask-agent] 床位={bed} 时间范围={result['time_range']} "
          f"mode={result['mode']}")
    print("\n" + "=" * 60)
    print(f"问：{args.question}")
    print(f"答：{result['answer']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
