# Import P5 (Xianwei) AutoDL-distilled model into ModelRegistry and run
# the release/rollback loop.
#
# Mapping:
#   P5 model : Qwen2.5-1.5B-Ward-v4-Q6 (HF: siwuxie27/Qwen2.5-1.5B-Ward-v4-Q6)
#   Registry : student-qwen1.5b-ward-1.0.0
#
# Confirmed by Xianwei (2026-08-24): model hash, dataset version,
# teacher version, HF artifact path. Metrics still pending eval.
#
# Usage:
#   python demo/import_ward_model.py
#

import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.model_registry import ModelRegistry, ReleaseManager

# ---- P5 model metadata (confirm with Xianwei) ----
MODEL_NAME = "qwen1.5b-ward"
MODEL_VERSION = "student-qwen1.5b-ward-1.0.0"
MODEL_HASH = "c86401b2befde9dd"
ARTIFACT_PATH = "https://huggingface.co/siwuxie27/Qwen2.5-1.5B-Ward-v4-Q6"
DATASET_VERSION = "ward-nlu-500-v1"
TEACHER_VERSION = "teacher-qwen14b-1.0.0"
METRICS = {"acc": 0.0, "recall": 0.0, "f1": 0.0}
PARAMS = {
    "teacher": "Qwen2.5-14B-Instruct-AWQ",
    "student": "Qwen2.5-1.5B",
    "quantization": "Q6",
    "method": "miniLLM-reverse-KL-or-hinton-KD",
    "source_model": "Qwen2.5-1.5B-Ward-v4-Q6",
    "source_artifact": "https://huggingface.co/siwuxie27/Qwen2.5-1.5B-Ward-v4-Q6",
}
EDGE_NODES = ["EDGE-W01-B01", "EDGE-W01-B02", "EDGE-W01-B03"]


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
    print("  Import P5 distilled model -> ModelRegistry release loop")
    print("  commit: %s" % commit)
    print("=" * 68)

    reg = ModelRegistry()
    mgr = ReleaseManager(reg, min_healthy_nodes=2)

    print("")
    print("[import] register external model (metadata only)...")
    mv = reg.register_external(
        model_name=MODEL_NAME,
        model_version=MODEL_VERSION,
        model_hash=MODEL_HASH,
        artifact_path=ARTIFACT_PATH,
        dataset_version=DATASET_VERSION,
        train_params=PARAMS,
        metrics=METRICS,
        base_version=TEACHER_VERSION,
        source="p5-autodl",
    )
    print("  registered: %s (status=%s)" % (mv.model_version, mv.status.value))

    print("")
    print("[release] gray publish + edge health confirm + rollout...")
    pub = mgr.publish(mv.model_version, gray_percent=10)
    print("  release_batch: %s" % pub["release_batch"])

    for node in EDGE_NODES[:2]:
        ok = mgr.confirm_health(mv.model_version, node, True, latency_ms=128)
        print("  %s: ok=True latency=128ms -> healthy=%s" % (node, ok))

    mgr.rollout(mv.model_version)
    active = reg.active()
    print("  rollout OK, ACTIVE=%s" % active.model_version)
    assert active.model_version == MODEL_VERSION

    evidence = {
        "scenario": "import-p5-distilled-model",
        "commit": commit,
        "registry_model": mv.to_dict(),
        "release_log": mgr.log(),
        "health": mgr.health_summary(mv.model_version),
        "pending_from_p5": [
            "metrics",
        ],
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    ev_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "docs", "evidence",
    )
    os.makedirs(ev_dir, exist_ok=True)
    day = time.strftime("%Y%m%d")
    ev_path = os.path.join(
        ev_dir, "%s_training-coordinator_import-ward-model_%s.txt" % (day, commit)
    )
    with open(ev_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(evidence, ensure_ascii=False, indent=2))
        f.write("\n")

    print("")
    print("evidence saved: %s" % ev_path)
    print("=" * 68)
    print("  Import loop OK. Confirm PENDING-FROM-P5 fields with Xianwei,")
    print("  then re-run to produce final evidence.")


if __name__ == "__main__":
    main()
