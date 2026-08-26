#!/usr/bin/env python
"""一条命令跑完全部测试套件（每个套件独立进程）。

用法：
    python scripts/run_all_tests.py            # 跑全部
    python scripts/run_all_tests.py edge cloud # 只跑名字含这些子串的套件

为什么必须分进程跑
------------------
cloud-backend / cloud-llm-service / diffusion-service / training-coordinator
四个服务的顶层包**都叫 `app`**（各自独立部署，Dockerfile 里都是
`uvicorn app.main:app`）。一个 Python 进程里 `sys.modules["app"]` 只能指向
其中一个，所以

    pytest cloud-llm-service/tests diffusion-service/tests

必然 collection error（先被导入的 `app` 会把后一个顶掉）。这不是配置问题，
是微服务各自独立命名的正常结果——它们本来就不该共享解释器。
本脚本为每个套件拉起独立子进程，规避该冲突。

退出码：任一套件失败则为 1。
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Windows 控制台默认 GBK，套件输出里的 emoji（边缘代理的 🟢/☁️/🔀 等）
# 直接 print 会抛 UnicodeEncodeError，这里统一降级为替换字符。
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        try:
            _reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass

# (显示名, 命令参数) —— 命令统一在仓库根目录执行
SUITES: list[tuple[str, list[str]]] = [
    ("edge-agent", ["-m", "unittest", "discover", "edge-agent/tests"]),
    ("cloud-backend", ["-m", "unittest", "discover", "cloud-backend/tests"]),
    ("training-coordinator", ["-m", "unittest", "discover", "training-coordinator/tests"]),
    ("cloud-llm-service", ["-m", "pytest", "cloud-llm-service/tests", "-q"]),
    ("diffusion-service", ["-m", "pytest", "diffusion-service/tests", "-q"]),
]


def run_suite(name: str, args: list[str]) -> tuple[bool, str, float]:
    """跑一个套件，返回 (是否通过, 摘要行, 耗时秒)。"""
    started = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = time.perf_counter() - started
    ok = proc.returncode == 0
    summary = _extract_summary(proc.stdout, proc.stderr) or f"exit={proc.returncode}"
    if not ok:
        # 失败时把原始输出打出来，便于直接定位
        print(f"\n{'=' * 70}\n{name} 失败，原始输出：\n{'=' * 70}")
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
    return ok, summary, elapsed


def _extract_summary(stdout: str, stderr: str) -> str:
    """从 unittest / pytest 输出里抽出一行结果摘要。"""
    # unittest 把结果写到 stderr，pytest 写到 stdout
    for stream in (stderr, stdout):
        lines = [line.strip() for line in stream.splitlines() if line.strip()]
        for line in reversed(lines):
            if line.startswith("Ran ") or line in {"OK"} or line.startswith("OK ("):
                ran = next((x for x in lines if x.startswith("Ran ")), "")
                status = next(
                    (x for x in reversed(lines) if x.startswith(("OK", "FAILED"))), "")
                return f"{ran} {status}".strip()
            if " passed" in line or " failed" in line or " error" in line:
                return line
    return ""


def main() -> int:
    wanted = [a.lower() for a in sys.argv[1:]]
    suites = [
        (name, args) for name, args in SUITES
        if not wanted or any(w in name.lower() for w in wanted)
    ]
    if not suites:
        print(f"没有匹配的套件；可选：{', '.join(n for n, _ in SUITES)}")
        return 2

    print(f"运行 {len(suites)} 个测试套件（各自独立进程）\n")
    results = []
    for name, args in suites:
        print(f"  -> {name} ...", flush=True)
        results.append((name, *run_suite(name, args)))

    print(f"\n{'=' * 70}")
    failed = 0
    for name, ok, summary, elapsed in results:
        mark = "PASS" if ok else "FAIL"
        failed += 0 if ok else 1
        print(f"  [{mark}] {name:<22} {summary:<34} {elapsed:5.1f}s")
    print("=" * 70)

    if failed:
        print(f"\n{failed}/{len(results)} 个套件失败")
        return 1
    print(f"\n全部 {len(results)} 个套件通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
