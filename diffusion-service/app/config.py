"""扩散模型服务全局配置"""

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = Path(os.getenv("MODEL_DIR", BASE_DIR / "models"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", BASE_DIR / "output"))
IMAGES_DIR = OUTPUT_DIR / "images"
LABELS_DIR = OUTPUT_DIR / "labels"
DATASETS_DIR = OUTPUT_DIR / "datasets"

# MQTT 误报回流配置
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
AUTO_GENERATE = os.getenv("AUTO_GENERATE", "true").lower() == "true"
GENERATION_BATCH_SIZE = int(os.getenv("GENERATION_BATCH_SIZE", "4"))
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "data" / "diffusion.db"))

# 视觉语义验证（VISION_ENDPOINT 为空则禁用，仅做像素级筛选）
VISION_ENDPOINT = os.getenv("VISION_ENDPOINT", "")

# 模型 ID - SDXL
CONTROLNET_MODEL = "lllyasviel/control_v11p_sd15_openpose"
BASE_MODEL = "runwayml/stable-diffusion-v1-5"

# 生成参数默认值 — 医疗场景优化
DEFAULT_WIDTH = 768
DEFAULT_HEIGHT = 768
DEFAULT_STEPS = 28
DEFAULT_GUIDANCE_SCALE = 5.5
DEFAULT_CONTROLNET_CONDITIONING_SCALE = 1.1
DEFAULT_BATCH_COUNT = 4
DEFAULT_VARIANTS_PER_TEMPLATE = 3

# 质量筛选阈值
MIN_SHARPNESS_SCORE = 50.0       # Laplacian 方差最小值
MAX_BLUR_SCORE = 300.0           # Laplacian 方差超过此值判定为噪声
MIN_BRIGHTNESS = 20              # 图像平均亮度最小值
MAX_BRIGHTNESS = 235             # 图像平均亮度最大值

# 模型缓存配置
MODEL_CACHE_DIR = MODEL_DIR / "huggingface"
os.environ.setdefault("HF_HOME", str(MODEL_CACHE_DIR))
os.environ.setdefault("TORCH_HOME", str(MODEL_DIR / "torch"))
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")


def ensure_dirs():
    for d in [MODEL_DIR, OUTPUT_DIR, IMAGES_DIR, LABELS_DIR, DATASETS_DIR]:
        d.mkdir(parents=True, exist_ok=True)
