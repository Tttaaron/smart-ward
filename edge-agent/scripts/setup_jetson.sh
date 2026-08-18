#!/bin/bash
# ============================================================
# Jetson Orin Nano 边缘端一键部署脚本
# 智慧病房 smart-ward · 云端准备 / 边缘执行
# 作者: 烽亮 (P6) · 2026-08-19
#
# 用途: 在 Jetson Orin Nano 8GB 上部署
#       1. 系统环境检查 (JetPack/CUDA)
#       2. llama.cpp (运行 Qwen2.5-1.5B GGUF)
#       3. edge-agent 代码 + Python 依赖
#       4. 模型文件 (GGUF + YOLOv8n-pose)
#       5. MQTT 配置
#       6. 启动 edge-agent
#
# 用法: sudo bash setup_jetson.sh [--mqtt-host 192.168.1.100] [--camera 0]
# ============================================================
set -e

# ─── 配置 ───
MQTT_HOST="${MQTT_HOST:-127.0.0.1}"          # 云端 MQTT Broker 地址
MQTT_PORT="${MQTT_PORT:-1883}"
WARD_ID="${WARD_ID:-W-01}"
EDGE_NODE_ID="${EDGE_NODE_ID:-EDGE-W01-B01}"
BED_ID="${BED_ID:-B01}"
CAMERA_INDEX="${CAMERA_INDEX:-0}"            # USB 摄像头索引
REPO_URL="https://github.com/Tttaaron/smart-ward.git"
MODEL_BASE="https://hf-mirror.com/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main"
GGUF_MODEL="qwen2.5-1.5b-instruct-q4_k_m.gguf"
WORK_DIR="/opt/smart-ward"

echo "=============================================="
echo " 智慧病房 Jetson Orin Nano 边缘端部署"
echo "=============================================="

# ─── 1. 系统检查 ───
echo ""
echo "[1/6] 系统环境检查..."
if [ ! -f /etc/nv_tegra_release ]; then
    echo "  ⚠️  未检测到 NVIDIA Jetson 系统 (JetPack)。"
    echo "     此脚本针对 Jetson Orin Nano 8GB 编写，可在 x86 上以模拟模式运行。"
    read -p "  继续? [y/N] " ans
    [[ "$ans" == "y" || "$ans" == "Y" ]] || exit 1
else
    echo "  ✓ JetPack 系统确认: $(cat /etc/nv_tegra_release | cut -d' ' -f1-2)"
fi

if command -v nvcc >/dev/null 2>&1; then
    echo "  ✓ CUDA: $(nvcc --version | grep release | awk '{print $6}')"
elif [ -d /usr/local/cuda/bin ]; then
    export PATH=/usr/local/cuda/bin:$PATH
    echo "  ✓ CUDA: $(nvcc --version | grep release | awk '{print $6}')"
else
    echo "  ⚠️  未找到 CUDA，尝试通过 JetPack 环境"
fi

# ─── 2. 基础依赖 ───
echo ""
echo "[2/6] 安装基础依赖..."
apt-get update -y
apt-get install -y git curl cmake build-essential python3-pip python3-venv \
    libssl-dev pkg-config libgl1-mesa-glx

# ─── 3. llama.cpp ───
echo ""
echo "[3/6] 编译 llama.cpp..."
if [ ! -d /opt/llama.cpp ]; then
    git clone https://github.com/ggerganov/llama.cpp /opt/llama.cpp
    cd /opt/llama.cpp
    # Jetson 用 CUDA 后端
    cmake -B build -DGGML_CUDA=ON -DCMAKE_BUILD_TYPE=Release
    cmake --build build --config Release -j $(nproc)
    echo "  ✓ llama.cpp 编译完成"
else
    echo "  ✓ llama.cpp 已存在"
fi
LLAMA_CLI=/opt/llama.cpp/build/bin/llama-cli

# ─── 4. 模型文件 ───
echo ""
echo "[4/6] 下载模型文件..."
mkdir -p $WORK_DIR/models
cd $WORK_DIR/models

# Qwen2.5-1.5B GGUF (约 1GB)
if [ ! -f "$GGUF_MODEL" ]; then
    echo "  下载 $GGUF_MODEL ..."
    curl -L -o "$GGUF_MODEL" "$MODEL_BASE/$GGUF_MODEL"
    echo "  ✓ GGUF 模型下载完成"
else
    echo "  ✓ GGUF 模型已存在"
fi

# YOLOv8n-pose 权重
if [ ! -f "yolov8n-pose.pt" ]; then
    echo "  下载 yolov8n-pose.pt ..."
    curl -L -o yolov8n-pose.pt "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n-pose.pt"
    echo "  ✓ YOLO 权重下载完成"
else
    echo "  ✓ YOLO 权重已存在"
fi

# ─── 5. edge-agent 代码 ───
echo ""
echo "[5/6] 拉取 edge-agent 代码..."
if [ ! -d $WORK_DIR/smart-ward ]; then
    git clone $REPO_URL $WORK_DIR/smart-ward
else
    cd $WORK_DIR/smart-ward && git pull
fi

# Python 环境
cd $WORK_DIR/smart-ward/edge-agent
if [ ! -d .venv ]; then
    python3 -m venv .venv
    ./.venv/bin/pip install -U pip
    ./.venv/bin/pip install -r requirements.txt 2>/dev/null || \
    ./.venv/bin/pip install paho-mqtt numpy opencv-python-headless ultralytics
    echo "  ✓ Python 依赖安装完成"
fi

# ─── 6. 配置与启动 ───
echo ""
echo "[6/6] 生成配置文件..."
cat > $WORK_DIR/smart-ward/edge-agent/.env << EOF
WARD_ID=$WARD_ID
BED_ID=$BED_ID
EDGE_NODE_ID=$EDGE_NODE_ID
MQTT_BROKER=$MQTT_HOST
MQTT_PORT=$MQTT_PORT
CAMERA_INDEX=$CAMERA_INDEX
YOLO_MODEL=$WORK_DIR/models/yolov8n-pose.pt
LLM_MODEL=$WORK_DIR/models/$GGUF_MODEL
LLAMA_CLI=$LLAMA_CLI
EOF

echo ""
echo "=============================================="
echo " 部署完成!"
echo "=============================================="
echo ""
echo "  配置: $WORK_DIR/smart-ward/edge-agent/.env"
echo "  模型: $WORK_DIR/models/"
echo ""
echo "  启动边缘代理:"
echo "    cd $WORK_DIR/smart-ward/edge-agent"
echo "    source .venv/bin/activate"
echo "    python -m src.main"
echo ""
echo "  测试 LLM (独立运行):"
echo "    $LLAMA_CLI -m $WORK_DIR/models/$GGUF_MODEL -p \"你是智慧病房AI助手\" -n 64"
echo ""
echo "  监控:"
echo "    watch -n 2 'nvidia-smi | head -12'"
echo "    tail -f /var/log/syslog | grep edge-agent"
echo ""
echo "  常见问题:"
echo "    - USB 摄像头权限: sudo usermod -aG video \$USER"
echo "    - MQTT 连不上: 检查 $MQTT_HOST:$MQTT_PORT 可达"
echo "    - 模型下载慢: 手动下载后放入 $WORK_DIR/models/"
echo "=============================================="
