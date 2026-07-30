"""扩散模型服务全局配置"""

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = Path(os.getenv("MODEL_DIR", BASE_DIR / "models"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", BASE_DIR / "output"))
IMAGES_DIR = OUTPUT_DIR / "images"
LABELS_DIR = OUTPUT_DIR / "labels"
DATASETS_DIR = OUTPUT_DIR / "datasets"

# 模型 ID
CONTROLNET_MODEL = "lllyasviel/control_v11p_sd15_openpose"
BASE_MODEL = "runwayml/stable-diffusion-v1-5"
# 备选：SDXL 模型（显存充裕时启用）
# CONTROLNET_MODEL = "thibaud/controlnet-openpose-sdxl-1.0"
# BASE_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"

# 生成参数默认值
DEFAULT_IMAGE_SIZE = 640
DEFAULT_STEPS = 25
DEFAULT_GUIDANCE_SCALE = 7.5
DEFAULT_CONTROLNET_CONDITIONING_SCALE = 0.85
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
