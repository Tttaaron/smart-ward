#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""拉取并校验边缘 LLM（GGUF）模型文件

用于把蒸馏学生模型（如 qwen2.5-1.5b-ward-q4_k_m.gguf）从 P5/Artifact 拉取到边缘
模型目录，并按 sha256 校验（不匹配不落盘）。文件到位后，边缘设置
LLM_MODE=real + LLM_MODEL_PATH 指向该文件即可运行时加载（或通过 model/deploy 下发）。

用法:
  python scripts/fetch_edge_llm.py --url http://<artifact>/qwen2.5-1.5b-ward-q4_k_m.gguf \\
      --sha256 c86401b2befde9ddfa7b3e3b8c0f51a5ecaf5de01beb86a6877efb420c352986
  python scripts/fetch_edge_llm.py --url file:///path/to/model.gguf --out edge-agent/models/my.gguf
"""

import argparse
import hashlib
import os
import sys
import tempfile
import urllib.request

# 蒸馏学生模型默认落位路径（P5 蒸馏产出，checksum 见 datasets/.../comparison.json）
DEFAULT_OUT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..",
    "edge-agent", "models", "qwen2.5-1.5b-ward-distilled",
    "qwen2.5-1.5b-ward-q4_k_m.gguf",
)


def sha256_of_stream(stream) -> str:
    h = hashlib.sha256()
    while True:
        chunk = stream.read(1 << 20)
        if not chunk:
            break
        h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: str, sha256: str = "") -> str:
    """下载 url -> dest（临时文件 + sha256 校验 + 原子落盘），返回实际 sha256。"""
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)

    # 打开源：http(s) / file:// / 普通本地路径
    if url.lower().startswith("http"):
        req = urllib.request.Request(url, headers={"User-Agent": "smart-ward/fetch-edge-llm"})
        src = urllib.request.urlopen(req)  # noqa: S310 - 内部产物地址
    elif url.lower().startswith("file://"):
        src = open(url[7:], "rb")
    else:
        src = open(url, "rb")

    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(dest)),
                                    suffix=".part")
    actual = ""
    try:
        with os.fdopen(fd, "wb") as out, src:
            h = hashlib.sha256()
            while True:
                chunk = src.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
                h.update(chunk)
            actual = h.hexdigest()

        if sha256:
            expected = sha256.strip().lower()
            if expected.startswith("sha256:"):
                expected = expected[7:]
            if actual != expected:
                os.remove(tmp_path)
                raise SystemExit(
                    f"校验失败: 实际 {actual[:16]}… != 期望 {expected[:16]}…，"
                    f"已删除临时文件，未落盘")
        os.replace(tmp_path, dest)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    return actual


def main():
    parser = argparse.ArgumentParser(description="拉取并校验边缘 LLM GGUF 模型")
    parser.add_argument("--url", required=True, help="模型地址 http(s)/file:///本地路径")
    parser.add_argument("--sha256", default="", help="期望 sha256（可选，提供则校验）")
    parser.add_argument("--out", default=DEFAULT_OUT, help=f"目标路径（默认 {DEFAULT_OUT}）")
    parser.add_argument("--model-name", default="qwen2.5-1.5b-ward",
                        help="模型名称（供边缘 LLM_MODEL_NAME 使用）")
    parser.add_argument("--model-version", default="1.0.0-int4",
                        help="模型版本（供 LLM_MODEL_VERSION 使用）")
    args = parser.parse_args()

    print(f"[fetch-edge-llm] 下载: {args.url}")
    actual = download(args.url, args.out, args.sha256)
    size_mb = os.path.getsize(args.out) / (1024 * 1024)
    print(f"[fetch-edge-llm] 完成: {args.out} ({size_mb:.1f} MB)")
    print(f"[fetch-edge-llm] sha256: {actual}")
    print(f"[fetch-edge-llm] 就绪，边缘使用以下环境变量：")
    print(f"  LLM_MODE=real")
    print(f"  LLM_MODEL_PATH={args.out}")
    print(f"  LLM_MODEL_NAME={args.model_name}")
    print(f"  LLM_MODEL_VERSION={args.model_version}")


if __name__ == "__main__":
    main()
