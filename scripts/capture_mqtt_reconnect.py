"""
护士站 MQTT 重连 / 数据补传场景截图脚本（P2 交付物）

流程：
  1. 页面在线态：节点心跳正常、MQTT 在线截图
  2. 停止 mqtt-broker 容器 -> 等待边缘节点心跳过期 -> 心跳中断/MQTT 异常截图
  3. 恢复 mqtt-broker -> 等待节点重连、心跳恢复 -> 恢复截图

用法：
  python scripts/capture_mqtt_reconnect.py [--out DIR]
"""
import argparse
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8081"
COMPOSE = "docker compose -f docker-compose.yml"


def run_cmd(cmd, cwd=None):
    subprocess.run(cmd, shell=True, check=False, cwd=cwd)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="docs/evidence/screenshots")
    args = parser.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(BASE, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # 1) 正常态（MQTT 在线，心跳正常）
        page.screenshot(path=str(out_dir / "raw_mqtt-online.png"))
        print("[OK] mqtt-online (raw)")

        # 2) 停止 MQTT Broker
        run_cmd(f"{COMPOSE} stop mqtt-broker")
        print("[STEP] mqtt-broker stopped, waiting for heartbeat expiry...")
        # 等心跳过期（>45s），最多 90s
        degraded_seen = False
        for _ in range(90):
            page.wait_for_timeout(1000)
            hb_text = page.locator(".status-chip").nth(3).inner_text()  # 节点心跳 chip
            if "中断" in hb_text or "0/3" in hb_text:
                degraded_seen = True
                break
        page.wait_for_timeout(1000)
        page.screenshot(path=str(out_dir / "raw_mqtt-offline.png"))
        print(f"[OK] mqtt-offline (raw) degraded_seen={degraded_seen}")

        # 3) 恢复 MQTT Broker
        run_cmd(f"{COMPOSE} start mqtt-broker")
        print("[STEP] mqtt-broker started, waiting for heartbeat recovery...")
        recovered = False
        for _ in range(60):
            page.wait_for_timeout(1000)
            hb_text = page.locator(".status-chip").nth(3).inner_text()
            if "3/3" in hb_text and "中断" not in hb_text:
                recovered = True
                break
        page.wait_for_timeout(1500)
        page.screenshot(path=str(out_dir / "raw_mqtt-recovered.png"))
        print(f"[OK] mqtt-recovered (raw) recovered={recovered}")

        browser.close()
    print(f"\nMQTT 场景 raw 截图完成: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
