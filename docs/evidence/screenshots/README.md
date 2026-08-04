# 护士站前端演示截图素材索引（P2 交付物）

> 采集时间：2026-08-04 · 环境：Windows/x86 Docker 全栈（mqtt-broker + mysql + cloud-backend + cloud-frontend + 3×edge-agent）
> 页面：http://localhost:8081
> 提交号占位：请在最终提交后统一回填 `_<commit>`（任务书 §8.3 命名规范）

| 文件 | 场景 | 标注要素 |
| --- | --- | --- |
| `20260804_frontend_dashboard-overview.png` | 主看板总览 | 三床卡片、系统状态栏全绿（云端链路/API/节点在线）、事件面板含 ⚡边缘 / ☁️云端 / 🔁协同 路由徽章 |
| `20260804_frontend_route-edge-card.png` | 边缘路由事件卡片 | `⚡ 边缘` 徽章、模型 qwen2.5-1.5b@1.0.0-q4、边缘推理耗时 / TTFT / 内存指标 |
| `20260804_frontend_event-detail-drawer.png` | 事件详情抽屉 | **trace_id / event_id / node_id**、链路摘要、性能四宫格（边缘推理/TTFT/云端延迟/内存）、模型版本、时间线、处置记录 |
| `20260804_frontend_timeout-filter.png` | 超时/降级筛选 | “超时/降级”筛选 tab、橙色虚线徽章 `云端超时·边缘回退`、右侧橙色提示条 |
| `20260804_frontend_scenario-cloud-online.png` | 场景·云端在线 | 状态栏云端链路=在线、API=正常、节点 3/3 在线 |
| `20260804_frontend_scenario-cloud-offline-banner.png` | 场景·云端断线 | 状态栏云端链路=不可用(红)、API=不可用(红)、橙色横幅“云端链路中断 · 边缘继续本地值守” |
| `20260804_frontend_scenario-cloud-recovery-banner.png` | 场景·云端恢复 | 绿色横幅“云端链路已恢复”显示恢复时间 + 补传条数，状态栏转绿 |

## 截图回查方法

1. 打开事件详情抽屉，复制 **trace_id**；
2. 按 trace_id 在 cloud-backend 日志/数据库 `safety_events` 中回查：
   ```bash
   docker compose logs cloud-backend | grep <trace_id>
   docker exec smart-ward-mysql-1 mysql -usmart_ward -psmartward_pass smart_ward \
     -e "SELECT event_id,event_type,state,confidence,occurred_at FROM safety_events WHERE details LIKE '%<trace_id>%' ORDER BY occurred_at DESC LIMIT 5;"
   ```

## 重新生成命令

```bash
# 依赖：全栈已启动 + Playwright(Chromium)
python scripts/capture_frontend_screenshots.py --out docs/evidence/screenshots
python scripts/capture_offline_scenario.py --out docs/evidence/screenshots
```

## 原始日志

- `docs/evidence/20260804_frontend_npm-build.log` — 本地 `npm run build` 日志
- `docs/evidence/20260804_frontend_docker-build.log` — `docker compose build cloud-frontend` 日志
