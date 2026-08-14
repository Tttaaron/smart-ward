<template>
  <div class="app-shell">
    <Sidebar :collapsed="collapsed" @toggle-collapse="collapsed = !collapsed" />

    <div class="shell-main">
      <TopBar
        :stats="state.stats"
        :current-time="state.currentTime"
        :page-title="pageTitle"
        :page-sub="pageSub"
        @open-model="state.modelVisible = true"
      />

      <!-- 链路状态条（全局可观测性） -->
      <SystemStatusBar
        :ws-status="state.wsStatus"
        :stats="state.stats"
        :nodes="state.nodes"
        :api-healthy="state.apiHealthy"
        :demo-mode="state.demoMode"
        :presentation-fallback="state.presentationFallback"
      />

      <main class="shell-content">
        <router-view v-slot="{ Component }">
          <transition name="view-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>

      <footer class="shell-footer">
        <span>第一人民医院 · 呼吸与危重症医学科（W-01 病区）</span>
        <span class="foot-divider" aria-hidden="true"></span>
        <span>智慧病房中央护理工作站 <b class="font-num">v0.4.1</b></span>
      </footer>
    </div>

    <!-- 全局浮层 -->
    <LiveMonitor
      :visible="state.monitorVisible"
      :bed-id="state.monitorBedId"
      :event-type="state.monitorEventType"
      :confidence="state.monitorConfidence"
      @close="state.monitorVisible = false"
    />

    <EventDetailDrawer
      :visible="state.detailVisible"
      :event-id="state.detailEventId"
      :fallback-event="detailEvent"
      @close="state.detailVisible = false"
    />

    <ModelManage
      :visible="state.modelVisible"
      :demo-mode="state.demoMode"
      @close="state.modelVisible = false"
    />

    <!-- 调试模拟注入台：仅 ?debug=1 时挂载，不干扰正常演示界面 -->
    <SceneInjector v-if="debugEnabled" />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import Sidebar from '../components/Sidebar.vue'
import TopBar from '../components/TopBar.vue'
import SystemStatusBar from '../components/SystemStatusBar.vue'
import LiveMonitor from '../components/LiveMonitor.vue'
import EventDetailDrawer from '../components/EventDetailDrawer.vue'
import ModelManage from '../components/ModelManage.vue'
import SceneInjector from '../components/SceneInjector.vue'
import { useWardStore } from '../stores/ward.js'

const { state, detailEvent } = useWardStore()
const route = useRoute()

const collapsed = ref(false)
const debugEnabled = new URLSearchParams(window.location.search).get('debug') === '1'

const pageTitle = computed(() => route.meta.title || '总览大屏')
const pageSub = computed(() => route.meta.sub || '')
</script>

<style scoped>
.app-shell {
  display: flex;
  height: 100vh;
  min-height: 0;
  overflow: hidden;
  background: transparent;
}

.shell-main {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
  min-height: 0;
}

.shell-content {
  flex: 1;
  min-height: 0;
  padding: 14px 16px 12px;
  overflow: hidden;
}

.shell-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  flex: 0 0 30px;
  padding: 0 16px;
  font-size: 11px;
  color: var(--text-3);
  border-top: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.6);
  white-space: nowrap;
  overflow: hidden;
}
.shell-footer b { color: var(--primary); font-weight: 700; }
.foot-divider { width: 1px; height: 11px; background: var(--line-strong); }

@media (max-width: 860px) {
  .shell-footer span:first-child { display: none; }
  .foot-divider { display: none; }
}
</style>
