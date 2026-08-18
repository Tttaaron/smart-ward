"""核心生成器 - Stable Diffusion + ControlNet OpenPose 推理管道

生成流程:
    1. 加载 SD 1.5 + ControlNet OpenPose 模型
    2. 根据姿态模板生成 OpenPose 骨架图作为条件输入
    3. 使用 pose-conditioned SD 生成病房场景图像
    4. 返回 PIL Image + 元数据
"""

import gc
import random
import time
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
from PIL import Image, ImageDraw

from .config import (
    BASE_MODEL,
    CONTROLNET_MODEL,
    MODEL_CACHE_DIR,
    DEFAULT_WIDTH,
    DEFAULT_HEIGHT,
    DEFAULT_STEPS,
    DEFAULT_GUIDANCE_SCALE,
    DEFAULT_CONTROLNET_CONDITIONING_SCALE,
    DEFAULT_BATCH_COUNT,
)
from config.pose_templates import (
    get_templates_for_event,
    get_prompt_for_event,
    WARD_NEGATIVE_PROMPT,
)

logger = logging.getLogger(__name__)

# COCO 17 关键点骨架连线定义
SKELETON_EDGES = [
    (0, 1), (0, 2), (1, 3), (2, 4),  # 面部
    (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),  # 上肢
    (5, 11), (6, 12), (11, 12),  # 躯干
    (11, 13), (13, 15), (12, 14), (14, 16),  # 下肢
]


class DiffusionGenerator:
    """Stable Diffusion + ControlNet 生成器"""

    def __init__(self, device: str = "cuda", use_fp16: bool = True):
        self.device = device
        self.use_fp16 = use_fp16 and device == "cuda"
        self.pipe = None
        self.controlnet = None
        self._loaded = False

    def load_models(self) -> None:
        """加载 SD + ControlNet 模型"""
        if self._loaded:
            return

        logger.info("Loading SD 1.5 + ControlNet models...")
        t0 = time.time()

        from diffusers import (
            StableDiffusionControlNetPipeline,
            ControlNetModel,
            DPMSolverMultistepScheduler,
        )

        torch_dtype = torch.float16 if self.use_fp16 else torch.float32

        self.controlnet = ControlNetModel.from_pretrained(
            CONTROLNET_MODEL,
            torch_dtype=torch_dtype,
            cache_dir=str(MODEL_CACHE_DIR),
            use_safetensors=True,
        )

        self.pipe = StableDiffusionControlNetPipeline.from_pretrained(
            BASE_MODEL,
            controlnet=self.controlnet,
            torch_dtype=torch_dtype,
            cache_dir=str(MODEL_CACHE_DIR),
            use_safetensors=True,
            safety_checker=None,
        )
        self.pipe.scheduler = DPMSolverMultistepScheduler.from_config(
            self.pipe.scheduler.config,
            algorithm_type="dpmsolver++",
            final_sigmas_type="sigma_min",
        )
        self.pipe.to(self.device)

        self._loaded = True
        gc.collect()
        torch.cuda.empty_cache()

        logger.info(f"SD 1.5 loaded in {time.time() - t0:.1f}s, "
                     f"VRAM: {torch.cuda.memory_allocated() / 1e9:.1f}GB")

    def unload_models(self) -> None:
        """释放模型显存"""
        if self.pipe:
            del self.pipe
            self.pipe = None
        if self.controlnet:
            del self.controlnet
            self.controlnet = None
        self._loaded = False
        gc.collect()
        torch.cuda.empty_cache()

    def _build_pose_image(
        self,
        keypoints: List[List[float]],
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
    ) -> Image.Image:
        """根据 COCO 关键点生成 OpenPose 风格骨架图——严格模仿原始 OpenPose 视觉"""
        import numpy as np
        # 先用白色在黑色背景画骨架
        arr = np.zeros((height, width, 3), dtype=np.uint8)

        kps_px = [(int(kp[0] * width), int(kp[1] * height)) for kp in keypoints]

        # OpenPose 风格：彩色肢体段（每条肢体不同颜色）+ 彩色关节点
        limb_colors = [
            (0, 255, 0),    # 头->肩 绿
            (255, 0, 0),    # 肩->肘 红
            (255, 255, 0),  # 肘->腕 黄
            (0, 255, 255),  # 肩->髋 青
            (255, 0, 255),  # 髋->膝 紫
            (0, 0, 255),    # 膝->踝 蓝
        ]

        from PIL import Image as PILImage

        def _draw_line(p1, p2, color, w=4):
            nonlocal arr
            temp = PILImage.fromarray(arr)
            draw = ImageDraw.Draw(temp)
            draw.line([p1, p2], fill=color, width=w)
            arr = np.array(temp)

        for idx, (i, j) in enumerate(SKELETON_EDGES):
            # 跳过面部连线 (0-1,0-2,1-3,2-4)：脸点不画，头只用绿圆表示
            if i <= 4 or j <= 4:
                continue
            if i < len(kps_px) and j < len(kps_px):
                x1, y1 = kps_px[i]
                x2, y2 = kps_px[j]
                if (x1, y1) != (0, 0) and (x2, y2) != (0, 0):
                    color = limb_colors[idx % len(limb_colors)]
                    _draw_line((x1, y1), (x2, y2), color, 4)

        # 头部大圆 + 脖子
        # 头半径：优先鼻到最远可见面部点（眼/耳）；无面部点时用躯干长度估算；
        # 侧视姿势肩 X 重叠，不能用肩宽。
        import math as _math
        head_radius_px = 0
        nose = kps_px[0]
        shoulders_visible = (kps_px[5] != (0, 0) and kps_px[6] != (0, 0))

        if nose != (0, 0):
            face_dists = [
                _math.dist(nose, kps_px[f])
                for f in range(1, 5)
                if kps_px[f] != (0, 0)
            ]
            if face_dists:
                # 用最大值（最远脸点=头部边界），由下方上限控制大小
                head_radius_px = int(max(face_dists))
        if head_radius_px == 0 and shoulders_visible:
            # 用躯干长度（肩中点->髋）估算：头半径 ≈ 躯干 * 0.25
            hip = kps_px[11] if kps_px[11] != (0, 0) else kps_px[12]
            if hip != (0, 0):
                shoulder_mid = ((kps_px[5][0] + kps_px[6][0]) // 2,
                                (kps_px[5][1] + kps_px[6][1]) // 2)
                torso = _math.dist(shoulder_mid, hip)
                head_radius_px = int(torso * 0.25)
        if head_radius_px == 0:
            head_radius_px = int(width * 0.05)  # 兜底
        # 上限：不超过画面宽度 6.5%，避免头圆过大
        head_radius_px = min(head_radius_px, int(width * 0.065))

        if head_radius_px > 0:
            if nose == (0, 0) and shoulders_visible:
                # 背面姿势（门区）：从双肩中点向上估算头位置
                mid = ((kps_px[5][0] + kps_px[6][0]) // 2,
                       (kps_px[5][1] + kps_px[6][1]) // 2)
                nose = (mid[0], mid[1] - int(head_radius_px * 1.8))
            # 画头圆（亮绿实心，严格模仿 OpenPose 训练数据的头部可视化）
            temp = PILImage.fromarray(arr)
            draw = ImageDraw.Draw(temp)
            draw.ellipse(
                [(nose[0]-head_radius_px, nose[1]-head_radius_px),
                 (nose[0]+head_radius_px, nose[1]+head_radius_px)],
                fill=(0, 255, 0), outline=(0, 200, 0), width=3,
            )
            arr = np.array(temp)
            # 脖子：从圆底部边缘到双肩中点
            if shoulders_visible:
                neck_top = (nose[0], nose[1] + head_radius_px)
                neck_bottom = ((kps_px[5][0] + kps_px[6][0]) // 2,
                               (kps_px[5][1] + kps_px[6][1]) // 2)
                _draw_line(neck_top, neck_bottom, (255, 255, 255), 5)

        # 关节点：身体点正常显示，面部点(0-4)不画（模型会误认成手，头用绿圆表示）
        temp = PILImage.fromarray(arr)
        draw = ImageDraw.Draw(temp)
        for idx, (x, y) in enumerate(kps_px):
            if (x, y) != (0, 0) and idx > 4:
                r = 5
                draw.ellipse([(x-r, y-r), (x+r, y+r)], fill=(0, 255, 0))
        img = temp

        return img

    def generate_single(
        self,
        event_type: str,
        template: dict,
        seed: Optional[int] = None,
        night_mode: bool = False,
        steps: int = DEFAULT_STEPS,
        guidance_scale: float = DEFAULT_GUIDANCE_SCALE,
        controlnet_scale: float = DEFAULT_CONTROLNET_CONDITIONING_SCALE,
    ) -> Dict[str, Any]:
        """生成单张图像

        Args:
            event_type: 事件类型
            template: 姿态模板 dict（含 keypoints/bbox/label）
            seed: 随机种子
            night_mode: 是否夜间低照度模式
            steps: 采样步数
            guidance_scale: CFG 引导系数
            controlnet_scale: ControlNet 条件强度

        Returns:
            dict: {image, keypoints, bbox, event_type, label, seed, prompt, ...}
        """
        if not self._loaded:
            self.load_models()

        if seed is None:
            seed = random.randint(0, 2**31 - 1)

        # 构建姿态条件图
        pose_image = self._build_pose_image(template["keypoints"])

        # 构建提示词
        prompt = get_prompt_for_event(event_type, night_mode=night_mode)

        # 注入随机种子确保可复现
        generator = torch.Generator(device="cpu").manual_seed(seed)

        # 生成
        t0 = time.time()
        result = self.pipe(
            prompt=prompt,
            negative_prompt=WARD_NEGATIVE_PROMPT,
            image=pose_image,
            num_inference_steps=steps,
            guidance_scale=guidance_scale,
            controlnet_conditioning_scale=controlnet_scale,
            generator=generator,
            height=DEFAULT_HEIGHT,
            width=DEFAULT_WIDTH,
        )
        gen_time = time.time() - t0

        image = result.images[0]

        # 添加随机抖动到关键点以增加多样性
        jittered_kps = self._jitter_keypoints(template["keypoints"])

        return {
            "image": image,
            "keypoints": jittered_kps,
            "keypoints_original": template["keypoints"],
            "bbox": template["bbox"],
            "event_type": event_type,
            "label": template.get("label", event_type),
            "seed": seed,
            "prompt": prompt,
            "night_mode": night_mode,
            "generation_time_ms": int(gen_time * 1000),
            "model": "sd15-controlnet-openpose",
        }

    def generate_batch(
        self,
        event_type: str,
        count: int = DEFAULT_BATCH_COUNT,
        variants_per_template: int = 3,
        night_ratio: float = 0.3,
        steps: int = DEFAULT_STEPS,
    ) -> List[Dict[str, Any]]:
        """批量生成某事件类型的图像

        Args:
            event_type: 事件类型
            count: 目标生成数量
            variants_per_template: 每个模板变体的重复次数
            night_ratio: 夜间模式比例
            steps: 采样步数

        Returns:
            生成结果列表
        """
        templates = get_templates_for_event(event_type)
        if not templates:
            logger.warning(f"No templates found for event_type={event_type}")
            return []

        results = []
        night_count = int(count * night_ratio)

        for i in range(count):
            template = templates[i % len(templates)]
            night_mode = i < night_count
            seed = random.randint(0, 2**31 - 1)

            try:
                result = self.generate_single(
                    event_type=event_type,
                    template=template,
                    seed=seed,
                    night_mode=night_mode,
                    steps=steps,
                )
                results.append(result)
                logger.info(
                    f"[{i+1}/{count}] {event_type}/{template['label']} "
                    f"night={night_mode} seed={seed} "
                    f"time={result['generation_time_ms']}ms"
                )
            except Exception as e:
                logger.error(f"Generation failed [{i+1}/{count}]: {e}")

        return results

    @staticmethod
    def _jitter_keypoints(
        keypoints: List[List[float]],
        max_offset: float = 0.02,
    ) -> List[List[float]]:
        """对关键点添加随机抖动以增加多样性"""
        jittered = []
        for kp in keypoints:
            if kp[0] == 0 and kp[1] == 0:
                jittered.append([0.0, 0.0])
            else:
                jx = kp[0] + random.uniform(-max_offset, max_offset)
                jy = kp[1] + random.uniform(-max_offset, max_offset)
                jittered.append([
                    max(0.0, min(1.0, jx)),
                    max(0.0, min(1.0, jy)),
                ])
        return jittered


# 全局单例
_generator: Optional[DiffusionGenerator] = None


def get_generator() -> DiffusionGenerator:
    global _generator
    if _generator is None:
        _generator = DiffusionGenerator()
    return _generator
