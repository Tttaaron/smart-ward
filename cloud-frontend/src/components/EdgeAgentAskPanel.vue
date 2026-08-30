<template>
  <div class="ask-panel">
    <div class="ask-header">
      <span class="ask-title">边缘 Agent 问答</span>
      <span class="chip chip-ghost">{{ state.demoMode ? '演示' : '边缘 LLM' }}</span>
    </div>

    <div class="ask-form">
      <el-select v-model="state.edgeBedId" size="small" class="ask-bed">
        <el-option value="B01" label="B01 · 张阿姨" />
        <el-option value="B02" label="B02 · 李伯伯" />
        <el-option value="B03" label="B03 · 王奶奶" />
      </el-select>
      <el-input
        v-model="state.agentQuestion"
        size="small"
        placeholder="输入问题，如：今晚离床几次？近7天有什么风险？"
        @keyup.enter="ask"
      />
    </div>

    <div class="ask-quick">
      <button v-for="q in QUICK" :key="q" type="button" class="ask-chip" @click="ask(q)">
        {{ q }}
      </button>
    </div>

    <button type="button" class="ask-submit" :disabled="state.agentAsking" @click="ask(state.agentQuestion)">
      {{ state.agentAsking ? '边缘 Agent 思考中…' : '提问' }}
    </button>

    <div v-if="state.agentAnswer" class="ask-answer">
      <div class="answer-text">{{ state.agentAnswer.answer }}</div>
      <div v-if="state.agentAnswer.time_range || state.agentAnswer.model_name" class="answer-meta">
        <span v-if="state.agentAnswer.time_range">{{ state.agentAnswer.time_range }}</span>
        <span v-if="state.agentAnswer.model_name">{{ state.agentAnswer.model_name }}@{{ state.agentAnswer.model_version }}</span>
        <span v-if="state.agentAnswer.mode" :class="state.agentAnswer.mode === 'real' ? 't-real' : ''">{{ state.agentAnswer.mode }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useWardStore } from '../stores/ward.js'

const store = useWardStore()
const { state } = store

const QUICK = ['本班发生了什么？', '近7天风险趋势？', '上次交班注意什么？']

const ask = (question) => {
  if (!question || !question.trim()) return
  store.askEdgeAgent(question)
}
</script>

<style scoped>
.ask-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: 10px;
}
.ask-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.ask-title { color: var(--primary); font-size: 12.5px; font-weight: 800; }
.ask-form { display: flex; gap: 6px; }
.ask-bed { width: 108px; flex: 0 0 auto; }
.ask-quick { display: flex; flex-wrap: wrap; gap: 5px; }
.ask-chip {
  padding: 3px 8px;
  font-size: 12px;
  color: var(--primary);
  background: rgba(42, 125, 225, 0.07);
  border: 1px solid rgba(42, 125, 225, 0.25);
  border-radius: 999px;
  cursor: pointer;
}
.ask-chip:hover { background: rgba(42, 125, 225, 0.15); }
.ask-submit {
  padding: 6px 0;
  font-size: 12.5px;
  font-weight: 700;
  color: #fff;
  background: var(--primary);
  border: none;
  border-radius: 8px;
  cursor: pointer;
}
.ask-submit:disabled { opacity: 0.6; cursor: not-allowed; }
.ask-answer {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 9px 10px;
  background: rgba(42, 125, 225, 0.05);
  border: 1px solid var(--line);
  border-radius: 8px;
}
.answer-text { color: var(--text-2); font-size: 12.5px; line-height: 1.6; white-space: pre-wrap; }
.answer-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  color: var(--text-3);
  font-size: 11.5px;
  font-weight: 600;
}
.t-real { color: var(--success); }
</style>
