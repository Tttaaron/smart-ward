# -*- coding: utf-8 -*-
"""
一次性把护士站前端里过小的字号提升到"投影可读"区间。

背景：原界面大量使用 9 / 9.5 / 10 / 10.5 px 的字号，在笔记本上看尚可，
但评审现场是投影/大屏，11px 以下基本不可读。这里做单遍映射（不是链式放大），
避免 10 -> 11.5 -> 12 之类的累计漂移。

只处理 CSS 的 font-size 声明与 font 简写中的字号，不碰 ECharts 的 fontSize
（那是 JS 数值，语法不同，单独处理）。
"""
import re
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent / "src"

# 单遍映射：键为原始 px 数值，值为目标数值
SCALE = {
    "8": "11",
    "9": "11",
    "9.5": "11",
    "10": "11.5",
    "10.5": "12",
    "11": "11.5",
    "11.5": "12",
    "12": "12.5",
}

# font: 800 9px/1 'Outfit' 这类简写
FONT_SHORTHAND = re.compile(r"(\bfont:\s*[^;]*?\b)(\d+(?:\.\d+)?)px(/)")
FONT_SIZE = re.compile(r"(font-size:\s*)(\d+(?:\.\d+)?)px", re.IGNORECASE)


def bump(match: re.Match, group: int = 2) -> str:
    raw = match.group(group)
    return match.group(1) + (SCALE.get(raw, raw) + "px" if group == 2 else SCALE.get(raw, raw) + "px")


def process(path: pathlib.Path) -> int:
    text = path.read_text(encoding="utf-8")
    original = text
    hits = 0

    def repl_size(m):
        nonlocal hits
        raw = m.group(2)
        if raw in SCALE:
            hits += 1
            return m.group(1) + SCALE[raw] + "px"
        return m.group(0)

    def repl_shorthand(m):
        nonlocal hits
        raw = m.group(2)
        if raw in SCALE:
            hits += 1
            return m.group(1) + SCALE[raw] + "px" + m.group(3)
        return m.group(0)

    text = FONT_SIZE.sub(repl_size, text)
    text = FONT_SHORTHAND.sub(repl_shorthand, text)

    if text != original:
        path.write_text(text, encoding="utf-8")
    return hits


def main() -> None:
    total = 0
    changed = []
    for path in sorted(ROOT.rglob("*.vue")):
        n = process(path)
        if n:
            changed.append((path.relative_to(ROOT), n))
            total += n
    for rel, n in changed:
        print(f"  {n:>3} 处  {rel}")
    print(f"\n共调整 {total} 处字号，涉及 {len(changed)} 个组件")


if __name__ == "__main__":
    main()
