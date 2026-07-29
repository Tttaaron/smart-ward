# 智慧病房护士工作站 - React 前端交接文档

> **面向角色**：前端开发（景彬）
> **技术栈**：React 18 + TypeScript + Vite + Ant Design 5 + Tailwind CSS + ECharts + Zustand + Axios
> **当前参考实现**：`cloud-frontend/`（Vue 3 + Element Plus，本文档与其对照）
> **后端契约基线**：`cloud-backend/` FastAPI v0.3.0 + `contracts/` MQTT JSON Schema v1
> **文档版本**：v1.0 · 2026-07-29

---

## 目录

- [一、护士工作站功能需求分析](#一护士工作站功能需求分析)
  - [1.1 业务定位](#11-业务定位)
  - [1.2 功能清单总表](#12-功能清单总表)
  - [1.3 核心业务流程](#13-核心业务流程)
  - [1.4 事件优先级与响应时效要求](#14-事件优先级与响应时效要求)
  - [1.5 护士站不做的事（边界约束）](#15-护士站不做的事边界约束)
- [二、React 技术栈与工程结构](#二react-技术栈与工程结构)
  - [2.1 技术选型](#21-技术选型)
  - [2.2 建议目录结构](#22-建议目录结构)
  - [2.3 路由规划](#23-路由规划)
  - [2.4 主题与设计 Token](#24-主题与设计-token)
- [三、后端 API 契约（联调唯一标准）](#三后端-api-契约联调唯一标准)
  - [3.1 统一响应信封](#31-统一响应信封)
  - [3.2 REST 接口清单](#32-rest-接口清单)
  - [3.3 WebSocket 协议](#33-websocket-协议)
  - [3.4 前端开发需注意的契约陷阱](#34-前端开发需注意的契约陷阱)
- [四、组件设计与拆分](#四组件设计与拆分)
  - [4.1 页面布局总览](#41-页面布局总览)
  - [4.2 组件清单与职责](#42-组件清单与职责)
  - [4.3 状态管理设计（Zustand）](#43-状态管理设计zustand)
- [五、关键业务规则实现指南](#五关键业务规则实现指南)
  - [5.1 事件状态机](#51-事件状态机)
  - [5.2 告警音频双保险机制](#52-告警音频双保险机制)
  - [5.3 等待计时器与超时判定](#53-等待计时器与超时判定)
  - [5.4 P1 告警强提示](#54-p1-告警强提示)
  - [5.5 ECharts 生命周期](#55-echarts-生命周期)
  - [5.6 WebSocket 断线重连与心跳](#56-websocket-断线重连与心跳)
- [六、硬编码清单与改造建议](#六硬编码清单与改造建议)
- [七、数据流与刷新链路](#七数据流与刷新链路)
- [八、参考实现映射表](#八参考实现映射表)
- [九、验收标准](#九验收标准)

---

## 一、护士工作站功能需求分析

### 1.1 业务定位

护士工作站是整个智慧病房系统**唯一的人工交互入口与处置闭环节点**。系统定位为「辅助提示 + 人工复核」：
- 边缘端产出**疑似事件**与**辅助提示**，不直接诊断、不自动临床控制
- 所有事件必须由护士主动确认（acknowledge / resolve / false_positive / escalate）才能流转到终态
- 护士站面向 **1920×1080 护士站大屏**，操作极简，护士无需培训
- 所有展示数据需脱敏（仅匿名别名，不存真实姓名/病历号；原始视频留边缘端，仅上传脱敏证据指针）

### 1.2 功能清单总表

| # | 功能模块 | 子功能 | 说明 | 数据来源 |
|---|---|---|---|---|
| **1** | **顶栏状态总览** | 品牌 + 值班信息 | 医院名称、科室、值班护士/医生 | 硬编码/登录态 |
| | | 实时时钟 | 日期 + 中文星期 + 时分秒（每秒刷新） | 前端定时器 |
| | | 关键指标看板 | 总床位、在床数、离床数、监测节点在线率、P1 待处置数 | `GET /api/stats` |
| | | P1 特急强提示 | p1_pending > 0 时红色脉冲动画 | `stats.p1_pending` |
| **2** | **病区床位可视化** | 病区卡片 | 病区名、位置、待处理告警数、传感器数 | `GET /api/wards` |
| | | 床位卡片网格 | 床号、护理等级、患者别名、性别年龄、医护、风险标签、床位状态、待处理事件数 | `wards[].beds[]` + 硬编码映射 |
| | | 床位告警脉冲 | pending_events > 0 时卡片红色脉冲动画 | `bed.pending_events` |
| **3** | **护理告警与呼叫中心**（核心） | 事件列表 | 50 条近期事件，按时间倒序 | `GET /api/events?hours=24&limit=50` |
| | | 事件筛选 | 全部 / P1特急 / 待到场 / 已归档 四个 tab | 前端 filter |
| | | 优先级标识 | P1 红 / P2 橙 / P3 蓝 左边框 + 徽章 | `event.priority` |
| | | 事件类型中文映射 | 13 类事件类型 -> 中文名称 | 前端映射表 |
| | | 事件状态标签 | 未到场 / 到场中 / 已归档 / 误报 / 升级 | `event.state` |
| | | 等待计时器 | 显示「已等待 MM:SS」，超 3 分钟变红 | `occurred_at` + 每秒刷新 |
| | | P1 闪烁 | P1 且未到场时左边框闪烁 | 优先级 + 状态 |
| | | 四类处置动作 | 立即到场 / 确认处置 / 标记误报 / 科室升级 | `POST /api/events/{id}/ack` |
| **4** | **实时事件推送** | WebSocket 连接 | 自动重连 + 心跳 | `ws://.../ws` |
| | | 新事件推入 | 收到 safety_event 时 unshift 到列表头部 | WS `safety_event` |
| | | P1 告警音频 | P1 或指定事件类型触发告警音 | WS `safety_event` |
| | | 状态同步广播 | 收到 event_ack 时更新对应事件状态 | WS `event_ack` |
| | | 节点健康更新 | 收到 node_health 时刷新统计 | WS `node_health` |
| | | 交接班更新 | 收到 shift_summary 时刷新摘要 | WS `shift_summary` |
| **5** | **交接班管理** | 班次选择 | 日期 + 白班/晚班/夜班 | 前端选择 |
| | | 生成摘要 | 按班次聚合事件统计，幂等覆盖 | `POST /api/shift-summaries/generate` |
| | | 历史摘要列表 | 摘要正文 + P1/P2/已处置/误报统计 + 签名 | `GET /api/shift-summaries` |
| **6** | **数据可视化** | 事件趋势图 | 24h 按小时分桶折线图 | `GET /api/events` 聚合 |
| | | 事件类别占比 | 24h 按类型环形饼图 | `GET /api/events/by-type` |
| | | 节点延迟看板 | 边缘节点心跳延迟柱状图，10s 轮询 | `GET /api/nodes` |
| **7** | **调试注入台**（演示用） | 场景注入 | 选床位 + 置信度 + 13 类事件按钮 | `POST /api/events` |
| | | 注入反馈 | 成功/失败 toast 提示 | 响应 code |

### 1.3 核心业务流程

**事件闭环**（系统最核心链路）：

```
边缘端采集+推理+融合
      │  MQTT 上报 (QoS 1)
      ▼
云端入库 (state: notified) ──→ WebSocket 推送护士站
      │                              │
      │                              ▼
      │                    护士看到告警卡片
      │                    P1: 红闪 + 音频
      │                    P2: 橙色高亮
      │                    P3: 蓝色待办
      │                              │
      │                    护士点击处置动作
      │                    (acknowledge/resolve/
      │                     false_positive/escalate)
      │                              │
      ◄──────────────────────────── POST /api/events/{id}/ack
      │
云端更新 state + 写 dispositions + 写 audit_logs
      │ MQTT 下行 ack
      ▼
边缘端同步状态 → 终态 (resolved/false_positive/escalated)
```

**前端刷新链路**（收到 WS 消息后）：
- `safety_event` → 新事件 unshift 到列表（上限 50）→ P1 触发音频 → 刷新 stats/wards/两个图表
- `event_ack` → 按 event_id 找到事件 → 更新 state → 刷新 stats/wards/趋势图
- `node_health` → 刷新 stats/wards/节点延迟图
- `shift_summary` → 刷新交接摘要列表/趋势图

### 1.4 事件优先级与响应时效要求

| 优先级 | 视觉表现 | 响应时效目标 | 事件类型 |
|--------|----------|-------------|----------|
| **P1 紧急** | 红色闪烁 + 告警音频 + 置顶 | ≤ 2s 显示，立即确认 | fall_suspected, nurse_call, fall_prediction, seizure |
| **P2 高级** | 橙色高亮 | 5 分钟内确认 | bed_leave, door_departure, night_wandering, long_still, abnormal_posture |
| **P3 提醒** | 蓝色待办 | 进入队列可批量处理 | environment_anomaly, node_offline, bedsore_risk, device_fault |

### 1.5 护士站不做的事（边界约束）

> 以下约束直接影响前端文案与交互设计，务必遵守。

1. **不做诊断**：所有事件仅显示为「疑似 XX」，是否真实由护士到场判断。文案不能用确定性表述（如「患者已跌倒」），只能用「疑似跌倒」「检测到异常体态」。
2. **不做自动临床控制**：环境控制（空调/灯光/新风）属非医疗设备；所有事件处置必须护士主动点击，无自动关闭告警。
3. **不替代医护**：系统是辅助提示工具，不能作为医疗事故责任划分唯一依据。
4. **不存敏感数据**：不显示真实姓名/身份证/病历号，仅匿名别名（如「张阿姨」）；原始视频留边缘端，前端仅展示 `evidence_refs` 脱敏指针。
5. **不做训练管理**：协同训练（端口 8002）与实时业务隔离，护士站不涉及。

---

## 二、React 技术栈与工程结构

### 2.1 技术选型

| 层面 | 选型 | 理由 |
|------|------|------|
| 框架 | **React 18** + TypeScript | 团队决定 |
| 构建 | **Vite 5** | 与现有一致，快 |
| UI 库 | **Ant Design 5** | 后台/医疗场景组件最全，TS 原生支持 |
| 样式 | **Tailwind CSS 3** | 设计 token 统一，与 Ant Design 共存 |
| 图表 | **ECharts 5** + `echarts-for-react` | 与现有一致，保留 option 配置 |
| HTTP | **axios** | 拦截器统一处理信封 |
| 状态管理 | **Zustand** | 轻量，替代 Vue 的组件内 ref |
| 路由 | **React Router 6** | 预留多页扩展（当前单页） |
| WebSocket | 自封装 hook `useWebSocket` | 保留 ping/pong + 3s 重连 |

> Ant Design 与 Tailwind 共存需注意：Tailwind 的 base reset 会影响 Ant Design 样式，建议在 `tailwind.config.js` 设置 `corePlugins: { preflight: false }`，或使用 `@tailwind base` 时隔离。

### 2.2 建议目录结构

```
cloud-frontend-react/
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.ts
├── postcss.config.js
├── tsconfig.json
├── src/
│   ├── main.tsx                      # 入口
│   ├── App.tsx                       # 根布局 + 路由
│   ├── api/
│   │   ├── client.ts                 # axios 实例 + 拦截器
│   │   ├── wards.ts                  # 病区/床位
│   │   ├── events.ts                 # 事件 + 处置
│   │   ├── nodes.ts                  # 节点健康
│   │   ├── stats.ts                  # 统计
│   │   ├── shift.ts                  # 交接班
│   │   ├── models.ts                 # 模型管理
│   │   ├── env.ts                    # 环境控制
│   │   └── observations.ts           # 观测数据
│   ├── hooks/
│   │   ├── useWebSocket.ts           # WS 连接 + 心跳 + 重连
│   │   ├── useNow.ts                 # 每秒刷新的当前时间
│   │   └── usePolling.ts             # 通用轮询 hook
│   ├── store/
│   │   ├── useWardStore.ts           # 病区/床位数据
│   │   ├── useEventStore.ts          # 事件列表 + ack
│   │   ├── useStatsStore.ts          # 全局统计
│   │   ├── useShiftStore.ts          # 交接班
│   │   └── useAuthStore.ts           # 操作人身份（替代硬编码）
│   ├── components/
│   │   ├── layout/
│   │   │   └── TopBar.tsx            # 顶栏
│   │   ├── ward/
│   │   │   ├── WardCard.tsx          # 病区卡片
│   │   │   └── BedCard.tsx           # 床位卡片
│   │   ├── event/
│   │   │   ├── EventPanel.tsx        # 告警工作台
│   │   │   └── EventCard.tsx         # 单事件卡片
│   │   ├── shift/
│   │   │   └── ShiftPanel.tsx        # 交接班面板
│   │   ├── chart/
│   │   │   ├── EventTrendChart.tsx   # 事件趋势/占比
│   │   │   └── NodeLatencyChart.tsx  # 节点延迟
│   │   └── debug/
│   │       └── SceneInjector.tsx     # 调试注入台
│   ├── pages/
│   │   └── NurseStation.tsx          # 护士站主页面
│   ├── config/
│   │   ├── constants.ts              # 所有硬编码常量（见第六节）
│   │   ├── eventTypes.ts             # 事件类型中文映射 + 优先级映射
│   │   ├── bedConfig.ts             # 床位护理等级/患者/医护映射
│   │   └── theme.ts                  # Ant Design theme token
│   ├── types/
│   │   ├── api.ts                    # API 响应/请求类型
│   │   ├── event.ts                  # 事件/状态/优先级枚举
│   │   └── ws.ts                     # WebSocket 消息类型
│   ├── utils/
│   │   ├── audio.ts                  # 告警音频双保险
│   │   ├── time.ts                   # 时间格式化（兼容 UTC Z 后缀）
│   │   └── ackStateMap.ts           # action -> state 映射
│   └── styles/
│       └── theme.css                # 全局 CSS 变量 + Tailwind 指令
└── nginx.conf                        # 生产代理 /api /ws
```

### 2.3 路由规划

当前为单页应用，但预留路由：

```tsx
<Routes>
  <Route path="/" element={<NurseStation />} />
  {/* 预留 */}
  <Route path="/event/:eventId" element={<EventDetail />} />
  <Route path="/admin/models" element={<ModelManagement />} />
</Routes>
```

开发环境 Vite 代理配置（`vite.config.ts`）：
```ts
server: {
  host: '0.0.0.0',
  port: 5174,
  proxy: {
    '/api': { target: 'http://localhost:8001', changeOrigin: true },
    '/ws':  { target: 'ws://localhost:8001', ws: true, changeOrigin: true }
  }
}
```

### 2.4 主题与设计 Token

沿用现有医疗蓝浅色主题，通过 Ant Design ConfigProvider + Tailwind 双通道注入：

```ts
// src/config/theme.ts
import type { ThemeConfig } from 'antd'

export const antdTheme: ThemeConfig = {
  token: {
    colorPrimary: '#1677ff',
    colorSuccess: '#00b42a',
    colorWarning: '#ff7d00',
    colorError: '#f53f3f',
    colorInfo: '#86909c',
    borderRadius: 6,
    fontSize: 12,
  },
}

// tailwind.config.ts 扩展 med 色板
// colors.med = { bg, surface, surface-2, border, primary, primary-light,
//                text, text-2, text-3, success, warning, danger, info }
```

CSS 变量定义在 `src/styles/theme.css`（与现有 Vue 版一致）：
```css
:root {
  --color-bg: #f0f5ff;
  --color-surface: #ffffff;
  --color-surface-2: #f5f9ff;
  --color-border: #d6e4ff;
  --color-primary: #1677ff;
  --color-primary-light: #4096ff;
  --color-text: #1d2129;
  --color-text-2: #4e5969;
  --color-text-3: #86909c;
  --color-success: #00b42a;
  --color-warning: #ff7d00;
  --color-danger: #f53f3f;
  --color-info: #86909c;
}
```

---

## 三、后端 API 契约（联调唯一标准）

> **联调唯一标准**：以后端实际行为为准。契约文档见 `docs/06-接口规范.md`，MQTT Schema 见 `contracts/`。

### 3.1 统一响应信封

所有业务接口统一返回：
```ts
interface ApiResponse<T> {
  code: number       // 0 = 成功；非 0 = 错误（值与 HTTP 状态码相同）
  message: string    // "success" 或错误详情
  data: T | null     // 业务数据；错误时为 null
}
```

**特例**：`GET /health` 返回 `{"status":"ok"}`，`GET /` 返回 `{"message":"..."}`，均不走信封。

axios 拦截器建议：
```ts
// 统一解包 + 错误集中处理
apiClient.interceptors.response.use(
  (res) => {
    const body = res.data
    if (body.code !== undefined && body.code !== 0) {
      return Promise.reject(new Error(body.message || '请求失败'))
    }
    return body.data  // 直接返回 data，业务层无需再 .data.data
  },
  (err) => Promise.reject(err)
)
```

### 3.2 REST 接口清单

Base URL：`/api`（开发经 Vite 代理，生产经 nginx 代理）。

#### 病区与床位

| # | 方法 | 路径 | 说明 | Query/Body |
|---|------|------|------|-------------|
| 1 | GET | `/api/wards` | 全部病区（含 beds + nodes + pending_alerts） | - |
| 2 | GET | `/api/wards/{ward_id}` | 病区详情（不含 nodes/pending_alerts） | - |
| 3 | GET | `/api/beds/occupancy` | 床位占用 | `ward_id?` |

`GET /api/wards` 响应：
```jsonc
{
  "code": 0, "message": "success",
  "data": [{
    "id": "W-01", "name": "普通病房 W-01",
    "ward_type": "general", "location": "三楼东侧", "status": "online",
    "beds": [
      { "id": "B01", "name": "1床", "status": "idle", "patient_alias": "张阿姨", "pending_events": 0 }
    ],
    "nodes": [
      { "id": "EDGE-W01-B01", "status": "online", "bed_id": "B01",
        "last_heartbeat": "2026-07-29T10:00:00Z", "buffered_events": 0 }
    ],
    "pending_alerts": 0   // priority in (P1,P2) 且 state in (new,notified,acknowledged)
  }]
}
```

#### 安全事件

| # | 方法 | 路径 | 说明 | Query/Body |
|---|------|------|------|-------------|
| 4 | GET | `/api/events` | 事件列表（多条件过滤） | `ward_id?, bed_id?, priority?, state?, event_type?, hours=24, limit=100` |
| 5 | GET | `/api/events/{event_id}` | 事件详情（含 dispositions） | - |
| 6 | POST | `/api/events/{event_id}/ack` | 确认/处置/升级事件 | body 见下 |
| 7 | POST | `/api/events` | 手动注入事件（演示用） | body 见下 |
| 8 | GET | `/api/events/by-type` | 按类型统计最近 N 小时 | `hours=24` |

`GET /api/events` 响应（事件对象结构）：
```jsonc
{
  "event_id": "uuid", "ward_id": "W-01", "node_id": "EDGE-W01-B01", "bed_id": "B01",
  "event_type": "bed_leave", "priority": "P2", "state": "notified",
  "confidence": 0.92,
  "model_name": "rule-fusion-v1", "model_version": "0.1.0-mock", "inference_ms": 5,
  "evidence_refs": [], "rule_hits": [], "details": {},
  "occurred_at": "2026-07-29T10:00:00Z",
  "acknowledged_at": null, "resolved_at": null
}
```
响应还含顶层 `total` 字段。Query 参数范围：`hours` 1~168，`limit` 1~1000。

`POST /api/events/{event_id}/ack` 请求体：
```jsonc
{
  "action": "resolve",              // 必填，正则 ^(acknowledge|resolve|false_positive|escalate)$
  "operator_id": "nurse-01",       // 必填，1~50 字符
  "operator_name": "李护士",       // 可选，最长 50
  "operator_role": "nurse",        // 可选，正则 ^(nurse|charge_nurse|admin|observer)$
  "result": "已处置",              // 可选，最长 200
  "note": "患者已躺回床位"          // 可选，最长 2000
}
```
后端同步更新状态 + MQTT 下行到边缘 + 写 audit_logs。前端不应等待边缘端回执。

`POST /api/events`（注入）请求体：字段均可选（`ward_id` 默认 W-01，`bed_id` 默认 B01，`event_type` 默认 nurse_call，`confidence` 默认 0.9）。落库时 state 强制为 `notified`。

`GET /api/events/by-type` 响应：`{ "bed_leave": 12, "nurse_call": 5 }`。**注意**：无数据时返回 404「事件不存在」，前端需捕获并当作空对象处理。

#### 节点健康

| # | 方法 | 路径 | 说明 | Query |
|---|------|------|------|--------|
| 9 | GET | `/api/nodes` | 边缘节点列表 | `ward_id?` |

响应：
```jsonc
{
  "id": "EDGE-W01-B01", "ward_id": "W-01", "bed_id": "B01",
  "status": "online",                  // online / degraded / offline
  "model_version": "0.1.0-mock",
  "last_heartbeat": "2026-07-29T10:00:00Z",
  "buffered_events": 0                 // 断网积压事件数
}
```

#### 系统统计

| # | 方法 | 路径 | 说明 |
|---|------|------|------|
| 10 | GET | `/api/stats` | 全局统计（建议每秒轮询） |

响应：
```jsonc
{
  "total_wards": 1, "total_beds": 3,
  "online_nodes": 3, "total_nodes": 3,
  "events_today": 5,                   // UTC 0 点起算
  "pending_events": 2,                 // state in (new,notified,acknowledged)
  "p1_pending": 1                      // priority=P1 且同 state 集合
}
```

#### 交接班

| # | 方法 | 路径 | 说明 | Query/Body |
|---|------|------|------|-------------|
| 11 | GET | `/api/shift-summaries` | 摘要列表（按 created_at 倒序） | `ward_id?, shift_date?, limit=20` |
| 12 | POST | `/api/shift-summaries/generate` | 生成摘要（幂等覆盖） | body 见下 |

`GET /api/shift-summaries` 响应：
```jsonc
{
  "id": 1, "ward_id": "W-01",
  "shift_date": "2026-07-29",          // YYYY-MM-DD 字符串
  "shift_period": "day",               // day / evening / night
  "operator_id": "auto",
  "summary_text": "2026-07-29 白班交接班摘要：共发生 5 起事件（P1 1 起，P2 2 起），已处置 4 起...",
  "event_count": 5, "p1_count": 1, "p2_count": 2,
  "resolved_count": 4, "false_positive_count": 1,
  "avg_response_seconds": 120
}
```

`POST /api/shift-summaries/generate` 请求体：
```jsonc
{
  "ward_id": "W-01",                   // 必填，最长 10
  "shift_date": "2026-07-29",          // 必填，YYYY-MM-DD
  "shift_period": "day",              // 默认 day，^(day|evening|night)$
  "operator_id": "nurse-01"           // 默认 "auto"，最长 50
}
```
班次时段（按本地时区 +08:00 换算 UTC 查询）：day 08-16 / evening 16-24 / night 00-08。同 `ward_id + shift_date + shift_period` 覆盖原记录。

#### 观测数据 / 模型管理 / 环境控制（预留，当前未使用）

| # | 方法 | 路径 | 说明 |
|---|------|------|------|
| 13 | GET | `/api/observations?bed_id&source_type&hours=1&limit=100` | 观测历史 |
| 14 | GET | `/api/models` | 模型版本列表 |
| 15 | POST | `/api/models/deploy?node_id=` | 模型下发（node_id 在 Query！） |
| 16 | POST | `/api/env/control` | 环境控制（device: ac/light/fresh_air，action: on/off） |

### 3.3 WebSocket 协议

端点：`ws://{host}:{port}/ws`（开发用 `window.location` 推导，生产经 nginx 代理 `/ws`）。

**心跳**：服务端每 30s 发 `{"type":"ping"}`，客户端必须回 `{"type":"pong"}`，否则 60s 断开。

**服务端推送消息类型**（共 5 种业务 + 1 种心跳）：

```ts
type WsMessage =
  | { type: 'safety_event'; event_id: string; ward_id: string; node_id: string;
      bed_id: string; event_type: string; priority: 'P1'|'P2'|'P3';
      state: string; confidence: number; occurred_at: string; data: any }
  | { type: 'event_ack'; event_id: string; action: string;
      operator: { id: string; name?: string; role: string } }
  | { type: 'node_health'; node_id: string; ward_id: string;
      status: 'online'|'degraded'|'offline'; timestamp: string }
  | { type: 'shift_summary'; ward_id: string; shift_date: string;
      shift_period: string; summary_text: string; event_count: number }
  | { type: 'observation'; ward_id: string; node_id: string; bed_id: string;
      data: any; timestamp: string }   // 每 3s 推送，当前前端未深度使用
  | { type: 'ping' }                     // 心跳，客户端回 pong
```

### 3.4 前端开发需注意的契约陷阱

> 以下均为现有后端的实际行为，React 侧需针对性处理，避免踩坑。

1. **事件详情与列表字段结构不同**：
   - 列表（`GET /api/events`）：扁平 `model_name` / `model_version` / `inference_ms`，含 `acknowledged_at` / `resolved_at` / `node_id`。
   - 详情（`GET /api/events/{event_id}`）：嵌套 `model: {name, version, inference_ms}`，含 `dispositions` 数组，**不含** `acknowledged_at` / `resolved_at`。
   - 前端类型定义需区分 `EventListItem` 与 `EventDetail`。

2. **时间字段后缀 `Z` 不规范**：后端用 `datetime.isoformat() + "Z"` 拼接，对 aware datetime 可能产生 `+00:00Z` 异常后缀。前端解析时间时建议先 `replace('+00:00', '')` 再 `new Date()`。

3. **`GET /api/events/by-type` 无数据返回 404**：而非空对象。前端需 `catch` 后返回 `{}`。

4. **`POST /api/models/deploy` 的 `node_id` 是 Query 参数**，不在 body 中。

5. **`POST /api/events`（注入）接收 `dict` 无强校验**：前端需自行保证字段合法性。

6. **错误响应**：`{"code": <http状态码>, "message": <detail>, "data": null}`，HTTP 状态码与 `code` 同值。

7. **CORS 全开放 `*`**：生产环境建议收敛。

---

## 四、组件设计与拆分

### 4.1 页面布局总览

```
┌─────────────────────────────────────────────────────────────────┐
│  TopBar  品牌 | 值班信息 | [总床位][在床][离床][节点][P1] | 时钟    │  ~84px
├──────────────────┬──────────────────┬────────────────────────────┤
│  左栏 (1.55fr)    │  中栏 (1.15fr)   │  右栏 (1.15fr)              │
│                  │                  │                            │
│  WardCard         │  EventPanel      │  ShiftPanel                │
│   └ BedCard 网格  │   └ 事件卡片列表 │   └ 交接摘要列表           │
│                  │     (50 条)      │                            │
│  ─────────────   │     筛选 tab     │  ─────────────             │
│                  │     处置按钮组    │                            │
│  NodeLatencyChart │                  │  EventTrendChart           │
│   (10s 轮询)      │                  │   (趋势/占比 双 tab)       │
├──────────────────┴──────────────────┴────────────────────────────┤
│  Footer  第一人民医院 · 呼吸与危重症医学科 · v0.3.0                │
└─────────────────────────────────────────────────────────────────┘
                                       SceneInjector (右侧浮动抽屉)
```

Grid：`grid-template-columns: 1.55fr 1.15fr 1.15fr`，高度 `calc(100vh - 84px)`，`overflow: hidden`，各栏独立滚动。

### 4.2 组件清单与职责

| 组件 | 职责 | Ant Design 组件映射 | 数据来源 |
|------|------|---------------------|----------|
| **TopBar** | 顶栏：品牌、值班信息、指标看板、时钟 | `Row`/`Col` + `Statistic` + `Badge` | `stats` store + `useNow` |
| **WardCard** | 单病区容器：标题 + 床位网格 | `Card` | `wards` store |
| **BedCard** | 单床位卡片：床号、护理等级、患者、医护、风险标签、状态 | `Card` + `Tag` + `Tooltip` | `bed` prop + `bedConfig` |
| **EventPanel** | 告警工作台：筛选 + 事件列表 | `Radio.Group`(button) + `Empty` + `Badge` | `events` store |
| **EventCard** | 单事件卡片：优先级边框 + 状态 + 计时器 + 处置按钮 | `Tag` + `Button.Group` | `event` prop |
| **ShiftPanel** | 交接班：日期/班次选择 + 生成 + 摘要列表 | `DatePicker` + `Select` + `Button`(loading) + `Timeline` | `shift` store |
| **EventTrendChart** | 事件趋势折线/类别占比饼图（双 tab） | `Radio.Group` + `Button` + ECharts | `events` API + `events/by-type` API |
| **NodeLatencyChart** | 节点心跳延迟柱状图（10s 轮询） | `Card` + `Button` + ECharts | `nodes` API |
| **SceneInjector** | 调试注入台（浮动抽屉） | `Drawer` + `Select` + `Slider` + `Button` | `injectEvent` API |

### 4.3 状态管理设计（Zustand）

> 现有 Vue 版把状态全堆在 App.vue，React 侧建议拆分 store。

```ts
// store/useAuthStore.ts —— 替代硬编码操作人
interface AuthState {
  operator: { id: string; name: string; role: 'nurse'|'charge_nurse'|'admin'|'observer' }
  wardId: string  // 默认 'W-01'
}

// store/useStatsStore.ts —— 顶栏指标
interface StatsStore {
  stats: Stats | null
  loadStats: () => Promise<void>
}

// store/useEventStore.ts —— 事件列表
interface EventStore {
  events: EventListItem[]
  loadEvents: (params?) => Promise<void>
  unshiftEvent: (evt) => void      // WS safety_event 时调用
  updateEventState: (id, state) => void  // WS event_ack / 本地 ack 时调用
  ackEvent: (eventId, action) => Promise<void>
}

// store/useWardStore.ts —— 病区/床位
interface WardStore {
  wards: Ward[]
  loadWards: () => Promise<void>
}

// store/useShiftStore.ts —— 交接班
interface ShiftStore {
  summaries: ShiftSummary[]
  shiftDate: string
  shiftPeriod: 'day'|'evening'|'night'
  generating: boolean
  loadSummaries: () => Promise<void>
  generate: () => Promise<void>
}
```

---

## 五、关键业务规则实现指南

### 5.1 事件状态机

```
new → notified → acknowledged → ┬→ resolved        (终态)
                                ├→ false_positive  (终态)
                                └→ escalated       (终态)
```

- `new`：边缘端新建（落库时被强制改为 `notified`，前端基本不会见到）
- `notified`：云端已入库并推送到护士站（云端自动）
- `acknowledged`：护士点击「立即到场」
- `resolved`/`false_positive`/`escalated`：终态，不可逆

**action -> state 映射**（前端 ack 和 WS event_ack 两处共用，务必抽成单一工具函数）：

```ts
// utils/ackStateMap.ts
export const ACTION_TO_STATE: Record<string, EventState> = {
  acknowledge:    'acknowledged',
  resolve:       'resolved',
  false_positive:'false_positive',
  escalate:      'escalated',
}
```

**「待处理」事件集合** = `state in (new, notified, acknowledged)`（统计口径，与后端一致）。

**处置按钮显示条件**：仅 `state in (new, notified, acknowledged)` 显示；「立即到场」按钮额外要求 `state !== 'acknowledged'`。

### 5.2 告警音频双保险机制

收到 WS `safety_event` 时，满足以下条件之一即触发告警音频：
- `msg.priority === 'P1'`，**或**
- `msg.event_type in [fall_suspected, nurse_call, seizure, fall_prediction]`

**双保险实现**（React 侧用 `useRef` 持有 AudioContext，避免重复创建）：
1. 主路径：`new Audio('/alert.mp3').play()`
2. 回退（文件不存在/浏览器拦截）：Web Audio API 合成双音警笛
   - 880Hz 正弦波 0.2s + 660Hz 正弦波 0.25s
   - 增益 0.3，指数衰减到 0.01
3. 浏览器自动播放策略：首次需用户交互后才能播放，建议页面加载时加一个「点击启用告警」提示。

```ts
// utils/audio.ts
let audioCtx: AudioContext | null = null

export function playBeep() {
  const audio = new Audio('/alert.mp3')
  audio.play().catch(() => synthesizeBeep())
}

function synthesizeBeep() {
  audioCtx ??= new (window.AudioContext || (window as any).webkitAudioContext)()
  const playTone = (freq: number, dur: number, offset: number) => {
    const osc = audioCtx!.createOscillator()
    const gain = audioCtx!.createGain()
    osc.connect(gain); gain.connect(audioCtx!.destination)
    osc.type = 'sine'
    osc.frequency.setValueAtTime(freq, audioCtx!.currentTime + offset)
    gain.gain.setValueAtTime(0.3, audioCtx!.currentTime + offset)
    gain.gain.exponentialRampToValueAtTime(0.01, audioCtx!.currentTime + offset + dur - 0.05)
    osc.start(audioCtx!.currentTime + offset)
    osc.stop(audioCtx!.currentTime + offset + dur)
  }
  playTone(880, 0.2, 0)
  playTone(660, 0.25, 0.25)
}
```

### 5.3 等待计时器与超时判定

- 仅对 `state in (new, notified, acknowledged)` 的事件显示计时器
- 计算：`now - occurred_at`，格式 `已等待 MM:SS`
- **超时阈值：180 秒（3 分钟）**，超时后计时器变红
- 实现：组件内 `useNow()`（每秒刷新），或独立 `useWaitTimer(event.occurred_at)` hook

### 5.4 P1 告警强提示

| 触发点 | 表现 |
|--------|------|
| 顶栏 P1 计数 | `stats.p1_pending > 0` 时红色脉冲动画（`med-text-pulse` 1.2s） |
| 事件卡片左边框 | P1 且 `state in (new, notified)` 时闪烁（`p1-card-blink` 1.2s，红↔透明） |
| 告警音频 | 见 5.2 |

### 5.5 ECharts 生命周期

React 侧用 `echarts-for-react` 或原生 + `useEffect`，注意：
- `onMounted` 等价：`useEffect(() => { init + fetchData }, [])`
- `onUnmounted` 等价：`return () => { chart.dispose(); removeEventListener }`
- 监听 `window resize` 调 `chart.resize()`
- 两个图表组件需通过 `forwardRef + useImperativeHandle` 暴露 `fetchData()`，供父组件在 ack/WS 推送时主动刷新（对应 Vue 的 `defineExpose`）

**ECharts 浅色配色**（与 Vue 版一致）：
- tooltip 背景 `#fff`，边框 `#d6e4ff`，文字 `#1d2129`
- 坐标轴文字 `#86909c`，网格线 `#f0f0f0`
- 折线主色 `#1677ff` + 渐变面积
- 饼图配色 7 色 `['#1677ff','#4096ff','#f53f3f','#ff7d00','#00b42a','#722ed1','#eb2f96']`
- 柱状延迟图：<5s 绿渐变、5-15s 橙渐变、≥15s/离线 红渐变

### 5.6 WebSocket 断线重连与心跳

封装为 `useWebSocket` hook：
- 连接地址：`ws://${window.location.hostname}:${window.location.port}/ws`（生产经 nginx 代理为 `/ws`，同源）
- 收到 `{type:'ping'}` 自动回 `{type:'pong'}`
- `onclose` 非主动关闭时，`setTimeout(connect, 3000)` 重连
- `onMessage(cb)` 注册回调（支持多个）
- 组件卸载时 `disconnect()`

---

## 六、硬编码清单与改造建议

> 现有 Vue 版有大量硬编码，React 侧建议集中到 `config/` 下，部分改为运行时注入。

| # | 硬编码项 | 当前值 | 位置 | 改造建议 |
|---|---------|--------|------|----------|
| 1 | 病区 ID | `'W-01'` | loadShiftSummaries、generateShiftSummary、injectEvent | 抽到 `useAuthStore.wardId` |
| 2 | 操作人身份 | `operator_id='nurse-demo'`, `operator_name='演示护士'`, `operator_role='nurse'` | ackEvent、generateShiftSummary | 抽到 `useAuthStore.operator`，未来接登录 |
| 3 | 床位护理等级映射 | B01 特级/B02 Ⅰ级/B03 Ⅱ级 | BedCard | 抽到 `config/bedConfig.ts` |
| 4 | 床位患者信息 | B01 张阿姨 男68 / B02 李伯伯 女74 / B03 王奶奶 男59 | BedCard | 同上（演示数据，正式应后端下发） |
| 5 | 医护姓名 | 张莉/王主任/李秀/陈医师/王婷/刘医师 | BedCard | 同上 |
| 6 | 风险标签 | 防跌倒/防压疮/禁食/高龄/防坠床 | BedCard | 同上 |
| 7 | 顶栏值班信息 | 护士 张莉(主管护师) / 医生 王主任 | TopBar | 抽到 `config` 或登录态 |
| 8 | 交班/接班人 | 交班 张莉 / 接班 李秀 | ShiftPanel | 抽到 `config` |
| 9 | 顶栏指标兜底默认值 | total_beds=3, occupied_beds=2, leave_beds=1 | TopBar | 去掉兜底，后端无数据时显示 0 或 loading |
| 10 | 事件列表参数 | hours=24, limit=50 | loadEvents | 抽到常量 |
| 11 | 交接摘要参数 | ward_id=W-01, limit=10 | loadShiftSummaries | ward_id 从 authStore 取 |
| 12 | 告警音频触发条件 | P1 或 [fall_suspected, nurse_call, seizure, fall_prediction] | playBeep 调用处 | 抽到 `config/constants.ts` |
| 13 | 音频文件路径 | `/alert.mp3` | playBeep | 常量 |
| 14 | 等待超时阈值 | 180 秒 | EventPanel | 常量 `WAIT_TIMEOUT_SECONDS` |
| 15 | 节点离线延迟封顶 | 60 秒 | NodeLatencyChart | 常量 `NODE_OFFLINE_LATENCY_CAP` |
| 16 | 节点延迟配色阈值 | <5s 绿 / 5-15s 橙 / ≥15s 红 | NodeLatencyChart | 常量 `LATENCY_THRESHOLDS` |
| 17 | 班次时段定义 | day 08-16 / evening 16-24 / night 00-08 | ShiftPanel | 常量 `SHIFT_PERIODS` |
| 18 | 事件列表上限 | 50 条 | WS unshift 后 pop | 常量 `EVENT_LIST_MAX` |
| 19 | 轮询间隔 | stats 1s / nodes 10s | App、NodeLatencyChart | 常量 `POLL_INTERVALS` |
| 20 | 版本号 | v0.3.0 | Footer | 从 `package.json` 读取 |
| 21 | 三栏布局比例 | 1.55fr 1.15fr 1.15fr | App | 常量或 CSS 变量 |

### 事件类型中文映射（`config/eventTypes.ts`）

```ts
export const EVENT_TYPE_LABELS: Record<string, string> = {
  fall_suspected:      '疑似跌倒 (突发危险)',
  nurse_call:          '护士呼叫 (患者求助)',
  bed_leave:           '患者离床 (离床预警)',
  door_departure:      '门区异常 (离走风险)',
  night_wandering:     '夜间徘徊 (离床夜游)',
  environment_anomaly: '环境异常 (病房监测)',
  node_offline:        '节点失联 (设备断连)',
  fall_prediction:     '坠床预警 (体态危险)',
  long_still:          '长时间静止 (体征监护)',
  abnormal_posture:    '异常体态 (姿势异常)',
  seizure:             '抽搐检测 (身体抽动)',
  bedsore_risk:        '压疮预防 (翻身提醒)',
  device_fault:        '设备故障 (网络异常)',
}

// event_type -> 默认优先级（与后端 priority_map 一致）
export const EVENT_TYPE_PRIORITY: Record<string, 'P1'|'P2'|'P3'> = {
  fall_suspected: 'P1', nurse_call: 'P1', fall_prediction: 'P1', seizure: 'P1',
  bed_leave: 'P2', door_departure: 'P2', night_wandering: 'P2',
  long_still: 'P2', abnormal_posture: 'P2',
  environment_anomaly: 'P3', node_offline: 'P3', bedsore_risk: 'P3', device_fault: 'P3',
}

// 事件状态中文映射
export const EVENT_STATE_LABELS: Record<string, string> = {
  new: '未到场', notified: '未到场',
  acknowledged: '护士到场中',
  resolved: '已归档完成',
  false_positive: '判定误报',
  escalated: '升级上报',
}

// 床位状态中文映射
export const BED_STATUS_LABELS: Record<string, string> = {
  idle: '空闲', occupied: '在床', alert: '告警/呼叫中', maintenance: '设备维护',
}

// 班次定义
export const SHIFT_PERIODS = [
  { value: 'day',     label: '白班 (08:00 - 16:00)' },
  { value: 'evening', label: '晚班 (16:00 - 24:00)' },
  { value: 'night',   label: '夜班 (00:00 - 08:00)' },
]
```

---

## 七、数据流与刷新链路

### 初始加载（进入页面时）

```
loadWards ──┐
loadEvents(hours:24, limit:50) ──┤
loadStats ──┤  并发执行
loadShiftSummaries(ward_id:W-01, limit:10) ──┘
              │
              ▼
        连接 WebSocket
        注册 onMessage 回调
              │
              ▼
     启动 1s 定时器（更新时钟 + loadStats）
```

### 两个独立轮询定时器

| 定时器 | 间隔 | 职责 | 所在组件 |
|--------|------|------|----------|
| App 级 | 1s | 更新 `currentTime` + `loadStats` | `useStatsStore` + `useNow` |
| NodeLatencyChart 级 | 10s | 拉取节点状态 | `NodeLatencyChart` 组件内 |

### WebSocket 推送触发的刷新链路

| WS 消息 | 处理动作 |
|---------|----------|
| `safety_event` | ① unshift 新事件到列表头（仅取关键字段）② 超 50 条 pop 末尾 ③ 满足条件触发 `playBeep` ④ 刷新 `wards`/`stats`/两图表 |
| `event_ack` | ① 按 `event_id` 找到事件 ② 按 `action->state` 映射更新 ③ 刷新 `wards`/`stats`/趋势图 |
| `node_health` | 刷新 `stats`/`wards`/节点延迟图 |
| `shift_summary` | 刷新交接摘要列表/趋势图 |

### 图表主动刷新点

App 在以下时机通过 ref 调用图表组件的 `fetchData()`：
- 本地 `ack` 成功后
- WS 收到 `safety_event` / `event_ack` / `node_health` / `shift_summary` 后

---

## 八、参考实现映射表

> 现有 Vue 版作为参考，React 侧对照迁移。

| Vue 组件 | React 组件 | 关键差异 |
|----------|------------|----------|
| `App.vue`（全局状态 + WS 分发 + 音频） | `NurseStation.tsx` + 各 Zustand store + `useWebSocket` hook | 状态拆分到 store，WS 逻辑抽到 hook |
| `TopBar.vue` | `components/layout/TopBar.tsx` | 指标用 `Statistic`，P1 脉冲用 CSS animation |
| `WardCard.vue` + `BedCard.vue` | `components/ward/WardCard.tsx` + `BedCard.tsx` | bed.id 映射抽到 `config/bedConfig.ts` |
| `EventPanel.vue`（含事件卡片） | `components/event/EventPanel.tsx` + `EventCard.tsx` | 拆分更细，筛选用 `Radio.Group` |
| `ShiftPanel.vue` | `components/shift/ShiftPanel.tsx` | 日期用 `DatePicker`，列表用 `Timeline` |
| `EventTrendChart.vue` | `components/chart/EventTrendChart.tsx` | `echarts-for-react` + `useImperativeHandle` |
| `NodeLatencyChart.vue` | `components/chart/NodeLatencyChart.tsx` | 同上 + `usePolling` hook |
| `SceneInjector.vue` | `components/debug/SceneInjector.tsx` | `Drawer` 替代手写浮动抽屉 |
| `api/index.js`（16 函数） | `api/*.ts`（按业务拆分） | 拦截器统一解包信封 |
| `api/websocket.js` | `hooks/useWebSocket.ts` | 保留 ping/pong + 3s 重连 |
| `styles/theme.css` | `styles/theme.css` + `config/theme.ts` | Ant Design ConfigProvider + Tailwind 双通道 |

---

## 九、验收标准

React 版护士工作站完成时，应满足以下全部标准：

### 功能验收
- [ ] 三栏布局正确渲染（左栏病区床位+节点图、中栏告警工作台、右栏交接班+趋势图）
- [ ] 顶栏指标看板实时更新（每秒刷新 stats）
- [ ] 床位卡片正确显示护理等级/患者/医护/风险标签/状态
- [ ] 床位有待处理事件时红色脉冲动画
- [ ] 事件列表加载 50 条，筛选 tab（全部/P1/待到场/已归档）正确过滤
- [ ] 事件优先级左边框 + 徽章颜色正确（P1红/P2橙/P3蓝）
- [ ] 事件等待计时器每秒刷新，超 3 分钟变红
- [ ] P1 事件左边框闪烁
- [ ] 四类处置按钮点击后状态正确流转（acknowledge→acknowledged 等）
- [ ] 处置后事件卡片按钮组消失（终态）
- [ ] 交接班日期/班次选择 + 生成摘要成功 + 历史列表显示
- [ ] 事件趋势图/占比图切换 + 数据正确
- [ ] 节点延迟图 10s 轮询 + 延迟配色正确（<5s绿/5-15s橙/≥15s红）
- [ ] 调试注入台注入事件成功后 toast 提示

### 实时性验收
- [ ] WebSocket 连接成功，收到 ping 自动回 pong
- [ ] WS 断线后 3s 自动重连
- [ ] 收到 `safety_event` 时新事件 unshift 到列表头
- [ ] P1 事件推送时告警音频播放（主路径或 Web Audio 回退）
- [ ] 收到 `event_ack` 时对应事件状态更新
- [ ] 收到 `node_health`/`shift_summary` 时对应数据刷新

### 视觉验收
- [ ] 医疗蓝浅色主题（#f0f5ff 底 + #1677ff 主色）
- [ ] Ant Design 主色覆盖为 #1677ff
- [ ] ECharts 图表浅色可读，文字/网格线清晰
- [ ] 1920×1080 分辨率下布局不溢出

### 工程验收
- [ ] TypeScript 无 any 满天飞，API 类型完整
- [ ] 硬编码集中到 `config/`，无散落魔法数字
- [ ] `action->state` 映射为单一工具函数，无重复
- [ ] `npm run build` 无报错
- [ ] Docker 构建（Dockerfile 复用现有两阶段：node 编译 + python 代理）成功
- [ ] http://localhost:8081 返回 200，页面正常

---

## 附：关键文件路径索引

供 React 开发者进一步查阅的参考资源：

| 资源 | 路径 |
|------|------|
| 现有 Vue 参考实现 | `cloud-frontend/src/` |
| 后端路由 + WS | `cloud-backend/app/main.py` |
| 后端请求模型 | `cloud-backend/app/schemas.py` |
| 后端 ORM（11 表） | `cloud-backend/app/database.py` |
| WebSocket 管理 | `cloud-backend/app/websocket_manager.py` |
| MQTT 处理 | `cloud-backend/app/mqtt_handler.py` |
| 数据库 DDL + 初始数据 | `cloud-backend/init.sql` |
| MQTT 契约 Schema | `contracts/`（6 份 JSON Schema） |
| 事件字典 | `docs/00-事件字典.md` |
| MQTT 契约文档 | `docs/01-MQTT契约.md` |
| 接口规范（21 路由 + WS 全示例） | `docs/06-接口规范.md` |
| 架构设计 | `docs/05-架构设计.md` |
| 需求分析 | `docs/04-需求分析.md` |
| 服务编排 | `docker-compose.yml` |
| 版本记录 | `CHANGELOG.md`（注意 v0.3.0 移除输液监测的破坏性变更） |

---

**文档结束。如有疑问，对照现有 Vue 实现 `cloud-frontend/src/` 或后端 `cloud-backend/app/main.py`。**
