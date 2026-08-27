#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/autodl-tmp/smart-ward-master}"
QWEN_ROOT="${QWEN_ROOT:-/root/autodl-tmp/qwen}"
PYTHON="${PYTHON:-$QWEN_ROOT/venv/bin/python}"
EVAL_DIR="$PROJECT_ROOT/datasets/ward-nlu-500-v1/distillation/general-retention-v1"
SCRIPT_DIR="$PROJECT_ROOT/edge-agent/distillation"

cd "$PROJECT_ROOT"

"$PYTHON" "$SCRIPT_DIR/rescore_general_retention_v2.py" \
  --benchmark "$EVAL_DIR/benchmark.jsonl" \
  --baseline-samples "$EVAL_DIR/general-baseline-1.5b-full.samples.jsonl" \
  --distilled-samples "$EVAL_DIR/general-distilled-1.5b-full.samples.jsonl" \
  --output-dir "$EVAL_DIR" \
  --threshold 0.80

"$PYTHON" "$SCRIPT_DIR/audit_domain_content_v2.py" \
  --events "$PROJECT_ROOT/datasets/ward-nlu-500-v1/test-v1.0.0.jsonl" \
  --prompts "$PROJECT_ROOT/datasets/ward-nlu-500-v1/qwen-sft-test-v1.0.0.jsonl" \
  --report "$EVAL_DIR/domain-distilled-1.5b-full.json" \
  --output-dir "$EVAL_DIR" \
  --audit-count 30 \
  --seed 20260819

echo
echo "Corrected reports:"
echo "  $EVAL_DIR/general-comparison-full-v2.md"
echo "  $EVAL_DIR/domain-content-analysis-v2.md"
echo "  $EVAL_DIR/domain-human-audit-30-v2.csv"
