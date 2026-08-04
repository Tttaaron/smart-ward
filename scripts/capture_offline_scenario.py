"""
护士站断网/恢复场景截图脚本（P2 交付物：异常状态视觉提示演示）

流程：
  1. 页面在线态截图
  2. 停止 cloud-backend 容器 -> 等待 WS 断开 -> 断网横幅截图
  3. 重启 cloud-backend 容器 -> 等待 WS 恢复 -> 恢复横幅截图

用法：
  python scripts/capture_offline_scenario.py [--out DIR] [--base http://localhost:8081]
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
    parser.add_argument("--base", default=BASE)
    args = parser.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(args.base, wait_until="networkidle")
        page.wait_for_timeout(2000)

        # 1) 在线态
        page.screenshot(path=str(out_dir / "20260804_frontend_scenario-cloud-online.png"))
        print("[OK] cloud-online")

        # 2) 停止 cloud-backend，模拟云端不可用
        run_cmd(f"{COMPOSE} stop cloud-backend")
        print("[STEP] cloud-backend stopped, waiting for WS disconnect...")
        # 等待 WS 进入 reconnecting / 断网横幅出现（最多 40s）
        offline_seen = False
        for _ in range(40):
            page.wait_for_timeout(1000)
            if page.locator(".status-banner.offline").count() > 0:
                offline_seen = True
                break
        page.wait_for_timeout(1500)  # 让横幅完整显示
        page.screenshot(path=str(out_dir / "20260804_frontend_scenario-cloud-offline-banner.png"))
        print(f"[OK] cloud-offline-banner (banner_seen={offline_seen})")

        # 3) 重启 cloud-backend，模拟网络恢复
        run_cmd(f"{COMPOSE} start cloud-backend")
        print("[STEP] cloud-backend started, waiting for recovery banner...")
        recovery_seen = False
        for _ in range(60):
            page.wait_for_timeout(1000)
            if page.locator(".status-banner.recovery").count() > 0:
                recovery_seen = True
                break
        page.wait_for_timeout(1200)
        page.screenshot(path=str(out_dir / "20260804_frontend_scenario-cloud-recovery-banner.png"))
        print(f"[OK] cloud-recovery-banner (banner_seen={recovery_seen})")

        browser.close()
    print(f"\n断网/恢复场景截图完成: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
