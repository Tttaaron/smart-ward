"""
护士站前端演示截图脚本（P2 交付物）

场景：
  1. 主看板总览（含 edge/cloud/hybrid 路由事件 + 系统状态栏全绿）
  2. 事件详情抽屉（trace_id / 模型 / 性能指标 / 处置记录）
  3. 超时/降级事件卡片
  4. 云端路由事件卡片

用法：
  python scripts/capture_frontend_screenshots.py [--out DIR] [--base http://localhost:8081]
"""
import argparse
import json
import sys
import time
import urllib.request
import uuid
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8081"


def api_post(path, payload):
    """向后端注入事件（走前端代理 8081）"""
    req = urllib.request.Request(
        f"{BASE}/api{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def gen_trace():
    return str(uuid.uuid4())


def inject_route(bed, route, event_type, confidence=0.91, timeout=False, network="online"):
    """注入带链路/性能/网络标注的事件"""
    is_cloud = route == "cloud"
    is_hybrid = route == "hybrid"
    model = (
        {"model_name": "qwen2.5-14b-instruct", "model_version": "1.0.0-vllm", "inference_ms": 12}
        if is_cloud
        else {"model_name": "qwen2.5-1.5b-instruct", "model_version": "1.0.0-q4", "inference_ms": 208}
    )
    details = {
        "route": route,
        "network": network,
        "trace_id": gen_trace(),
        "route_source": f"TaskRouter: {route}",
        "ttft_ms": 8 if is_cloud else 128,
        "cloud_latency_ms": 460 if (is_cloud or is_hybrid) else None,
        "memory_mb": 640 if is_cloud else 962,
    }
    if timeout:
        details["state_fallback"] = "timeout"
        details["fallback_note"] = "云端 60s 未响应，已按边缘决策回退"
    if network != "online":
        details["state_fallback"] = "cloud_unavailable"
    return api_post("/events", {
        "ward_id": "W-01",
        "bed_id": bed,
        "node_id": f"EDGE-W01-{bed}",
        "event_type": event_type,
        "confidence": confidence,
        "model": model,
        "details": details,
    })


def wait_render(page, ms=1500):
    page.wait_for_timeout(ms)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="docs/evidence/screenshots")
    parser.add_argument("--base", default=BASE)
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 注入三类链路事件 + 一个超时回退事件，供截图展示
    inject_route("B01", "edge", "fall_suspected", confidence=0.94)
    inject_route("B02", "cloud", "seizure", confidence=0.87)
    inject_route("B03", "hybrid", "bed_leave", confidence=0.90)
    inject_route("B01", "cloud", "fall_prediction", confidence=0.82, timeout=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(args.base, wait_until="domcontentloaded")
        wait_render(page, 2500)

        # ---- 场景 1：主看板总览 ----
        page.screenshot(path=str(out_dir / "20260804_frontend_dashboard-overview.png"), full_page=True)
        print("[OK] dashboard-overview")

        # ---- 场景 2：edge 路由事件卡片 ----
        # 截取中间事件面板区域
        panel = page.locator("section.clinical-panel").nth(1)
        panel.screenshot(path=str(out_dir / "20260804_frontend_route-edge-card.png"))
        print("[OK] route-edge-card")

        # ---- 场景 3：打开事件详情抽屉 ----
        cards = page.locator("li.clinical-event-card")
        n = cards.count()
        if n > 0:
            cards.first.click()
            wait_render(page, 1200)
            page.screenshot(path=str(out_dir / "20260804_frontend_event-detail-drawer.png"))
            print("[OK] event-detail-drawer")
            # 关闭抽屉
            page.locator("button.detail-close").click()
            wait_render(page, 600)

        # ---- 场景 4：超时/降级筛选 ----
        timeout_tab = page.locator("text=超时/降级").first
        if timeout_tab.count() > 0:
            timeout_tab.click()
            wait_render(page, 800)
            page.screenshot(path=str(out_dir / "20260804_frontend_timeout-filter.png"))
            print("[OK] timeout-filter")

        # 回到全部
        page.locator("text=全部").first.click()
        wait_render(page, 600)

        browser.close()
    print(f"\n截图完成，输出目录: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
