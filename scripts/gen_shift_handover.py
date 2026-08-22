#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""边缘端交接班小 agent -- 生成每床自然语言交接班记录（薄封装）

核心逻辑见 edge-agent/src/agent_service.py（与主循环 MQTT 命令共用）：
检索事件/统计/趋势/上次交接 -> LLMAdvisor 生成 -> 写入边缘 SQLite shift_handovers

用法:
  python scripts/gen_shift_handover.py --bed B02 --period evening
  python scripts/gen_shift_handover.py --bed B02 --period day --date 2026-08-19
  LLM_MODE=real LLM_N_GPU_LAYERS=99 python scripts/gen_shift_handover.py --bed B01
"""

import argparse
import os
import sys
from datetime import datetime

EDGE_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "edge-agent", "src")
if EDGE_SRC not in sys.path:
    sys.path.insert(0, os.path.abspath(EDGE_SRC))

from database import LocalDatabase  # noqa: E402
from agent_service import EdgeAgentService, default_period  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="边缘端交接班小 agent：生成每床自然交接班记录")
    parser.add_argument("--db", default="edge-agent/src/data/edge_EDGE-W01-B01.db",
                        help="边缘 SQLite 路径（默认 edge-agent/src/data/edge_EDGE-W01-B01.db）")
    parser.add_argument("--patients", default="edge-agent/config/patients.json")
    parser.add_argument("--bed", default="B01")
    parser.add_argument("--node", default="")
    parser.add_argument("--ward", default="W-01")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--period", choices=["day", "evening", "night"], default=None)
    parser.add_argument("--out", default="edge-agent/data/handovers")
    args = parser.parse_args()

    period = args.period or default_period()
    node_id = args.node or f"EDGE-{args.ward}-{args.bed}"

    print(f"[shift-agent] 班次: {args.date} {period}")
    service = EdgeAgentService(node_id, args.bed, args.ward,
                               database=LocalDatabase(args.db))
    result = service.generate_handover(args.date, period)
    print(f"[shift-agent] 生成完成 (mode={result['mode']}, p1={result['p1_count']}, "
          f"total={result['event_count']})")

    os.makedirs(args.out, exist_ok=True)
    md_path = os.path.join(args.out, f"{args.bed}-{args.date}-{period}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(result["handover_text"] + "\n")
    print(f"[shift-agent] 已导出: {md_path}")

    print("\n" + "=" * 60)
    print(result["handover_text"])
    print("=" * 60)


if __name__ == "__main__":
    main()
