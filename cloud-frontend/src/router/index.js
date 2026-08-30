import { createRouter, createWebHistory } from 'vue-router'

/**
 * 护士站多视图路由
 * 生产环境由 proxy.py 提供 SPA 回退（未知路径返回 index.html），
 * 开发环境由 Vite dev server 原生支持 history 模式。
 */
const routes = [
  {
    path: '/',
    name: 'overview',
    component: () => import('../views/OverviewView.vue'),
    meta: { title: '总览大屏', sub: 'W-01 病区 · 三楼东侧 · 实时态势' },
  },
  {
    path: '/alerts',
    name: 'alerts',
    component: () => import('../views/AlertsView.vue'),
    meta: { title: '告警中心', sub: '优先级队列 · 实时处置 · 全量归档' },
  },
  {
    path: '/beds',
    name: 'beds',
    component: () => import('../views/BedsView.vue'),
    meta: { title: '床位与节点', sub: '床位态势 · 边缘节点 · 活动轨迹' },
  },
  {
    path: '/shifts',
    name: 'shifts',
    component: () => import('../views/ShiftsView.vue'),
    meta: { title: '交班记录', sub: '临床护理交接摘要 · 班次归档' },
  },
  {
    path: '/system',
    name: 'system',
    component: () => import('../views/SystemView.vue'),
    meta: { title: '系统与模型', sub: '链路健康 · 模型版本 · 服务拓扑' },
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
