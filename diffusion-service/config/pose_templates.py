"""姿态模板库 - 13 类安全事件的 COCO 17 关键点模板与 SD 提示词

COCO 17 关键点定义 (归一化坐标 0~1):
    0:鼻 1:左眼 2:右眼 3:左耳 4:右耳
    5:左肩 6:右肩 7:左肘 8:右肘 9:左腕 10:右腕
    11:左髋 12:右髋 13:左膝 14:右膝 15:左踝 16:右踝
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class PoseTemplate:
    """单组姿态模板"""
    name: str
    chinese_name: str
    event_type: str
    description: str
    keypoints: List[List[float]]
    bbox: List[float]
    positive_prompt: str
    negative_prompt: str = ""
    category_id: int = 0


# ─── 公共提示词 ───

WARD_BASE_PROMPT = (
    "hospital room, patient in blue gown, medical bed, "
    "clinical setting, security camera view, sharp photo"
)

WARD_NEGATIVE_PROMPT = (
    "nude, naked, exposed, gore, blood, wound, surgery, "
    "multiple people, crowd, text, watermark, signature, "
    "cartoon, illustration, deformed body, bad anatomy, "
    "extra limbs, blurry, low quality, worst quality"
)

# ─── 1. 跌倒 (fall_suspected) ───

FALL_KEYPOINTS_VARIANTS = [
    {
        "label": "仰面跌倒",
        "keypoints": [
            [0.35, 0.55], [0.33, 0.54], [0.37, 0.54],
            [0.31, 0.55], [0.39, 0.55],
            [0.28, 0.65], [0.42, 0.65],
            [0.22, 0.72], [0.50, 0.72],
            [0.18, 0.78], [0.55, 0.78],
            [0.30, 0.50], [0.40, 0.50],
            [0.28, 0.38], [0.42, 0.38],
            [0.26, 0.28], [0.44, 0.28],
        ],
        "bbox": [0.35, 0.42, 0.40, 0.55],
    },
    {
        "label": "侧身跌倒",
        "keypoints": [
            [0.40, 0.50], [0.39, 0.49], [0.41, 0.49],
            [0.38, 0.50], [0.42, 0.50],
            [0.33, 0.58], [0.47, 0.58],
            [0.28, 0.65], [0.52, 0.62],
            [0.24, 0.70], [0.56, 0.66],
            [0.35, 0.45], [0.45, 0.45],
            [0.36, 0.35], [0.44, 0.35],
            [0.35, 0.25], [0.45, 0.25],
        ],
        "bbox": [0.40, 0.38, 0.35, 0.50],
    },
    {
        "label": "俯面跌倒",
        "keypoints": [
            [0.50, 0.30], [0.48, 0.29], [0.52, 0.29],
            [0.46, 0.30], [0.54, 0.30],
            [0.42, 0.40], [0.58, 0.40],
            [0.38, 0.48], [0.62, 0.48],
            [0.35, 0.55], [0.65, 0.55],
            [0.44, 0.35], [0.56, 0.35],
            [0.46, 0.25], [0.54, 0.25],
            [0.47, 0.18], [0.53, 0.18],
        ],
        "bbox": [0.50, 0.30, 0.35, 0.45],
    },
]

# ─── 2. 坠床预警 (fall_prediction) ───

FALL_PREDICTION_VARIANTS = [
    {
        "label": "床沿不稳坐姿",
        "keypoints": [
            [0.50, 0.30], [0.48, 0.28], [0.52, 0.28],
            [0.46, 0.30], [0.54, 0.30],
            [0.35, 0.42], [0.65, 0.42],
            [0.30, 0.50], [0.70, 0.50],
            [0.26, 0.55], [0.74, 0.55],
            [0.42, 0.60], [0.58, 0.60],
            [0.40, 0.78], [0.60, 0.78],
            [0.38, 0.92], [0.62, 0.92],
        ],
        "bbox": [0.50, 0.45, 0.50, 0.65],
    },
    {
        "label": "床沿侧倾坐姿",
        "keypoints": [
            [0.55, 0.28], [0.53, 0.26], [0.57, 0.26],
            [0.51, 0.28], [0.59, 0.28],
            [0.45, 0.40], [0.60, 0.38],
            [0.40, 0.48], [0.65, 0.45],
            [0.36, 0.52], [0.70, 0.48],
            [0.48, 0.58], [0.58, 0.56],
            [0.46, 0.76], [0.60, 0.74],
            [0.44, 0.90], [0.62, 0.88],
        ],
        "bbox": [0.52, 0.43, 0.38, 0.65],
    },
]

# ─── 3. 抽搐检测 (seizure) ───

SEIZURE_VARIANTS = [
    {
        "label": "抽搐发作",
        "keypoints": [
            [0.50, 0.25], [0.47, 0.23], [0.53, 0.23],
            [0.45, 0.25], [0.55, 0.25],
            [0.40, 0.42], [0.60, 0.38],
            [0.30, 0.52], [0.70, 0.48],
            [0.20, 0.58], [0.80, 0.55],
            [0.44, 0.50], [0.56, 0.48],
            [0.42, 0.70], [0.58, 0.68],
            [0.40, 0.85], [0.60, 0.83],
        ],
        "bbox": [0.50, 0.45, 0.62, 0.62],
    },
    {
        "label": "抽搐扭曲",
        "keypoints": [
            [0.50, 0.22], [0.47, 0.20], [0.53, 0.20],
            [0.45, 0.22], [0.55, 0.22],
            [0.35, 0.38], [0.65, 0.42],
            [0.25, 0.50], [0.75, 0.52],
            [0.18, 0.55], [0.82, 0.58],
            [0.40, 0.48], [0.60, 0.50],
            [0.38, 0.68], [0.62, 0.70],
            [0.35, 0.85], [0.65, 0.87],
        ],
        "bbox": [0.50, 0.43, 0.65, 0.65],
    },
]

# ─── 4. 长时间静止 (long_still) ───

LONG_STILL_VARIANTS = [
    {
        "label": "仰卧不动",
        "keypoints": [
            [0.50, 0.15], [0.48, 0.13], [0.52, 0.13],
            [0.46, 0.15], [0.54, 0.15],
            [0.35, 0.28], [0.65, 0.28],
            [0.32, 0.42], [0.68, 0.42],
            [0.30, 0.55], [0.70, 0.55],
            [0.38, 0.45], [0.62, 0.45],
            [0.40, 0.68], [0.60, 0.68],
            [0.42, 0.88], [0.58, 0.88],
        ],
        "bbox": [0.50, 0.38, 0.42, 0.78],
    },
]

# ─── 5. 异常体态 - 蜷缩 (curled) ───

CURLED_VARIANTS = [
    {
        "label": "胎儿位蜷缩",
        "keypoints": [
            [0.50, 0.35], [0.48, 0.33], [0.52, 0.33],
            [0.47, 0.35], [0.53, 0.35],
            [0.40, 0.42], [0.60, 0.42],
            [0.38, 0.55], [0.62, 0.55],
            [0.45, 0.60], [0.55, 0.60],
            [0.42, 0.52], [0.58, 0.52],
            [0.45, 0.60], [0.55, 0.60],
            [0.46, 0.68], [0.54, 0.68],
        ],
        "bbox": [0.50, 0.48, 0.28, 0.38],
    },
]

# ─── 6. 异常体态 - 前倾 (leaning) ───

LEANING_VARIANTS = [
    {
        "label": "坐姿前倾",
        "keypoints": [
            [0.58, 0.32], [0.56, 0.30], [0.60, 0.30],
            [0.54, 0.32], [0.62, 0.32],
            [0.50, 0.44], [0.66, 0.44],
            [0.46, 0.52], [0.70, 0.52],
            [0.42, 0.58], [0.74, 0.58],
            [0.52, 0.56], [0.64, 0.56],
            [0.50, 0.74], [0.66, 0.74],
            [0.48, 0.90], [0.68, 0.90],
        ],
        "bbox": [0.58, 0.52, 0.36, 0.62],
    },
]

# ─── 7. 异常体态 - 抓胸 (grabbing_chest) ───

GRABBING_CHEST_VARIANTS = [
    {
        "label": "双手抓胸",
        "keypoints": [
            [0.50, 0.22], [0.47, 0.20], [0.53, 0.20],
            [0.45, 0.22], [0.55, 0.22],
            [0.38, 0.35], [0.62, 0.35],
            [0.42, 0.40], [0.58, 0.40],
            [0.44, 0.38], [0.56, 0.38],
            [0.40, 0.52], [0.60, 0.52],
            [0.42, 0.72], [0.58, 0.72],
            [0.44, 0.90], [0.56, 0.90],
        ],
        "bbox": [0.50, 0.42, 0.28, 0.72],
    },
]

# ─── 8. 门区离开 (door_departure) ───

DOOR_DEPARTURE_VARIANTS = [
    {
        "label": "站立门区",
        "keypoints": [
            [0.80, 0.12], [0.78, 0.10], [0.82, 0.10],
            [0.77, 0.12], [0.83, 0.12],
            [0.73, 0.22], [0.87, 0.22],
            [0.70, 0.32], [0.90, 0.32],
            [0.68, 0.40], [0.92, 0.40],
            [0.74, 0.45], [0.86, 0.45],
            [0.72, 0.68], [0.88, 0.68],
            [0.70, 0.90], [0.90, 0.90],
        ],
        "bbox": [0.80, 0.42, 0.28, 0.82],
    },
]

# ─── 事件 -> 模板映射 ───

EVENT_TEMPLATE_MAP: Dict[str, List[dict]] = {
    "fall_suspected": FALL_KEYPOINTS_VARIANTS,
    "fall_prediction": FALL_PREDICTION_VARIANTS,
    "seizure": SEIZURE_VARIANTS,
    "long_still": LONG_STILL_VARIANTS,
    "abnormal_posture": CURLED_VARIANTS + LEANING_VARIANTS + GRABBING_CHEST_VARIANTS,
    "door_departure": DOOR_DEPARTURE_VARIANTS,
}

# ─── 事件 -> SD 提示词 ───

EVENT_PROMPTS: Dict[str, str] = {
    "fall_suspected": (
        "elderly patient fallen on floor beside hospital bed, "
        "lying on ground, arms spread, overhead security camera"
    ),
    "fall_prediction": (
        "patient sitting on bed edge, body tilted, unstable, "
        "about to fall, gripping bed rail, wall camera view"
    ),
    "seizure": (
        "patient on bed having seizure, arms twisted, "
        "legs contorted, body rigid, tangled sheets, overhead view"
    ),
    "long_still": (
        "patient lying motionless on bed, flat on back, "
        "arms at sides, unconscious appearance, ceiling camera"
    ),
    "abnormal_posture": (
        "patient curled in fetal position on bed, "
        "knees to chest, in pain, hospital gown, wall camera"
    ),
    "door_departure": (
        "elderly patient standing at open door, leaving room, "
        "confused, hospital gown, wide security camera view"
    ),
}

NIGHT_PROMPT_SUFFIX = (
    ", dim night light, dark room, night vision camera, "
    "low light surveillance photo"
)

EVENT_CATEGORY_IDS: Dict[str, int] = {
    "fall_suspected": 0,
    "fall_prediction": 1,
    "seizure": 2,
    "long_still": 3,
    "abnormal_posture": 4,
    "door_departure": 5,
}

ALL_EVENT_TYPES = list(EVENT_TEMPLATE_MAP.keys())


def get_templates_for_event(event_type: str) -> List[dict]:
    return EVENT_TEMPLATE_MAP.get(event_type, [])


def get_prompt_for_event(event_type: str, night_mode: bool = False) -> str:
    suffix = NIGHT_PROMPT_SUFFIX if night_mode else ""
    event_prompt = EVENT_PROMPTS.get(event_type, "patient in hospital bed")
    return f"{WARD_BASE_PROMPT}, {event_prompt}{suffix}"
