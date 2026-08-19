#!/bin/bash
# AutoDL 受限环境启动脚本（容器内 Docker 不可用时的替代部署）
# 环境变量与 docker-compose.yml 的 diffusion-service 完全对齐
#
# 用法：
#   bash scripts/start_diffusion_autodl.sh          # 默认 8003 端口
#   PORT=8004 bash scripts/start_diffusion_autodl.sh # 自定义端口
#
# 可选环境变量（默认值与 docker-compose.yml 一致）：
#   MQTT_BROKER / MQTT_PORT / AUTO_GENERATE / GENERATION_BATCH_SIZE
#   HF_ENDPOINT / HF_HUB_DISABLE_XET
#   CONDA_PY    # conda 环境 python 路径，默认 $HOME/miniconda3/envs/diffusion/bin/python

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ── 与 docker-compose.yml 对齐的环境变量 ──
export MQTT_BROKER="${MQTT_BROKER:-localhost}"
export MQTT_PORT="${MQTT_PORT:-1883}"
export AUTO_GENERATE="${AUTO_GENERATE:-true}"
export GENERATION_BATCH_SIZE="${GENERATION_BATCH_SIZE:-4}"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export HF_HUB_DISABLE_XET="${HF_HUB_DISABLE_XET:-1}"
PORT="${PORT:-8003}"
PYTHON="${CONDA_PY:-$HOME/miniconda3/envs/diffusion/bin/python}"

if [ ! -x "$PYTHON" ]; then
    echo "[deploy] 未找到 $PYTHON，请设置 CONDA_PY 指向 diffusion 环境 python"
    exit 1
fi

# ── 启动 mosquitto（未运行时）──
if ! pgrep -x mosquitto > /dev/null 2>&1; then
    mkdir -p /mosquitto/data
    nohup mosquitto -c "$PROJECT_DIR/mqtt-broker/mosquitto.conf" > /tmp/mosquitto.log 2>&1 &
    echo "[deploy] mosquitto 已启动 (:1883)"
else
    echo "[deploy] mosquitto 已在运行"
fi

# ── 启动 diffusion-service ──
cd "$PROJECT_DIR/diffusion-service"
setsid nohup "$PYTHON" -m uvicorn app.main:app \
    --host 0.0.0.0 --port "$PORT" \
    > /tmp/diffusion.log 2>&1 < /dev/null &
echo "[deploy] diffusion-service 已启动 (:${PORT})"
echo "[deploy] 日志: /tmp/diffusion.log"
echo "[deploy] 健康检查: curl http://localhost:${PORT}/health"
