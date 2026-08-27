#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-smoke}"
PROJECT_ROOT="${PROJECT_ROOT:-/root/autodl-tmp/smart-ward-master}"
QWEN_ROOT="${QWEN_ROOT:-/root/autodl-tmp/qwen}"
PYTHON="${PYTHON:-$QWEN_ROOT/venv/bin/python}"
EVAL_DIR="$PROJECT_ROOT/datasets/ward-nlu-500-v1/distillation/general-retention-v1"
BENCHMARK="$EVAL_DIR/benchmark.jsonl"
GENERAL_SCRIPT="$PROJECT_ROOT/edge-agent/distillation/evaluate_general_retention.py"
DOMAIN_SCRIPT="$PROJECT_ROOT/edge-agent/distillation/evaluate_model.py"
DOMAIN_INPUT="$PROJECT_ROOT/datasets/ward-nlu-500-v1/qwen-sft-test-v1.0.0.jsonl"

case "$MODE" in
  smoke)
    PER_TASK=20
    LIMIT_ARGUMENTS=(--limit-per-task 3)
    DOMAIN_LIMIT_ARGUMENTS=(--limit 6)
    ;;
  full)
    PER_TASK=200
    LIMIT_ARGUMENTS=()
    DOMAIN_LIMIT_ARGUMENTS=()
    ;;
  *)
    echo "Usage: bash run_retention_eval.sh {smoke|full}" >&2
    exit 2
    ;;
esac

mkdir -p "$EVAL_DIR"
cd "$PROJECT_ROOT"

"$PYTHON" "$GENERAL_SCRIPT" prepare \
  --output "$BENCHMARK" \
  --cache-dir "$EVAL_DIR/cache" \
  --per-task "$PER_TASK" \
  --seed 20260818

qwen-start 1.5b
"$PYTHON" "$DOMAIN_SCRIPT" \
  --input "$DOMAIN_INPUT" \
  --output "$EVAL_DIR/domain-baseline-1.5b-$MODE.json" \
  --model qwen2.5-1.5b \
  --label baseline-1.5b \
  "${DOMAIN_LIMIT_ARGUMENTS[@]}"
"$PYTHON" "$GENERAL_SCRIPT" run \
  --benchmark "$BENCHMARK" \
  --output "$EVAL_DIR/general-baseline-1.5b-$MODE.json" \
  --model qwen2.5-1.5b \
  --label baseline-1.5b \
  --workers 6 \
  "${LIMIT_ARGUMENTS[@]}"

qwen-start ward
"$PYTHON" "$DOMAIN_SCRIPT" \
  --input "$DOMAIN_INPUT" \
  --output "$EVAL_DIR/domain-distilled-1.5b-$MODE.json" \
  --model qwen2.5-1.5b-ward \
  --label distilled-1.5b-v2 \
  "${DOMAIN_LIMIT_ARGUMENTS[@]}"
"$PYTHON" "$GENERAL_SCRIPT" run \
  --benchmark "$BENCHMARK" \
  --output "$EVAL_DIR/general-distilled-1.5b-$MODE.json" \
  --model qwen2.5-1.5b-ward \
  --label distilled-1.5b-v2 \
  --workers 6 \
  "${LIMIT_ARGUMENTS[@]}"

"$PYTHON" "$GENERAL_SCRIPT" compare \
  --baseline "$EVAL_DIR/general-baseline-1.5b-$MODE.json" \
  --distilled "$EVAL_DIR/general-distilled-1.5b-$MODE.json" \
  --output "$EVAL_DIR/general-comparison-$MODE.json" \
  --threshold 0.80

echo
echo "Finished. Reports are in: $EVAL_DIR"
echo "Main table: $EVAL_DIR/general-comparison-$MODE.md"
qwen-status
