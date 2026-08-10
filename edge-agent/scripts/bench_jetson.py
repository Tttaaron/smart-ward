"""边缘 LLM 性能基准脚本（Jetson / x86 通用）。

对齐任务书 §7.1 性能记录格式，输出可归档 JSON 报告：
  - 模型加载耗时（冷启动）
  - 热身后 TTFT p50/p95/max（同一 prompt 重复 N 次，默认 30）
  - 峰值 RSS（psutil 采样，含/不含视觉模型并行）
  - 吞吐量 tokens/s（p50/p95）
  - 系统/运行时/模型哈希/git 提交号等关键环境信息

用法::

    # 基础测量（复用 edge-agent LLMEngine，环境变量同 docker-compose）
    python edge-agent/scripts/bench_jetson.py \
        --model edge-agent/models/qwen2.5-1.5b-gguf/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf

    # 调整参数
    python edge-agent/scripts/bench_jetson.py --model <path> \
        --rounds 50 --warmup 5 --n-ctx 512 --batch 128 --threads 8 --max-tokens 64

    # 视觉模型并行占用（与 YOLO-pose 同时运行时的峰值 RSS）
    python edge-agent/scripts/bench_jetson.py --model <path> \
        --visual-model edge-agent/models/yolo11n-pose.pt --device 0

    # 跳过大文件哈希（首次可加 --skip-hash 加速）
    python edge-agent/scripts/bench_jetson.py --model <path> --skip-hash

报告输出: edge-agent/data/bench-<模型名>-<YYYYMMDD-HHMMSS>.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "edge-agent" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

PROMPT = (
    "患者 B01 在夜间 23:40 检测到疑似跌倒，置信度 0.82，"
    "请给出护理建议和处置优先级。"
)


def sha256_of(path: Path, chunk_size: int = 1 << 20) -> str:
    """流式计算模型文件 SHA256（1GB 模型约数秒）。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def git_head(repo: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True,
            text=True, timeout=5, check=False)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def collect_system_info() -> dict:
    """系统/运行时信息（任务书 §7.1 要求的关键环境字段）。"""
    info = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
        "cpu_count": os.cpu_count(),
    }
    try:
        import torch
        info["torch_version"] = torch.__version__
        info["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            info["cuda_version"] = torch.version.cuda
            info["gpu_name"] = torch.cuda.get_device_name(0)
            info["gpu_memory_gb"] = round(
                torch.cuda.get_device_properties(0).total_memory / (1024 ** 3), 1)
    except Exception as exc:
        info["torch_error"] = str(exc)
    return info


class RssSampler:
    """后台采样进程峰值 RSS（MB），覆盖加载与全部推理过程。"""

    def __init__(self, interval: float = 0.01) -> None:
        self.interval = interval
        self.peak_mb = 0.0
        self.baseline_mb = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        import psutil
        self._proc = psutil.Process()
        self.baseline_mb = self._proc.memory_info().rss / (1024 * 1024)
        self._stop.clear()
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self._thread.start()

    def _sample(self) -> None:
        import psutil
        while not self._stop.wait(self.interval):
            rss = self._proc.memory_info().rss / (1024 * 1024)
            if rss > self.peak_mb:
                self.peak_mb = rss

    def stop(self) -> float:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        return self.peak_mb


def percentile(values: list, p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round(p / 100 * (len(ordered) - 1)))))
    return ordered[index]


def load_visual_model(path: Path, device: str) -> object | None:
    """并行占用测量：加载 YOLO-pose 模型（依赖 ultralytics）。"""
    try:
        from ultralytics import YOLO
    except ImportError:
        print("[bench] ultralytics 未安装，跳过视觉模型并行测量")
        return None
    print(f"[bench] 加载视觉模型: {path} (device={device})")
    return YOLO(str(path))


def run_benchmark(args) -> dict:
    import psutil

    # ── 模型与参数（对齐 docker-compose 的 LLM 环境变量）──
    model_path = Path(args.model).resolve()
    if not model_path.exists():
        sys.exit(f"模型文件不存在: {model_path}")
    os.environ["LLM_MODE"] = "real"
    os.environ["LLM_MODEL_PATH"] = str(model_path)
    os.environ["LLM_N_CTX"] = str(args.n_ctx)
    os.environ["LLM_N_BATCH"] = str(args.batch)
    os.environ["LLM_N_UBATCH"] = str(args.batch)
    os.environ["LLM_N_THREADS"] = str(args.threads)
    os.environ["LLM_MAX_TOKENS"] = str(args.max_tokens)
    os.environ["LLM_USE_MMAP"] = str(args.mmap).lower()

    from llm_engine import LLMEngine

    print(f"[bench] 模型: {model_path.name}")
    print(f"[bench] 参数: ctx={args.n_ctx} batch={args.batch} "
          f"threads={args.threads} max_tokens={args.max_tokens} "
          f"rounds={args.rounds} warmup={args.warmup}")

    # ── 冷启动加载耗时 + RSS 采样 ──
    sampler = RssSampler()
    sampler.start()
    t0 = time.perf_counter()
    engine = LLMEngine()
    if not engine.is_ready():
        sys.exit("[bench] LLMEngine 未就绪（real 模式需要 llama-cpp-python；"
                 "请检查依赖与 LLM_MODEL_PATH）")
    load_time_s = time.perf_counter() - t0

    # ── 视觉模型并行（可选）──
    visual = None
    if args.visual_model:
        visual = load_visual_model(Path(args.visual_model), args.visual_device)

    # ── 热身 + 正式测量 ──
    for _ in range(args.warmup):
        engine.generate(PROMPT, max_tokens=args.max_tokens)

    ttft_ms: list[float] = []
    total_ms: list[float] = []
    tps: list[float] = []
    tokens: list[int] = []
    for i in range(args.rounds):
        resp = engine.generate(PROMPT, max_tokens=args.max_tokens)
        ttft_ms.append(resp.ttft_ms)
        total_ms.append(resp.total_ms)
        tps.append(resp.tokens_per_sec)
        tokens.append(resp.tokens_generated)
        if (i + 1) % 10 == 0 or i == args.rounds - 1:
            print(f"[bench] round {i + 1}/{args.rounds} "
                  f"ttft={resp.ttft_ms:.1f}ms total={resp.total_ms:.1f}ms "
                  f"tps={resp.tokens_per_sec:.1f}")
    peak_rss_mb = sampler.stop()
    if visual is not None:
        del visual

    status = engine.get_status()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "dataset": None,
        "model": {
            "path": str(model_path),
            "name": status.get("model_name", model_path.name),
            "version": status.get("model_version", ""),
            "quantization": status.get("quantization", "unknown"),
            "size_bytes": model_path.stat().st_size,
            "sha256": None if args.skip_hash else sha256_of(model_path),
        },
        "params": {
            "n_ctx": args.n_ctx,
            "batch": args.batch,
            "threads": args.threads,
            "max_tokens": args.max_tokens,
            "mmap": args.mmap,
            "warmup_rounds": args.warmup,
            "samples": args.rounds,
            "prompt_chars": len(PROMPT),
        },
        "environment": collect_system_info(),
        "git_head": git_head(REPO_ROOT),
        "load_time_s": round(load_time_s, 2),
        "ttft_ms": {
            "p50": round(percentile(ttft_ms, 50), 2),
            "p95": round(percentile(ttft_ms, 95), 2),
            "max": round(max(ttft_ms), 2),
            "min": round(min(ttft_ms), 2),
        },
        "total_ms": {
            "p50": round(percentile(total_ms, 50), 2),
            "p95": round(percentile(total_ms, 95), 2),
            "max": round(max(total_ms), 2),
        },
        "tokens_per_sec": {
            "p50": round(percentile(tps, 50), 2),
            "p95": round(percentile(tps, 95), 2),
            "max": round(max(tps), 2),
        },
        "tokens_generated_avg": round(statistics.mean(tokens), 1),
        "memory": {
            "baseline_rss_mb": round(sampler.baseline_mb, 1),
            "peak_rss_mb": round(peak_rss_mb, 1),
            "visual_model": bool(args.visual_model),
            "visual_model_path": args.visual_model,
        },
        "metrics_from_engine": engine.get_status(),
    }

    # ── 控制台汇总 ──
    print("\n" + "=" * 60)
    print("边缘 LLM 性能基准汇总")
    print("=" * 60)
    print(f"模型:            {report['model']['name']} ({report['model']['version']})")
    print(f"加载耗时:        {report['load_time_s']}s")
    print(f"TTFT p50/p95/max: {report['ttft_ms']['p50']} / "
          f"{report['ttft_ms']['p95']} / {report['ttft_ms']['max']} ms")
    print(f"总延迟 p50/p95:   {report['total_ms']['p50']} / {report['total_ms']['p95']} ms")
    print(f"吞吐 p50/p95:     {report['tokens_per_sec']['p50']} / "
          f"{report['tokens_per_sec']['p95']} tok/s")
    print(f"峰值 RSS:        {report['memory']['peak_rss_mb']} MB "
          f"(基线 {report['memory']['baseline_rss_mb']} MB, "
          f"视觉并行={'是' if visual else '否'})")
    print(f"设备:            {report['environment'].get('gpu_name', 'CPU')}")

    out_dir = REPO_ROOT / "edge-agent" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / f"bench-{model_path.stem}-{stamp}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"\n报告已保存: {out_path}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="边缘 LLM 性能基准（Jetson/x86）")
    parser.add_argument("--model", required=True, help="GGUF 模型文件路径")
    parser.add_argument("--rounds", type=int, default=30, help="正式测量次数（默认 30）")
    parser.add_argument("--warmup", type=int, default=3, help="热身轮数（默认 3）")
    parser.add_argument("--n-ctx", type=int, default=512, help="上下文窗口（默认 512）")
    parser.add_argument("--batch", type=int, default=128, help="批处理大小（默认 128）")
    parser.add_argument("--threads", type=int, default=8, help="CPU 线程数（默认 8）")
    parser.add_argument("--max-tokens", type=int, default=64, help="最大生成 token（默认 64）")
    parser.add_argument("--mmap", action="store_true", default=True, help="mmap 加载（默认开）")
    parser.add_argument("--skip-hash", action="store_true", help="跳过模型 SHA256 计算")
    parser.add_argument("--visual-model", default=None, help="视觉模型路径（并行占用测量）")
    parser.add_argument("--visual-device", default="0", help="视觉模型设备（默认 cuda:0）")
    args = parser.parse_args()
    run_benchmark(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
