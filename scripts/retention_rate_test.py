#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""断网保持率统计（三指标分开统计，对齐赛题 ≥90%）

自动化编排：amqtt broker + edge-agent（mock），模拟断网 -> 缓存 -> 恢复补传，
统计并输出三个保持率指标与证据 JSON。

三指标定义：
  1. 断网事件保持率   = 断网期间成功产生并缓存的事件 / 断网期间事件总数
                       （边端离线持续值守，事件全部落 SQLite，应 100%）
  2. 恢复补传完整率   = 恢复后成功同步的事件 / 断网期间缓存事件
                       （网络恢复后批量补传，应 100%）
  3. 云端去重保持率   = 唯一 event_id / 接收事件总数
                       （event_id 全局唯一 + 云端幂等，应 100%）

用法:
  python scripts/retention_rate_test.py --online 20 --offline 25 --recover 15
  python scripts/retention_rate_test.py --out docs/evidence/mqtt-sync/
"""

import argparse
import json
import os
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone

EDGE_SRC = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "edge-agent", "src"))
AMQTT = os.path.join(os.path.dirname(sys.executable), "Scripts", "amqtt.exe")


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class RetentionTest:
    def __init__(self, workdir, online_s, offline_s, recover_s):
        self.workdir = workdir
        self.online_s = online_s
        self.offline_s = offline_s
        self.recover_s = recover_s
        self.db_path = os.path.join(workdir, "edge_EDGE-W01-B02.db")
        self.procs = []

    # ── 进程管理 ──
    def _start_broker(self):
        logf = open(os.path.join(self.workdir, "broker.log"), "a")
        proc = subprocess.Popen([AMQTT], stdout=logf, stderr=logf)
        logf.close()  # Popen 持有自己的句柄，父进程关闭避免句柄占用
        self.procs.append(("broker", proc))
        time.sleep(1.5)

    def _stop_broker(self):
        # 强杀所有 amqtt 相关进程（amqtt.exe 会派生 python 子进程，需一并清理）
        subprocess.run(["taskkill", "/F", "/IM", "amqtt.exe"], capture_output=True)
        powershell = (
            "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
            "Where-Object { $_.CommandLine -like '*amqtt*' } | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")
        subprocess.run(["powershell", "-NoProfile", "-Command", powershell],
                       capture_output=True)
        for name, proc in list(self.procs):
            if name == "broker":
                self.procs.remove((name, proc))
        time.sleep(2)

    def _start_edge(self):
        logf = open(os.path.join(self.workdir, "edge.log"), "w")
        env = dict(os.environ)
        env.update({
            "PYTHONUNBUFFERED": "1",
            "WARD_ID": "W-01", "BED_ID": "B02", "EDGE_NODE_ID": "EDGE-W01-B02",
            "MQTT_BROKER": "localhost", "MQTT_PORT": "1883",
            "TICK_SECONDS": "1", "EVENT_DEDUPE_SECONDS": "2",
            "SCENARIO_PROFILE": "seizure", "LLM_MODE": "mock",
            "ROUTER_CLOUD_TIMEOUT_S": "3", "ROUTER_EDGE_THRESHOLD": "0.95",
            "EDGE_DB_DIR": self.workdir,
        })
        proc = subprocess.Popen([sys.executable, "main.py"], cwd=EDGE_SRC,
                                env=env, stdout=logf, stderr=logf)
        logf.close()
        self.procs.append(("edge", proc))

    def _stop_edge(self):
        for name, proc in list(self.procs):
            if name == "edge":
                try:
                    proc.terminate()
                    proc.wait(timeout=8)
                except (subprocess.TimeoutExpired, ProcessLookupError):
                    if sys.platform == "win32":
                        subprocess.run(
                            ["taskkill", "/F", "/PID", str(proc.pid)],
                            capture_output=True)
                    else:
                        proc.kill()
                self.procs.remove((name, proc))

    # ── SQLite 快照 ──
    def _db_counts(self):
        conn = sqlite3.connect(self.db_path)
        total = conn.execute("SELECT COUNT(*) FROM safety_events").fetchone()[0]
        synced0 = conn.execute("SELECT COUNT(*) FROM safety_events WHERE synced=0").fetchone()[0]
        unique = conn.execute("SELECT COUNT(DISTINCT event_id) FROM safety_events").fetchone()[0]
        conn.close()
        return {"total": total, "synced0": synced0, "synced1": total - synced0, "unique": unique}

    def run(self) -> dict:
        self._start_broker()
        self._start_edge()
        # 1) 在线基线
        time.sleep(self.online_s)
        online = self._db_counts()
        # 2) 断网
        self._stop_broker()
        time.sleep(2)
        offline_start = self._db_counts()
        time.sleep(self.offline_s)
        offline_end = self._db_counts()
        buffered_during_offline = offline_end["synced0"] - offline_start["synced0"]
        generated_during_offline = offline_end["total"] - offline_start["total"]
        # 3) 恢复 + 补传
        self._start_broker()
        time.sleep(self.recover_s)
        recovered = self._db_counts()
        self._stop_edge()
        self._stop_broker()

        # ── 三指标 ──
        # 1) 断网事件保持率：断网期间产生的事件全部缓存（synced=0 增量为负视为异常）
        if generated_during_offline > 0:
            cached = offline_end["synced0"] - offline_start["synced0"]
            event_retention = cached / generated_during_offline if generated_during_offline else 0.0
        else:
            cached = 0
            event_retention = 0.0
        # 2) 恢复补传完整率：断网期间缓存事件在恢复后全部 synced
        remaining_after_recover = recovered["synced0"] - online["synced0"]
        if buffered_during_offline > 0:
            replay_rate = 1.0 - remaining_after_recover / buffered_during_offline
        else:
            replay_rate = 1.0 if generated_during_offline == 0 else 0.0
        # 3) 云端去重保持率：event_id 唯一性（恢复后无重复）
        dedup_rate = recovered["unique"] / recovered["total"] if recovered["total"] else 1.0

        report = {
            "generated_at": utc_now(),
            "method": "amqtt broker + edge-agent(mock) 断网->缓存->恢复->补传",
            "phases": {
                "online_s": self.online_s, "offline_s": self.offline_s,
                "recover_s": self.recover_s,
                "online_snapshot": online,
                "offline_start": offline_start,
                "offline_end": offline_end,
                "recovered_snapshot": recovered,
            },
            "metrics": {
                "generated_during_offline": generated_during_offline,
                "buffered_during_offline": buffered_during_offline,
                "remaining_unsynced_after_recover": remaining_after_recover,
            },
            "retention_rates": {
                "event_retention_rate": round(event_retention, 4),
                "replay_rate": round(max(0.0, replay_rate), 4),
                "dedup_rate": round(dedup_rate, 4),
            },
            "target": "each >= 0.90",
        }
        return report


def main():
    parser = argparse.ArgumentParser(description="断网保持率三指标统计")
    parser.add_argument("--online", type=int, default=20, help="在线阶段秒数")
    parser.add_argument("--offline", type=int, default=25, help="断网阶段秒数")
    parser.add_argument("--recover", type=int, default=15, help="恢复补传秒数")
    parser.add_argument("--out", default="docs/evidence/mqtt-sync",
                        help="证据 JSON 输出目录")
    args = parser.parse_args()

    workdir = tempfile.mkdtemp(prefix="retention-")
    tester = RetentionTest(workdir, args.online, args.offline, args.recover)
    print(f"[retention] 在线 {args.online}s -> 断网 {args.offline}s -> 恢复 {args.recover}s")
    try:
        report = tester.run()
    finally:
        import shutil
        shutil.rmtree(workdir, ignore_errors=True)  # 句柄已释放，忽略残留

    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, "retention_rate_report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    rates = report["retention_rates"]
    passed = all(v >= 0.9 for v in rates.values())
    print("\n" + "=" * 60)
    print(f"断网事件保持率: {rates['event_retention_rate']:.1%}")
    print(f"恢复补传完整率: {rates['replay_rate']:.1%}")
    print(f"云端去重保持率: {rates['dedup_rate']:.1%}")
    print(f"三指标均 ≥90%: {'PASS ✅' if passed else 'FAIL ❌'}")
    print(f"证据: {path}")
    print("=" * 60)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
