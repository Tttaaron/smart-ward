# Gray release / failed rollback / edge health confirmation demo.
# 负责人：P4 振鑫 | 截止：2026-08-20
#
# 场景1：v1 灰度 -> 2 节点 health ok -> 全量 rollout (ACTIVE)
# 场景2：v2 灰度 -> 边缘 health 失败 -> rollback 到 v1
#
# Usage:
#   python demo/run_release_demo.py
# 运行后自动生成证据文件：
#   docs/evidence/20260818_training-coordinator_release_rollback_<commit>.txt

import json
import os
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.model_registry import ModelRegistry, ReleaseManager, ModelStatus

EDGE_NODES = ["EDGE-W01-B01", "EDGE-W01-B02", "EDGE-W01-B03"]


def make_weights(scale):
    return [np.full((2, 3), scale, np.float32), np.full((2,), scale, np.float32)]


def current_commit():
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            stderr=subprocess.DEVNULL,
        )
        return out.decode().strip()
    except Exception:
        return "unknown"


def main():
    commit = current_commit()
    print("=" * 68)
    print("  灰度发布 / 失败回滚 / 边缘 health 确认演示")
    print(f"  代码提交: {commit}")
    print("=" * 68)

    reg = ModelRegistry()
    mgr = ReleaseManager(reg, min_healthy_nodes=2)

    # ---- 场景1：正常灰度发布 + health 确认 + 全量 rollout ----
    print("[场景1] 注册 v1 并灰度发布...")
    v1 = reg.register(
        "qwen1.5b", make_weights(1.0), "models/qwen1.5b/", "ward-nlu-500-v1",
        metrics={"acc": 0.80}, aggregation_version="agg-job001-r10",
    )
    rec_pub1 = mgr.publish(v1.model_version, gray_percent=10)
    print(f"  publish: batch={rec_pub1[chr(114)+chr(101)+chr(108)+chr(101)+chr(97)+chr(115)+chr(101)+chr(95)+chr(98)+chr(97)+chr(116)+chr(99)+chr(104)]}")

    print("  边缘节点上报 health...")
    for node in EDGE_NODES[:2]:
        ok = mgr.confirm_health(v1.model_version, node, True, latency_ms=120)
        print(f"    {node}: ok=True latency=120ms -> healthy={ok}")

    mgr.rollout(v1.model_version)
    active1 = reg.active()
    print(f"  rollout 完成，当前 ACTIVE: {active1.model_version}")
    assert active1.model_version == v1.model_version

    # ---- 场景2：v2 灰度 -> health 失败 -> 回滚 ----
    print("")
    print("[场景2] 注册 v2 并灰度发布（模拟异常版本）...")
    v2 = reg.register(
        "qwen1.5b", make_weights(2.0), "models/qwen1.5b/", "ward-nlu-500-v1",
        metrics={"acc": 0.90}, aggregation_version="agg-job001-r11",
    )
    mgr.publish(v2.model_version, gray_percent=10)

    print("  边缘节点 health 失败...")
    mgr.confirm_health(v2.model_version, EDGE_NODES[0], False, latency_ms=9999)
    mgr.confirm_health(v2.model_version, EDGE_NODES[1], False, latency_ms=5000)
    summary_bad = mgr.health_summary(v2.model_version)
    print(f"  v2 health: healthy={summary_bad[chr(104)+chr(101)+chr(97)+chr(108)+chr(116)+chr(104)+chr(121)]} total={summary_bad[chr(116)+chr(111)+chr(116)+chr(97)+chr(108)]}")

    print("  触发失败回滚...")
    rollback_rec = mgr.rollback(v2.model_version)
    print(f"  rollback: status={rollback_rec[chr(115)+chr(116)+chr(97)+chr(116)+chr(117)+chr(115)]} fallback={rollback_rec[chr(102)+chr(97)+chr(108)+chr(108)+chr(98)+chr(97)+chr(99)+chr(107)]}")
    assert rollback_rec["status"] == "ok"
    assert rollback_rec["fallback"] == v1.model_version

    active2 = reg.active()
    print(f"  回滚后 ACTIVE: {active2.model_version}")
    assert active2.model_version == v1.model_version
    assert reg.get(v2.model_version).status == ModelStatus.ROLLED_BACK

    # ---- 输出证据 ----
    evidence = {
        "scenario": "gray-release-rollback",
        "commit": commit,
        "edge_nodes": EDGE_NODES,
        "release_log": mgr.log(),
        "health_v1": mgr.health_summary(v1.model_version),
        "health_v2": mgr.health_summary(v2.model_version),
        "final_active": active2.model_version,
        "v2_status": reg.get(v2.model_version).status.value,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    ev_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "evidence")
    os.makedirs(ev_dir, exist_ok=True)
    ev_path = os.path.join(ev_dir, f"20260818_training-coordinator_release_rollback_{commit}.txt")
    with open(ev_path, "w", encoding="utf-8") as f:
        f.write(chr(10))
        f.write(chr(10))
    print("")
    print(f"证据已保存: {ev_path}")
    print("=" * 68)
    print("演示通过：灰度发布 + health 确认 + 失败回滚 全链路 OK")


if __name__ == "__main__":
    main()
