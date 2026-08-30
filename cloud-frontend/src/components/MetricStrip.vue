<template>
  <div class="metric-strip" :class="{ 'is-compact': compact }">
    <div
      v-for="item in items"
      :key="item.key"
      class="metric-card"
      :class="'acc-' + (item.tone || 'neutral')"
    >
      <span class="metric-icon" aria-hidden="true">
        <el-icon :size="17"><component :is="item.icon" /></el-icon>
      </span>
      <div class="metric-copy">
        <span class="metric-label">{{ item.label }}</span>
        <strong class="metric-value font-num">{{ item.value }}</strong>
      </div>
      <span v-if="item.hint && !compact" class="metric-hint">{{ item.hint }}</span>
    </div>
  </div>
</template>

<script setup>
/**
 * 指标带：总览与告警中心共用的统计卡组件。
 * 抽成组件是为了让两处统计卡的视觉语言完全一致——评审时跨页翻动，
 * 卡片样式不统一会显得拼凑。
 */
defineProps({
  items: { type: Array, required: true, default: () => [] },
  // 紧凑模式：隐藏右侧说明文字，用于窄栏
  compact: { type: Boolean, default: false },
})
</script>

<style scoped>
.metric-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  flex: 0 0 auto;
}

.metric-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 13px 14px;
  background:
    linear-gradient(180deg,
      color-mix(in srgb, var(--metric-accent, var(--primary)) 7%, transparent),
      transparent 58%),
    var(--surface-2);
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  overflow: hidden;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}
.metric-card:hover {
  transform: translateY(-2px);
  border-color: color-mix(in srgb, var(--metric-accent, var(--primary)) 35%, transparent);
  box-shadow: var(--shadow-card-hover);
}

/* 顶部强调条：语义身份标识 */
.metric-card::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 3px;
  background: var(--metric-accent, var(--primary));
  opacity: 0.85;
}

.metric-card.acc-danger { --metric-accent: var(--danger); }
.metric-card.acc-warning { --metric-accent: var(--warning); }
.metric-card.acc-accent { --metric-accent: var(--accent); }
.metric-card.acc-success { --metric-accent: var(--success); }
.metric-card.acc-primary { --metric-accent: var(--primary); }
.metric-card.acc-neutral { --metric-accent: var(--info); }

.metric-icon {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  border-radius: 10px;
  color: var(--metric-accent, var(--primary));
  background: color-mix(in srgb, var(--metric-accent, var(--primary)) 13%, transparent);
  border: 1px solid color-mix(in srgb, var(--metric-accent, var(--primary)) 32%, transparent);
}

.metric-copy { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.metric-label {
  color: var(--text-3);
  font-size: var(--fs-caption);
  font-weight: 700;
  white-space: nowrap;
}
.metric-value {
  color: var(--metric-accent, var(--text));
  font-size: var(--fs-hero);
  font-weight: 800;
  line-height: 1.05;
  white-space: nowrap;
}

.metric-hint {
  margin-left: auto;
  align-self: flex-end;
  color: var(--text-3);
  font-size: var(--fs-micro);
  font-weight: 600;
  white-space: nowrap;
}

@media (max-width: 1280px) {
  .metric-strip { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 760px) {
  .metric-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
