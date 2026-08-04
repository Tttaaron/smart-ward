"""
护士站演示流程录屏脚本（P2 交付物：任务书 §6 录屏素材，供 P6 剪辑）

Playwright 自动录制真实页面的演示流程，输出 webm 视频。
流程（约 70 秒）：
  1. 主看板总览 + 系统状态栏
  2. 注入 边缘/云端/协同 + 云端超时 事件
  3. 事件卡片路由徽章滚动展示
  4. 打开事件详情抽屉（含 trace_id）
  5. 超时/降级筛选
  6. 恢复全部视图

用法：
  python scripts/record_demo_video.py [--out DIR]
"""
import argparse
import json
import time
import urllib.request
import uuid
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8081"


def gen_trace():
    return str(uuid.uuid4())


def inject_route(bed, route, event_type, confidence=0.91, timeout=False):
    is_cloud = route == "cloud"
    is_hybrid = route == "hybrid"
    model = (
        {"model_name": "qwen2.5-14b-instruct", "model_version": "1.0.0-vllm", "inference_ms": 12}
        if is_cloud
        else {"model_name": "qwen2.5-1.5b-instruct", "model_version": "1.0.0-q4", "inference_ms": 208}
    )
    details = {
        "route": route,
        "network": "online",
        "trace_id": gen_trace(),
        "route_source": f"TaskRouter: {route}",
        "ttft_ms": 8 if is_cloud else 128,
        "cloud_latency_ms": 460 if (is_cloud or is_hybrid) else None,
        "memory_mb": 640 if is_cloud else 962,
    }
    if timeout:
        details["state_fallback"] = "timeout"
        details["fallback_note"] = "云端 60s 未响应，已按边缘决策回退"
    payload = {
        "ward_id": "W-01",
        "bed_id": bed,
        "node_id": f"EDGE-W01-{bed}",
        "event_type": event_type,
        "confidence": confidence,
        "model": model,
        "details": details,
    }
    req = urllib.request.Request(
        f"{BASE}/api/events", data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="docs/evidence/videos")
    args = parser.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 预注入三类链路 + 超时事件，让视频从"有内容"开始
    inject_route("B01", "edge", "fall_suspected", confidence=0.94)
    inject_route("B02", "cloud", "seizure", confidence=0.87)
    inject_route("B03", "hybrid", "bed_leave", confidence=0.90)
    inject_route("B01", "cloud", "fall_prediction", confidence=0.82, timeout=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(out_dir / "_pw_profile"),
            headless=True,
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(out_dir),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(BASE, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)

        # 1) 主看板总览（3s）
        page.wait_for_timeout(3000)

        # 2) 滚动病床卡片列
        page.mouse.wheel(0, 300)
        page.wait_for_timeout(1500)
        page.mouse.wheel(0, -300)
        page.wait_for_timeout(1200)

        # 3) 事件面板滚动展示路由徽章（向下滚再滚回）
        page.mouse.move(900, 400)
        for _ in range(3):
            page.mouse.wheel(0, 500)
            page.wait_for_timeout(900)
        page.mouse.wheel(0, -1500)
        page.wait_for_timeout(1200)

        # 4) 打开事件详情抽屉（带 trace_id 的协同事件）
        cards = page.locator("li.clinical-event-card")
        for i in range(min(6, cards.count())):
            cards.nth(i).click()
            page.wait_for_timeout(900)
            try:
                t = page.locator(".trace-block code").nth(1).inner_text()
            except Exception:
                t = ""
            if t and t != "—":
                break
        page.wait_for_timeout(4000)  # 停留展示抽屉内容
        page.locator("button.detail-close").click()
        page.wait_for_timeout(1200)

        # 5) 超时/降级筛选
        page.locator("text=超时/降级").first.click()
        page.wait_for_timeout(2500)
        # 回到全部
        page.locator("text=全部").first.click()
        page.wait_for_timeout(1500)

        # 6) 顶部状态栏特写（移动鼠标到状态栏位置，展示六态芯片）
        page.mouse.move(960, 130)
        page.wait_for_timeout(2500)

        context.close()  # 关闭 context 时才落盘视频

    videos = list(out_dir.glob("*.webm"))
    if videos:
        v = videos[0]
        print(f"[OK] 演示视频已录制: {v} ({v.stat().st_size / 1024 / 1024:.1f} MB)")
    else:
        print("[warn] 未生成视频文件，请检查 Playwright 录屏配置")
    print(f"输出目录: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
