"""
演示截图标注工具（P2 交付物：任务书 §6 要求截图标注测试场景/时间/trace_id）

用法：
  # 命令行单张
  python scripts/annotate_screenshot.py <in.png> <out.png> "场景文字" [trace_id]

  # 作为模块调用
  from annotate_screenshot import annotate_image
  annotate_image("in.png", "out.png", scene="断网横幅", trace="...")

标注样式：底部半透明黑条 + 白色文字（场景 | 时间 | trace_id）
"""
import argparse
import datetime
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Windows 中文字体（黑体/微软雅黑）
FONT_CANDIDATES = [
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simsun.ttc",
]


def load_font(size):
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def annotate_image(
    src: str,
    dst: str,
    scene: str = "",
    trace: str = "",
    when: str = None,
    bar_height: int = 46,
    font_size: int = 22,
):
    """在截图底部叠加标注条。when 缺省为当前时间字符串。"""
    img = Image.open(src).convert("RGB")
    w, h = img.size
    when = when or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 底部标注条（半透明黑）
    bar = Image.new("RGBA", (w, bar_height), (15, 23, 42, 210))
    img = img.convert("RGBA")
    img.paste(bar, (0, h - bar_height), bar)

    draw = ImageDraw.Draw(img)
    font = load_font(font_size)

    text_parts = [f"场景: {scene}"] if scene else []
    text_parts.append(f"时间: {when}")
    if trace:
        text_parts.append(f"trace_id: {trace}")
    text = "  |  ".join(text_parts)

    # 文字放在标注条内，居中偏左
    text_y = h - bar_height + (bar_height - font_size) // 2 - 2
    draw.text((16, text_y), text, fill=(255, 255, 255, 255), font=font)

    img.convert("RGB").save(dst)
    return dst


def main():
    parser = argparse.ArgumentParser(description="演示截图叠加标注")
    parser.add_argument("src", help="输入图片")
    parser.add_argument("dst", help="输出图片")
    parser.add_argument("scene", nargs="?", default="", help="场景名称")
    parser.add_argument("trace", nargs="?", default="", help="trace_id")
    args = parser.parse_args()

    out = annotate_image(args.src, args.dst, scene=args.scene, trace=args.trace)
    print(f"[OK] 标注完成: {out}")


if __name__ == "__main__":
    main()
