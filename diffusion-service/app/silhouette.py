"""人体轮廓生成器 — 从 COCO 17 关键点生成适合 img2img 的人体轮廓图

按骨架实际几何自适应：身体横放(侧视躺姿)或竖放(站立/坐姿)都能正确绘制。
"""

import math
from typing import List

from PIL import Image, ImageDraw, ImageFilter

from config.pose_templates import H


def _valid(kps_px, idx):
    return idx < len(kps_px) and kps_px[idx] != (0, 0)


def build_human_silhouette(keypoints, width=768, height=768, color=(170, 165, 160)):
    """从关键点生成人体轮廓图（白底）

    Args:
        keypoints: COCO 17 关键点（归一化 0~1），不可见点为 [0,0]
        width, height: 画布尺寸
        color: 人体填充色

    Returns:
        PIL.Image: 轮廓图（轻微高斯模糊）
    """
    kps_px = [(int(kp[0] * width), int(kp[1] * height)) for kp in keypoints]
    img = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    def _line(p1, p2, w, c=color):
        if p1 != (0, 0) and p2 != (0, 0):
            draw.line([p1, p2], fill=c, width=w)

    # ── 头 ──
    if _valid(kps_px, 0):
        nose = kps_px[0]
        if _valid(kps_px, 3) and _valid(kps_px, 4):
            hr = int(math.dist(kps_px[3], kps_px[4]) * 0.5)
        elif _valid(kps_px, 5) and _valid(kps_px, 6):
            hr = int(abs(kps_px[5][0] - kps_px[6][0]) * 0.28)
        else:
            hr = int(0.5 * H * height)
        draw.ellipse([(nose[0]-hr, nose[1]-hr), (nose[0]+hr, nose[1]+hr)], fill=color)

    # ── 躯干：肩中点 -> 髋中点 的粗线（横躺竖躺都自然）──
    if _valid(kps_px, 5) and _valid(kps_px, 6) and _valid(kps_px, 11) and _valid(kps_px, 12):
        shoulder_mid = ((kps_px[5][0] + kps_px[6][0]) // 2,
                        (kps_px[5][1] + kps_px[6][1]) // 2)
        hip_mid = ((kps_px[11][0] + kps_px[12][0]) // 2,
                   (kps_px[11][1] + kps_px[12][1]) // 2)
        # 脖子：头圆底部 -> 肩中点
        if _valid(kps_px, 0):
            nose = kps_px[0]
            if _valid(kps_px, 3) and _valid(kps_px, 4):
                hr = int(math.dist(kps_px[3], kps_px[4]) * 0.5)
            else:
                hr = int(0.5 * H * height)
            _line((nose[0], nose[1] + hr), shoulder_mid, int(0.35 * H * height))
        # 躯干：肩中点 -> 髋中点
        torso_w = int(1.1 * H * height)
        _line(shoulder_mid, hip_mid, torso_w)

    # ── 四肢：上下段分级粗细 ──
    segments = [
        (5, 7, 0.9), (7, 9, 0.55),   # 左臂
        (6, 8, 0.9), (8, 10, 0.55),  # 右臂
        (11, 13, 1.0), (13, 15, 0.65),  # 左腿
        (12, 14, 1.0), (14, 16, 0.65),  # 右腿
    ]
    for i, j, w_h in segments:
        if _valid(kps_px, i) and _valid(kps_px, j):
            w = int(w_h * H * height)
            _line(kps_px[i], kps_px[j], w)

    # ── 手（小圆）与脚（长椭圆）──
    for idx in (9, 10):
        if _valid(kps_px, idx):
            x, y = kps_px[idx]
            r = int(0.28 * H * height)
            draw.ellipse([(x-r, y-r), (x+r, y+r)], fill=(185, 180, 175))
    for idx in (15, 16):
        if _valid(kps_px, idx):
            x, y = kps_px[idx]
            rw = int(0.22 * H * height)
            rh = int(0.38 * H * height)
            draw.ellipse([(x-rw, y-rh), (x+rw, y+rh)], fill=(175, 170, 165))

    # 轻微模糊，让 img2img 有"填肉"空间
    return img.filter(ImageFilter.GaussianBlur(radius=3))
