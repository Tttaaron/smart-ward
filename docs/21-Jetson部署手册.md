# Jetson Orin Nano 边缘端部署手册

> 编写：烽亮 (P6) · 2026-08-19
> 适用设备：NVIDIA Jetson Orin Nano 8GB (40 TOPS)
> 对应任务：P1 亚伦（设备与实测） + P6 烽亮（环境与模型准备）

---

## 一、部署目标

在 Jetson Orin Nano 上运行智慧病房边缘代理：

```
USB 摄像头 ──▶ YOLOv8n-pose（姿态检测）──▶ 规则融合 ──▶ MQTT 上报云端
                                           │
Qwen2.5-1.5B GGUF（语义增强）◀── llama.cpp ◀──┘
```

## 二、需要准备的硬件

| 硬件 | 说明 |
|------|------|
| Jetson Orin Nano 8GB | 开发套件 + 电源 + 散热 |
| microSD 卡 ≥64GB | 烧录 JetPack 系统 |
| USB 摄像头 | 普通 USB 摄像头即可 |
| 网线/WiFi | 连接云端 MQTT Broker |

## 三、系统准备（一次性）

### 3.1 烧录 JetPack

1. 下载 [SDK Manager](https://developer.nvidia.com/sdk-manager)（在电脑上）
2. 用 SDK Manager 给 Jetson 烧录 **JetPack 6.x**（含 Ubuntu 22.04 + CUDA 12.x）
3. 完成初始配置（用户名/密码/网络）

### 3.2 验证系统

```bash
# 确认 Jetson 系统
cat /etc/nv_tegra_release
# 确认 CUDA
nvcc --version
# 确认 GPU 算力
nvidia-smi
```

预期输出：CUDA 12.x，显存 ~7.4GB 可用（系统占用一部分）。

## 四、一键部署

### 4.1 运行部署脚本

```bash
# 下载脚本（或从仓库 edge-agent/scripts/ 拷贝）
curl -O https://raw.githubusercontent.com/Tttaaron/smart-ward/master/edge-agent/scripts/setup_jetson.sh
chmod +x setup_jetson.sh

# 执行（替换 MQTT 地址为实际云端地址）
sudo bash setup_jetson.sh --mqtt-host <云端IP>
```

脚本会完成：系统检查 → 基础依赖 → llama.cpp 编译 → 模型下载 → 代码拉取 → 配置生成。

### 4.2 手动安装（脚本失败时）

```bash
# 依赖
sudo apt install -y git cmake build-essential python3-pip python3-venv libssl-dev

# llama.cpp（CUDA 后端）
git clone https://github.com/ggerganov/llama.cpp /opt/llama.cpp
cd /opt/llama.cpp && cmake -B build -DGGML_CUDA=ON && cmake --build build -j4

# 模型（约 1GB）
mkdir -p /opt/smart-ward/models && cd /opt/smart-ward/models
curl -L -O https://hf-mirror.com/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf
curl -L -O https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n-pose.pt

# 代码
git clone https://github.com/Tttaaron/smart-ward.git /opt/smart-ward/smart-ward
cd /opt/smart-ward/smart-ward/edge-agent
python3 -m venv .venv && ./.venv/bin/pip install paho-mqtt numpy opencv-python-headless ultralytics
```

## 五、配置

配置文件：`/opt/smart-ward/smart-ward/edge-agent/.env`

```ini
WARD_ID=W-01
BED_ID=B01
EDGE_NODE_ID=EDGE-W01-B01
MQTT_BROKER=<云端IP>      # 云端 AutoDL 实例地址
MQTT_PORT=1883
CAMERA_INDEX=0            # USB 摄像头索引
YOLO_MODEL=/opt/smart-ward/models/yolov8n-pose.pt
LLM_MODEL=/opt/smart-ward/models/qwen2.5-1.5b-instruct-q4_k_m.gguf
LLAMA_CLI=/opt/llama.cpp/build/bin/llama-cli
```

## 六、启动与验证

### 6.1 启动边缘代理

```bash
cd /opt/smart-ward/smart-ward/edge-agent
source .venv/bin/activate
python -m src.main
```

### 6.2 验证清单

| 检查项 | 命令 | 预期 |
|--------|------|------|
| LLM 推理 | `llama-cli -m /opt/smart-ward/models/qwen2.5-1.5b-instruct-q4_k_m.gguf -p "你是智慧病房AI助手" -n 64` | 正常生成文本 |
| YOLO 检测 | 启动 edge-agent 后观察日志 | 出现 person keypoints 检测 |
| MQTT 连接 | 云端 `mosquitto_sub -t 'ward/#'` | 收到 observation 消息 |
| 显存占用 | `nvidia-smi` | < 1.5GB（1.5B Q4 模型） |

### 6.3 性能指标测量（P1 亚伦负责）

```bash
# TTFT（首 Token 延迟）测量脚本在仓库 edge-agent/scripts/bench_jetson.py
python bench_jetson.py --model /opt/smart-ward/models/qwen2.5-1.5b-instruct-q4_k_m.gguf
```

记录：TTFT、总延迟、峰值 RSS、生成吞吐量（对照任务书 T1 指标：TTFT<200ms，内存≤1.5GB）。

## 七、常见问题

| 问题 | 解决 |
|------|------|
| 摄像头无法打开 | `sudo usermod -aG video $USER` 后重新登录 |
| 模型下载慢 | 手动下载放到 `/opt/smart-ward/models/` |
| llama.cpp 编译慢 | 用 `-j4` 限制并行（8GB 内存受限） |
| MQTT 连接失败 | `telnet <云端IP> 1883` 测试端口可达性 |
| 显存不足 | 换 Qwen2.5-0.5B Q4（约 400MB） |
| 温度过高 | 检查风扇/散热，`sudo jetson_clocks` 提高性能 |

## 八、云端侧信息（P6 提供）

| 项目 | 值 |
|------|-----|
| 云端实例 | AutoDL RTX 4090 |
| 云端 MQTT Broker | 由 docker-compose 启动，端口 1884→1883 |
| 云端 LLM | Qwen2.5-14B vLLM（端口 8501） |
| 云端服务 | cloud-backend:8001, cloud-llm-service:8005 |

## 九、交接给亚伦

设备到货后执行顺序：
1. 烧录 JetPack 6.x（3.1 节）
2. 运行 `setup_jetson.sh`（4.1 节）
3. 配置 `.env`（第五节）
4. 启动 + 验证（第六节）
5. 测量性能指标（6.3 节）并记录到任务看板
