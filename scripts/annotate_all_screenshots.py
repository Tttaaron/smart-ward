"""
对全部演示截图叠加标注（P2 交付物：任务书 §6 截图标注场景/时间/trace_id）

- 事件详情抽屉截图：重新采集并读取页面 DOM 中的真实 trace_id 后标注
- 其他截图：直接对已生成截图叠加 场景+时间 标注
- MQTT 场景 raw 截图：标注后另存为正式命名文件

用法：
  python scripts/annotate_all_screenshots.py [--out DIR] [--base http://localhost:8081]
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from annotate_screenshot import annotate_image

BASE = "http://localhost:8081"
SHOT_DIR = Path("docs/evidence/screenshots")
WHEN = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 场景标注映射（文件名 -> 场景文字）
SCENES = {
    "20260804_frontend_dashboard-overview.png": "主看板总览 · 边缘/云端/协同路由 + 系统状态栏",
    "20260804_frontend_route-edge-card.png": "边缘路由事件卡片 · 模型/TTFT/内存指标",
    "20260804_frontend_timeout-filter.png": "超时/降级事件筛选 · 云端超时回退徽章",
    "20260804_frontend_scenario-cloud-online.png": "云端在线 · 链路/API/节点全绿",
    "20260804_frontend_scenario-cloud-offline-banner.png": "云端断线 · 断网横幅+边缘值守",
    "20260804_frontend_scenario-cloud-recovery-banner.png": "云端恢复 · 恢复横幅+补传条数",
}


def annotate_existing_into(shot_dir: Path):
    """对已生成的正式截图叠加标注（不含详情抽屉，抽屉单独重采）"""
    for name, scene in SCENES.items():
        src = shot_dir / name
        if not src.exists():
            print(f"[skip] 不存在: {name}")
            continue
        dst = shot_dir / name  # 原位覆盖
        annotate_image(str(src), str(dst), scene=scene, when=WHEN)
        print(f"  [标注] {name}")


def annotate_mqtt_raw_into(shot_dir: Path):
    """MQTT 场景 raw 截图 -> 正式命名 + 标注"""
    mqtt_map = {
        "raw_mqtt-online.png": ("20260804_frontend_scenario-mqtt-online.png", "MQTT 在线 · 节点心跳正常"),
        "raw_mqtt-offline.png": ("20260804_frontend_scenario-mqtt-offline.png", "MQTT 中断 · 节点心跳过期"),
        "raw_mqtt-recovered.png": ("20260804_frontend_scenario-mqtt-recovered.png", "MQTT 恢复 · 心跳恢复+补传"),
    }
    for raw, (final_name, scene) in mqtt_map.items():
        src = shot_dir / raw
        if not src.exists():
            print(f"[skip] 不存在: {raw}")
            continue
        dst = shot_dir / final_name
        annotate_image(str(src), str(dst), scene=scene, when=WHEN)
        print(f"  [标注] {final_name}")
        src.unlink()  # 清理 raw


def recapture_detail_with_trace(shot_dir: Path):
    """重新采集事件详情抽屉截图，读取页面 DOM 中的真实 trace_id 并标注"""
    import json
    import urllib.request
    import uuid
    from playwright.sync_api import sync_playwright

    # 先注入一条带 trace_id 的协同路由事件，保证截图可标注真实 trace
    trace_id = str(uuid.uuid4())
    payload = {
        "ward_id": "W-01",
        "bed_id": "B03",
        "node_id": "EDGE-W01-B03",
        "event_type": "bed_leave",
        "confidence": 0.9,
        "model": {"model_name": "qwen2.5-1.5b-instruct", "model_version": "1.0.0-q4", "inference_ms": 205},
        "details": {
            "route": "hybrid",
            "network": "online",
            "trace_id": trace_id,
            "ttft_ms": 132,
            "cloud_latency_ms": 480,
            "memory_mb": 950,
            "route_source": "TaskRouter: hybrid",
        },
    }
    req = urllib.request.Request(
        f"{BASE}/api/events", data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    urllib.request.urlopen(req, timeout=15).read()

    dst = shot_dir / "20260804_frontend_event-detail-drawer.png"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(BASE, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        # 遍历列表前几张卡，找到带真实 trace_id 的事件再截抽屉（真实边缘事件无 trace）
        trace_id = ""
        cards = page.locator("li.clinical-event-card")
        for i in range(min(6, cards.count())):
            cards.nth(i).click()
            page.wait_for_timeout(1000)
            try:
                trace_code = page.locator(".trace-block code").nth(1).inner_text()
            except Exception:
                trace_code = ""
            if trace_code and trace_code != "—":
                trace_id = trace_code
                break
        page.wait_for_timeout(300)
        page.screenshot(path=str(dst))
        browser.close()
    annotate_image(
        str(dst), str(dst),
        scene="事件详情抽屉 · 链路追踪",
        trace=trace_id,
        when=WHEN,
    )
    print(f"  [重采+标注] {dst.name}  (trace_id={trace_id})")
    return dst.name


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(SHOT_DIR))
    args = parser.parse_args()
    out_dir = Path(args.out)
    annotate_existing_into(out_dir)
    annotate_mqtt_raw_into(out_dir)
    recapture_detail_with_trace(out_dir)
    print(f"\n标注完成，输出目录: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
