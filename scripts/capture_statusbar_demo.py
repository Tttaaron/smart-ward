"""
SystemStatusBar 演示素材采集脚本（适配 2026-08 最新 UI：浅色临床风 + 多视图导航）

产出（文件名自动带当天日期，便于区分历史素材）：
  docs/evidence/screenshots/{date}_frontend_statusbar-dashboard.png        主看板 · 状态栏全绿
  docs/evidence/screenshots/{date}_frontend_statusbar-cloud-offline.png   云端断网横幅
  docs/evidence/screenshots/{date}_frontend_statusbar-cloud-recovery.png  云端恢复横幅
  docs/evidence/screenshots/{date}_frontend_statusbar-mqtt-offline.png    MQTT 中断 · 心跳过期
  docs/evidence/screenshots/{date}_frontend_statusbar-mqtt-recovered.png  MQTT 恢复 · 心跳恢复
  docs/evidence/videos/{date}_frontend_statusbar-demo.webm               全程录屏

流程（单次浏览器会话全程录屏）：
  注入事件 -> 在线态截图 -> stop cloud-backend（断网横幅）-> start（恢复横幅）
  -> stop mqtt-broker（心跳过期）-> start（心跳恢复）-> 落盘视频

用法：
  python scripts/capture_statusbar_demo.py [--out docs/evidence] [--base http://localhost:8081]
"""
import argparse
import json
import subprocess
import time
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8081"
COMPOSE = "docker compose -f docker-compose.yml"


def run_cmd(cmd, cwd=None):
    subprocess.run(cmd, shell=True, check=False, cwd=cwd)


def api_post(path, payload):
    req = urllib.request.Request(
        f"{BASE}/api{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def inject_route(bed, route, event_type, confidence=0.91):
    is_cloud = route == "cloud"
    model = (
        {"model_name": "qwen2.5-14b-instruct", "model_version": "1.0.0-vllm", "inference_ms": 12}
        if is_cloud
        else {"model_name": "qwen2.5-1.5b-instruct", "model_version": "1.0.0-q4", "inference_ms": 208}
    )
    details = {
        "route": route,
        "network": "online",
        "trace_id": str(uuid.uuid4()),
        "route_source": f"TaskRouter: {route}",
        "ttft_ms": 8 if is_cloud else 128,
        "cloud_latency_ms": 460 if (is_cloud or route == "hybrid") else None,
        "memory_mb": 640 if is_cloud else 962,
    }
    return api_post("/events", {
        "ward_id": "W-01",
        "bed_id": bed,
        "node_id": f"EDGE-W01-{bed}",
        "event_type": event_type,
        "confidence": confidence,
        "model": model,
        "details": details,
    })


def wait_for(page, selector, timeout_s, interval_s=0.5):
    """轮询等待某个元素出现，返回是否命中"""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if page.locator(selector).count() > 0:
            return True
        page.wait_for_timeout(int(interval_s * 1000))
    return False


def heartbeat_state(page):
    """返回节点心跳芯片的类名（ok/warn/err/dim）"""
    chip = page.locator(".status-chip", has_text="节点心跳")
    if chip.count() == 0:
        return "missing"
    cls = chip.get_attribute("class") or ""
    for s in ("err", "warn", "ok", "dim"):
        if s in cls:
            return s
    return "unknown"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="docs/evidence")
    parser.add_argument("--base", default=BASE)
    args = parser.parse_args()

    date = datetime.now().strftime("%Y%m%d")
    out_dir = Path(args.out)
    shots_dir = out_dir / "screenshots"
    vids_dir = out_dir / "videos"
    shots_dir.mkdir(parents=True, exist_ok=True)
    vids_dir.mkdir(parents=True, exist_ok=True)
    shot = lambda name: str(shots_dir / f"{date}_frontend_statusbar-{name}.png")

    # 注入三类链路事件，让主看板有真实内容
    for bed, route, etype in (("B01", "edge", "fall_suspected"), ("B02", "cloud", "seizure"), ("B03", "hybrid", "bed_leave")):
        try:
            inject_route(bed, route, etype)
        except Exception as e:
            print(f"[warn] 事件注入失败 {etype}: {e}")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(vids_dir / "_pw_profile"),
            headless=True,
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(vids_dir),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = context.pages[0] if context.pages else context.new_page()
        # ?live=1：跳过"比赛演示保护"（历史累计告警异常时强制演示数据），确保展示真实状态
        page.goto(f"{args.base}/?live=1", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        # 刷新一次，确保吃到注入的实时数据、退出演示降级态
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(5000)

        # 1) 主看板 · 状态栏在线
        page.screenshot(path=shot("dashboard"))
        chips = page.locator(".status-chip .chip-value").all_inner_texts()
        print(f"[OK] dashboard（状态栏在线）chips={chips}")

        # 2) 停止 cloud-backend -> 断网横幅
        run_cmd(f"{COMPOSE} stop cloud-backend")
        seen = wait_for(page, ".status-banner.offline", 120, 1.0)
        page.wait_for_timeout(1500)
        page.screenshot(path=shot("cloud-offline"))
        print(f"[OK] cloud-offline (banner_seen={seen})")
        page.wait_for_timeout(3000)  # 录屏留足横幅展示时间

        # 3) 重启 cloud-backend -> 恢复横幅
        run_cmd(f"{COMPOSE} start cloud-backend")
        seen = wait_for(page, ".status-banner.recovery", 180, 0.3)
        page.screenshot(path=shot("cloud-recovery"))
        print(f"[OK] cloud-recovery (banner_seen={seen})")
        page.wait_for_timeout(4000)

        # 4) 停止 mqtt-broker -> 边缘心跳过期
        run_cmd(f"{COMPOSE} stop mqtt-broker")
        stale_seen = False
        for _ in range(45):  # 心跳 45s 过期 + 5s 前端刷新，轮询最多 ~135s
            page.wait_for_timeout(3000)
            if heartbeat_state(page) in ("warn", "err"):
                stale_seen = True
                break
        page.wait_for_timeout(1500)
        page.screenshot(path=shot("mqtt-offline"))
        chips = page.locator(".status-chip .chip-value").all_inner_texts()
        print(f"[OK] mqtt-offline (heartbeat_degraded={stale_seen}, state={heartbeat_state(page)}, chips={chips})")
        page.wait_for_timeout(3000)

        # 5) 恢复 mqtt-broker -> 心跳恢复
        run_cmd(f"{COMPOSE} start mqtt-broker")
        recovered = False
        for _ in range(45):
            page.wait_for_timeout(3000)
            if heartbeat_state(page) == "ok":
                recovered = True
                break
        page.wait_for_timeout(2000)
        page.screenshot(path=shot("mqtt-recovered"))
        chips = page.locator(".status-chip .chip-value").all_inner_texts()
        print(f"[OK] mqtt-recovered (heartbeat_recovered={recovered}, state={heartbeat_state(page)}, chips={chips})")

        context.close()  # 关闭时才落盘视频

    # 重命名最新生成的录屏
    videos = sorted(vids_dir.glob("*.webm"), key=lambda f: f.stat().st_mtime)
    if videos:
        newest = videos[-1]
        target = vids_dir / f"{date}_frontend_statusbar-demo.webm"
        if newest != target:
            newest.replace(target)
        print(f"[OK] 视频: {target} ({target.stat().st_size / 1024 / 1024:.1f} MB)")
    else:
        print("[warn] 未生成视频文件")

    print(f"完成，输出目录: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
