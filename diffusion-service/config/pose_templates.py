"""姿态模板库 - COCO 17 关键点模板与 SD 提示词

COCO 17 关键点定义 (归一化坐标 0~1):
    0:鼻 1:左眼 2:右眼 3:左耳 4:右耳
    5:左肩 6:右肩 7:左肘 8:右肘 9:左腕 10:右腕
    11:左髋 12:右髋 13:左膝 14:右膝 15:左踝 16:右踝

机位约定：墙装侧视（摄像头在病床侧面墙上，略高于床）
不可见点表示为 [0, 0]
"""

from dataclasses import dataclass
from typing import Dict, List

H = 0.11  # 头高（归一化），兼容旧引用


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
    "masterpiece, best quality, 8k, highly detailed, "
    "professional medical photography, photorealistic, "
    "cinematic lighting, clean hospital ward, solo patient"
)

WARD_NEGATIVE_PROMPT = (
    "low quality, worst quality, blurry, distorted anatomy, "
    "bad anatomy, extra limbs, missing limbs, extra fingers, "
    "mutated hands, poorly drawn face, deformed body, "
    "cartoon, painting, illustration, text, watermark, "
    "multiple people, duplicate, two people, three people, "
    "woman, female, girl, lady, feminine"
)


def face(head_x: float, head_y: float, rot: float = 0) -> List[List[float]]:
    """生成自然分布的面部 5 点（rot 为旋转角度，度）：
    rot=0: 站立/坐姿，眼耳连线水平，与垂直的鼻-颈线垂直。
    rot=90: 平躺侧视，眼耳连线竖直，与水平的鼻-颈线垂直。"""
    import math
    rad = math.radians(rot)
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    def _rot(dx: float, dy: float) -> List[float]:
        return [head_x + dx * cos_a - dy * sin_a,
                head_y + dx * sin_a + dy * cos_a]

    return [
        [head_x, head_y],
        _rot(-0.25 * H, -0.15 * H),
        _rot(0.25 * H, -0.15 * H),
        _rot(-0.5 * H, -0.15 * H),
        _rot(0.5 * H, -0.15 * H),
    ]


# ─── 1. 跌倒 (fall_suspected) — 侧视 ───

FALL_KEYPOINTS_VARIANTS = [
    {   # 侧身跌倒
        "label": "侧身跌倒",
        "keypoints": [
            [0.1803, 0.3057], [0.1493, 0.2808], [0.1368, 0.3150],
            [0.1601, 0.2575], [0.1275, 0.3321],
            [0.2363, 0.2777], [0.2223, 0.3741],
            [0.2612, 0.3958], [0.2068, 0.4285],
            [0.1819, 0.4813], [0.0917, 0.3927],
            [0.4478, 0.4005], [0.4353, 0.3523],
            [0.5846, 0.4223], [0.6048, 0.3414],
            [0.7432, 0.3290], [0.7711, 0.2730],
        ],
        "bbox": [0.40, 0.33, 0.55, 0.28],
    },
    {   # 仰面跌倒
        "label": "仰面跌倒",
        "keypoints": [
            [0.1772, 0.2621], [0.1477, 0.2435], [0.1337, 0.2808],
            [0.1788, 0.2217], [0.1337, 0.3103],
            [0.2581, 0.2481], [0.2301, 0.3103],
            [0.3794, 0.2030], [0.2923, 0.3850],
            [0.4757, 0.2015], [0.3980, 0.3803],
            [0.4897, 0.2295], [0.4804, 0.2917],
            [0.6390, 0.1782], [0.6452, 0.2792],
            [0.7991, 0.2155], [0.8131, 0.2792],
        ],
        "bbox": [0.45, 0.26, 0.50, 0.22],
    },
    {   # 俯卧跌倒（面部 0/4 不可见）
        "label": "俯卧跌倒",
        "keypoints": [
            [0.0000, 0.0000], [0.1322, 0.3321], [0.1555, 0.2963],
            [0.1244, 0.3507], [0.0000, 0.0000],
            [0.2192, 0.3989], [0.2472, 0.3057],
            [0.1819, 0.4798], [0.2425, 0.2621],
            [0.0871, 0.4207], [0.1601, 0.2419],
            [0.4167, 0.4083], [0.4384, 0.3134],
            [0.5784, 0.4083], [0.5877, 0.3181],
            [0.7525, 0.4036], [0.7525, 0.3197],
        ],
        "bbox": [0.42, 0.35, 0.55, 0.22],
    },
]

# ─── 2. 坠床预警 (fall_prediction) — 床沿躺姿，侧视 ───

FALL_PREDICTION_VARIANTS = [
    {
        "label": "床沿躺姿",
        "keypoints": [
            [0.2643, 0.4129], [0.2270, 0.3974], [0.2161, 0.4223],
            [0.0000, 0.0000], [0.2052, 0.4658],
            [0.3358, 0.3865], [0.3094, 0.4705],
            [0.3638, 0.3445], [0.2799, 0.5575],
            [0.4649, 0.3445], [0.2799, 0.6586],
            [0.5022, 0.3896], [0.4804, 0.4767],
            [0.6374, 0.3943], [0.6110, 0.5498],
            [0.7836, 0.4409], [0.6623, 0.6772],
        ],
        "bbox": [0.45, 0.48, 0.42, 0.35],
    },
]

# ─── 3. 抽搐检测 (seizure) — 床上发作，侧视 ───

SEIZURE_VARIANTS = [
    {
        "label": "抽搐发作",
        "keypoints": [
            [0.2301, 0.3445], [0.2114, 0.3228], [0.1928, 0.3539],
            [0.0000, 0.0000], [0.1912, 0.3787],
            [0.2627, 0.3290], [0.2830, 0.3787],
            [0.2083, 0.2590], [0.4493, 0.3912],
            [0.1182, 0.2357], [0.6048, 0.3850],
            [0.5177, 0.3259], [0.4944, 0.3710],
            [0.6297, 0.2310], [0.6654, 0.3663],
            [0.7556, 0.3150], [0.8722, 0.3741],
        ],
        "bbox": [0.50, 0.32, 0.62, 0.22],
    },
]

# ─── 4. 长时间静止 (long_still) — 侧视 ───

LONG_STILL_VARIANTS = [
    {
        "label": "仰卧不动",
        "keypoints": [
            [0.1741, 0.1502], [0.1461, 0.1533], [0.1430, 0.1688],
            [0.0000, 0.0000], [0.1275, 0.2108],
            [0.2114, 0.1735], [0.2083, 0.2155],
            [0.3607, 0.1673], [0.3343, 0.2357],
            [0.4851, 0.1549], [0.4975, 0.2357],
            [0.4851, 0.1720], [0.4866, 0.2077],
            [0.6748, 0.1735], [0.6763, 0.2124],
            [0.8613, 0.1704], [0.8629, 0.2046],
        ],
        "bbox": [0.45, 0.20, 0.60, 0.10],
    },
]

# ─── 5. 异常体态 - 蜷缩 (curled) — 侧视 ───

CURLED_VARIANTS = [
    {
        "label": "胎儿位蜷缩",
        "keypoints": [
            [0.3156, 0.1502], [0.2814, 0.1300], [0.2736, 0.1595],
            [0.2954, 0.1175], [0.2767, 0.1797],
            [0.3716, 0.1082], [0.3607, 0.1937],
            [0.4073, 0.1797], [0.4369, 0.1984],
            [0.3187, 0.2139], [0.3312, 0.2435],
            [0.5255, 0.1129], [0.5162, 0.1968],
            [0.4757, 0.1797], [0.4493, 0.2466],
            [0.5861, 0.1549], [0.5644, 0.2186],
        ],
        "bbox": [0.42, 0.18, 0.30, 0.16],
    },
]

# ─── 6. 异常体态 - 前倾 (leaning) — 侧视，呼吸困难三脚架体位 ───

LEANING_VARIANTS = [
    {
        "label": "坐姿前倾",
        "keypoints": [
            [0.5659, 0.2108], [0.0000, 0.0000], [0.5535, 0.1828],
            [0.0000, 0.0000], [0.5224, 0.1859],
            [0.5022, 0.2715], [0.5037, 0.3041],
            [0.5177, 0.3476], [0.4882, 0.3850],
            [0.6126, 0.3974], [0.6032, 0.4471],
            [0.0000, 0.0000], [0.4726, 0.4596],
            [0.6157, 0.4160], [0.6095, 0.4580],
            [0.7929, 0.4300], [0.7867, 0.4674],
        ],
        "bbox": [0.55, 0.34, 0.38, 0.30],
    },
]

# ─── 7. 异常体态 - 抓胸 (grabbing_chest) — 侧视，心绞痛/心梗 ───

GRABBING_CHEST_VARIANTS = [
    {
        "label": "双手捂胸",
        "keypoints": [
            [0.1866, 0.3088], [0.1710, 0.2839], [0.1617, 0.3274],
            [0.0000, 0.0000], [0.1415, 0.3570],
            [0.2332, 0.3570], [0.2379, 0.3290],
            [0.3669, 0.4036], [0.3716, 0.2870],
            [0.2923, 0.3414], [0.2923, 0.3321],
            [0.4664, 0.3725], [0.4726, 0.3399],
            [0.6405, 0.3756], [0.6374, 0.3445],
            [0.7991, 0.3818], [0.7960, 0.3383],
        ],
        "bbox": [0.50, 0.36, 0.45, 0.14],
    },
]

# ─── 8. 门区离开 (door_departure) — 侧视站立 ───

DOOR_DEPARTURE_VARIANTS = [
    {
        "label": "侧视站立",
        "keypoints": [
            [0.6141, 0.1113], [0.5861, 0.0942], [0.6079, 0.0740],
            [0.5519, 0.1051], [0.0000, 0.0000],
            [0.5690, 0.2108], [0.6141, 0.1735],
            [0.5566, 0.3539], [0.6297, 0.3212],
            [0.5752, 0.5358], [0.6623, 0.4829],
            [0.5846, 0.4409], [0.6312, 0.4036],
            [0.5955, 0.6182], [0.6530, 0.5979],
            [0.5861, 0.8016], [0.6545, 0.7938],
        ],
        "bbox": [0.60, 0.40, 0.20, 0.75],
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
    "fall_suspected": "a patient in blue hospital gown fallen on floor beside a bed",
    "fall_prediction": "a patient in blue hospital gown lying at the edge of hospital bed, body sliding off, gripping bed rail",
    "seizure": "a patient in blue hospital gown on hospital bed, convulsing, arms twisted, back arched",
    "long_still": "a patient in blue hospital gown lying stiff and motionless on bed, eyes open",
    "abnormal_posture": "a patient in blue hospital gown in distress, abnormal body posture, hospital ward",
    "door_departure": "a patient in blue hospital gown standing at hospital doorway, side view, hand on doorframe",
}

NIGHT_PROMPT_SUFFIX = (
    ", dim night light, dark hospital room, "
    "night vision camera, low light surveillance"
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
