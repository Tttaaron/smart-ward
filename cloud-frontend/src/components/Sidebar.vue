<template>
  <nav class="sidebar" :class="{ collapsed }" aria-label="主导航">
    <!-- 品牌区 -->
    <router-link to="/" class="brand" aria-label="智慧病房首页">
      <span class="brand-mark" aria-hidden="true">
        <el-icon :size="20"><FirstAidKit /></el-icon>
      </span>
      <span class="brand-copy" v-show="!collapsed">
        <span class="brand-title">智慧病房</span>
        <span class="brand-sub">中央护理工作站 · W-01</span>
      </span>
    </router-link>

    <div class="nav-divider" aria-hidden="true"></div>

    <!-- 导航项 -->
    <div class="nav-list">
      <router-link
        v-for="item in navItemsWithBadge"
        :key="item.name"
        :to="item.to"
        class="nav-item"
        :class="{ active: route.name === item.name }"
        :title="collapsed ? item.label : undefined"
      >
        <span class="nav-icon" aria-hidden="true">
          <el-icon :size="18"><component :is="item.icon" /></el-icon>
        </span>
        <span class="nav-label" v-show="!collapsed">{{ item.label }}</span>
        <span
          v-if="item.badge > 0 && !collapsed"
          class="nav-badge font-num"
          :class="{ 'is-danger': item.badgeTone === 'danger' }"
        >{{ item.badge }}</span>
        <span
          v-else-if="item.badge > 0"
          class="nav-dot-danger"
          aria-hidden="true"
        ></span>
      </router-link>
    </div>

    <div class="nav-spacer" aria-hidden="true"></div>

    <!-- 底部：链路状态 + 演示标识 + 折叠 -->
    <div class="sidebar-foot">
      <div class="link-state" v-show="!collapsed" :title="linkTooltip">
        <span class="dot" :class="linkDotClass" aria-hidden="true"></span>
        <span class="link-label">{{ linkText }}</span>
      </div>
      <div class="link-state" v-show="collapsed" :title="linkTooltip">
        <span class="dot" :class="linkDotClass" aria-hidden="true"></span>
      </div>
      <span v-if="state.demoMode && !collapsed" class="chip chip-warning" title="后端不可用或展示保护已启用，当前使用前端演示数据">演示数据</span>

      <button
        type="button"
        class="collapse-btn"
        :aria-label="collapsed ? '展开导航' : '收起导航'"
        :title="collapsed ? '展开导航' : '收起导航'"
        @click="emit('toggle-collapse')"
      >
        <el-icon :size="16"><component :is="collapsed ? 'Expand' : 'Fold'" /></el-icon>
        <span v-show="!collapsed">收起</span>
      </button>
    </div>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { FirstAidKit, DataBoard, BellFilled, Monitor, Calendar, Cpu } from '@element-plus/icons-vue'
import { useWardStore } from '../stores/ward.js'

defineProps({
  collapsed: { type: Boolean, default: false },
})

const emit = defineEmits(['toggle-collapse'])
const route = useRoute()
const { state } = useWardStore()

const navItems = [
  { name: 'overview', to: '/', label: '总览大屏', icon: DataBoard },
  { name: 'alerts', to: '/alerts', label: '告警中心', icon: BellFilled },
  { name: 'beds', to: '/beds', label: '床位与节点', icon: Monitor },
  { name: 'shifts', to: '/shifts', label: '交班记录', icon: Calendar },
  { name: 'system', to: '/system', label: '系统与模型', icon: Cpu },
]

const pendingCount = computed(
  () => state.events.filter((e) => ['new', 'notified'].includes(e.state)).length
)
// 将待处置数挂在告警中心项上（含 collapsed 模式的红点）
const navItemsWithBadge = computed(() =>
  navItems.map((item) =>
    item.name === 'alerts' ? { ...item, badge: pendingCount.value, badgeTone: 'danger' } : item
  )
)

// 底部链路状态
const linkDotClass = computed(() => {
  if (!state.apiHealthy) return 'alert'
  const s = state.wsStatus.status
  if (s === 'connected') return 'online'
  if (s === 'reconnecting' || s === 'connecting') return 'warn'
  return 'offline'
})
const linkText = computed(() => {
  if (!state.apiHealthy) return '云端不可用'
  const map = { connected: '云端链路在线', connecting: '链路连接中', reconnecting: '链路重连中', disconnected: '链路已断开' }
  return map[state.wsStatus.status] || '链路未知'
})
const linkTooltip = computed(() => {
  if (!state.apiHealthy) return '云端后端无响应（REST 健康探测失败）'
  if (state.wsStatus.status === 'connected') return `WebSocket 已连接 · 累计消息 ${Object.values(state.wsStatus.messageCount || {}).reduce((a, b) => a + b, 0)} 条`
  if (state.wsStatus.status === 'reconnecting') return `第 ${state.wsStatus.reconnectCount} 次重连，指数退避中`
  return 'WebSocket 链路未连接'
})
</script>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  width: 224px;
  flex: 0 0 224px;
  padding: 14px 12px 12px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.95), rgba(255, 255, 255, 0.78) 40%),
    rgba(255, 255, 255, 0.85);
  border-right: 1px solid var(--line);
  backdrop-filter: blur(12px);
  transition: width 0.24s cubic-bezier(0.4, 0, 0.2, 1), flex-basis 0.24s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}
.sidebar.collapsed {
  width: 68px;
  flex-basis: 68px;
  padding-inline: 10px;
}

/* 品牌 */
.brand {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 4px 6px 12px;
  text-decoration: none;
  white-space: nowrap;
}
.brand-mark {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  flex: 0 0 40px;
  color: #FFFFFF;
  background: linear-gradient(135deg, #8FC2FF 0%, #2A7DE1 55%, #164E9F 120%);
  border-radius: 11px;
  box-shadow: 0 6px 18px rgba(42, 125, 225, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.35);
}
.brand-copy { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.brand-title { font-size: 16px; font-weight: 800; color: var(--text); letter-spacing: 0.02em; }
.brand-sub { font-size: 11.5px; font-weight: 600; color: var(--text-3); }

.nav-divider { height: 1px; margin: 0 4px 10px; background: var(--line); }

/* 导航 */
.nav-list { display: flex; flex-direction: column; gap: 4px; }
.nav-spacer { flex: 1; }

.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 11px;
  height: 42px;
  padding: 0 12px;
  border: 1px solid transparent;
  border-radius: 9px;
  color: var(--text-2);
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  white-space: nowrap;
  transition: background 0.18s ease, color 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
}
.nav-item:hover {
  color: var(--text);
  background: rgba(24, 48, 76, 0.05);
}
.nav-item.active {
  color: var(--primary);
  background: var(--primary-soft);
  border-color: rgba(42, 125, 225, 0.28);
  box-shadow: 0 0 14px rgba(42, 125, 225, 0.10);
}
.nav-item.active::before {
  content: '';
  position: absolute;
  left: -13px;
  top: 9px;
  bottom: 9px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--primary);
  box-shadow: 0 0 8px rgba(42, 125, 225, 0.5);
}
.nav-icon {
  display: grid;
  place-items: center;
  width: 22px;
  flex: 0 0 22px;
}
.nav-label { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; }

.nav-badge {
  display: inline-grid;
  place-items: center;
  min-width: 20px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  font-size: 11.5px;
  font-weight: 800;
  color: var(--text-2);
  background: var(--surface-3);
  border: 1px solid var(--line-strong);
}
.nav-badge.is-danger {
  color: #fff;
  background: var(--danger-strong);
  border-color: var(--danger-strong);
  box-shadow: 0 0 10px rgba(220, 38, 38, 0.5);
}
.nav-dot-danger {
  position: absolute;
  right: 14px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--danger);
  box-shadow: 0 0 8px rgba(220, 38, 38, 0.9);
  animation: med-blink 1.2s ease-in-out infinite;
}
.sidebar.collapsed .nav-item {
  justify-content: center;
  padding: 0;
}
.sidebar.collapsed .nav-item.active::before { left: -11px; }

/* 底部 */
.sidebar-foot {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 10px;
  border-top: 1px solid var(--line);
}
.link-state {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 6px;
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text-3);
  white-space: nowrap;
}
.link-label { overflow: hidden; text-overflow: ellipsis; }

.collapse-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 34px;
  border: 1px solid var(--line-strong);
  border-radius: 8px;
  background: transparent;
  color: var(--text-3);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.18s ease;
  white-space: nowrap;
}
.collapse-btn:hover {
  color: var(--primary);
  border-color: rgba(42, 125, 225, 0.4);
  background: var(--primary-soft);
}
</style>
