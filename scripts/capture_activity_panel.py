"""
护士站活动日志面板截图脚本（P2 交付物）

场景：
  1. 通过 POST /api/observations 注入多床位活动状态（坐姿/站立/卧躺切换）
  2. 等待 WS 推送至前端第四列活动日志面板渲染
  3. 截图活动面板 + 全屏总览
  4. 复用 annotate_screenshot.py 叠加标注条（场景 | 时间 | trace_id）

依赖：全栈已启动（docker compose up -d）+ Playwright(Chromium)

用法：
  python scripts/capture_activity_panel.py [--out DIR] [--base http://localhost:8081]
"""
import argparse
import json
import time
import urllib.request
import uuid
from pathlib import Path

from playwright.sync_api import sync_playwright

from annotate_screenshot import annotate_image

BASE = "http://localhost:8081"

# 活动注入序列：床号 -> [(标签, 姿势, 间隔秒), ...]（含 switched 切换）
ACTIVITY_SEQUENCE = {
    "B01": [
        ("sitting", "sitting", 0),
        ("standing", "standing", 2.0),
        ("lying", "lying", 2.0),
    ],
    "B02": [
        ("sitting", "sitting", 0),
        ("sleeping", "lying", 3.0),
    ],
    "B03": [
        ("standing", "standing", 0),
        ("walking", "walking", 3.5),
    ],
}


def api_post(path, payload):
    """向后端注入观测（走前端代理 8081）"""
    req = urllib.request.Request(
        f"{BASE}/api{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def inject_activity(bed, label, posture, previous=None, since=None, trace_id=None):
    """注入一条含 activity 的 camera 观测，驱动活动日志面板"""
    trace = trace_id or str(uuid.uuid4())
    since = since or time.time()
    payload = {
        "ward_id": "W-01",
        "node_id": f"EDGE-W01-{bed}",
        "bed_id": bed,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sources": [{
            "source_type": "camera",
            "data": {
                "presence": True,
                "person_count": 1,
                "posture": posture,
                "fall_score": 0.0,
                "trace_id": trace,
                "activity": {
                    "label": label,
                    "since": round(since, 2),
                    "switched": True,
                    "previous": previous,
                },
            },
            "quality": {"confidence": 0.95, "latency_ms": 45, "degraded": False},
        }],
    }
    return api_post("/observations", payload)


def wait_render(page, ms=1500):
    page.wait_for_timeout(ms)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="docs/evidence/screenshots")
    parser.add_argument("--base", default=BASE)
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    trace = str(uuid.uuid4())

    # 按序列注入活动切换（previous 依次衔接形成切换链）
    for bed, seq in ACTIVITY_SEQUENCE.items():
        prev = None
        for label, posture, delay in seq:
            if delay:
                time.sleep(delay)
            inject_activity(bed, label, posture, previous=prev, since=time.time(), trace_id=trace)
            prev = label
            print(f"[OK] 注入 {bed} activity={label} (previous={prev})")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(args.base, wait_until="domcontentloaded")
        wait_render(page, 3000)

        # ---- 场景 1：活动日志面板（第四列）----
        activity_panel = page.locator("section.clinical-panel").nth(3)
        raw = out_dir / "raw_activity-panel.png"
        activity_panel.screenshot(path=str(raw))
        annotate_image(
            str(raw),
            str(out_dir / "20260811_frontend_activity-panel.png"),
            scene="活动日志面板 · observation.activity 实时切换",
            trace=trace,
        )
        print("[OK] activity-panel")

        # ---- 场景 2：全屏总览（含第四列布局）----
        raw2 = out_dir / "raw_dashboard-with-activity.png"
        page.screenshot(path=str(raw2), full_page=True)
        annotate_image(
            str(raw2),
            str(out_dir / "20260811_frontend_dashboard-activity-overview.png"),
            scene="主看板四列布局 · 活动日志面板",
            trace=trace,
        )
        print("[OK] dashboard-activity-overview")

        browser.close()
    print(f"\n活动面板截图完成，输出目录: {out_dir.resolve()}")
    print("注：以上标注条已包含 trace_id，可按下述回查：")
    print(f"  docker compose logs cloud-backend | grep {trace}")


if __name__ == "__main__":
    main()
