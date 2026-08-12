<template>
  <div class="model-manage-overlay" v-if="visible" @click.self="$emit('close')">
    <div class="model-manage-panel" role="dialog" aria-modal="true" aria-labelledby="model-manage-title">
      <div class="panel-head">
        <div class="panel-heading">
          <span class="model-mark" aria-hidden="true">ML</span>
          <div>
            <h2 id="model-manage-title">模型版本管理</h2>
            <p>边缘推理模型 · 发布与节点下发 <span v-if="demoMode" class="source-badge">演示配置</span></p>
          </div>
        </div>
        <button class="btn-close" aria-label="关闭模型版本管理" @click="$emit('close')">&times;</button>
      </div>
      <div class="panel-body">
        <div v-if="loading" class="loading">加载中...</div>
        <div v-else-if="models.length === 0" class="loading">暂无模型记录</div>
        <ul v-else class="model-list" aria-live="polite">
          <li v-for="m in models" :key="m.id" class="model-item">
            <div class="model-info">
              <div class="model-name">{{ m.model_name }}<span class="model-ver">@{{ m.model_version }}</span></div>
              <div class="model-meta">
                <span class="model-tag" :class="m.status">{{ statusLabel(m.status) }}</span>
                <span class="model-runtime">{{ m.runtime }} / {{ m.target_device }}</span>
                <span class="model-date">创建: {{ m.created_at?.slice(0, 10) }}</span>
              </div>
            </div>
            <button class="btn-deploy" :disabled="m.status !== 'released'" @click="openDeploy(m)">
              <span class="deploy-mark" aria-hidden="true"></span>下发
            </button>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import api from '../api/index.js'

const props = defineProps({
  visible: Boolean,
  demoMode: { type: Boolean, default: false },
})
const emit = defineEmits(['close'])

const models = ref([])
const loading = ref(false)

const demoModels = [
  {
    id: 'demo-model-edge',
    model_name: 'edge-vision',
    model_version: '1.0.0',
    status: 'released',
    runtime: 'ONNX Runtime',
    target_device: 'NPU',
    created_at: '2026-08-02T09:30:00Z',
  },
  {
    id: 'demo-model-audio',
    model_name: 'audio-fusion',
    model_version: '0.9.4',
    status: 'released',
    runtime: 'TensorRT',
    target_device: 'GPU',
    created_at: '2026-07-28T14:10:00Z',
  },
  {
    id: 'demo-model-qwen',
    model_name: 'qwen2.5-1.5b-instruct',
    model_version: '1.0.0-q4',
    status: 'validating',
    runtime: 'llama.cpp',
    target_device: 'CPU',
    created_at: '2026-08-06T11:45:00Z',
  },
]

const statusLabel = (s) => ({ draft: '草稿', validating: '验证中', released: '已发布', deprecated: '已弃用', rolled_back: '已回滚' }[s] || s)

const loadModels = async () => {
  loading.value = true
  try {
    const res = await api.getModels()
    const records = res.data?.data || []
    models.value = records.length > 0 ? records : (props.demoMode ? demoModels : [])
  } catch (e) {
    console.error('加载模型失败', e)
    models.value = props.demoMode ? demoModels : []
  } finally {
    loading.value = false
  }
}

const openDeploy = (m) => {
  const nodeId = prompt(`输入目标节点 ID（留空则下发到所有节点）：`, 'EDGE-W01-B01')
  if (nodeId === null) return
  api.deployModel(nodeId || 'EDGE-W01-B01', {
    model_name: m.model_name,
    model_version: m.model_version,
    artifact_url: m.artifact_url || 'http://localhost:8001/models/' + m.model_name + '-' + m.model_version + '.onnx',
    checksum: m.checksum || 'sha256:demo',
    runtime: m.runtime || 'onnx',
    target_device: m.target_device || 'npu',
  }).then(() => alert('下发指令已发送')).catch(() => alert('下发失败'))
}

watch(() => props.visible, (v) => { if (v) loadModels() })
</script>

<style scoped>
.model-manage-overlay {
  position: fixed;
  inset: 0;
  padding: 22px;
  background: rgba(23, 43, 46, 0.58);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}
.model-manage-panel {
  width: min(560px, 100%);
  max-height: min(72vh, 680px);
  background: #fffdfa;
  border: 1px solid #d9d3ca;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 24px 64px rgba(23, 43, 46, 0.24), 0 0 0 1px rgba(255, 255, 255, 0.72) inset;
  overflow: hidden;
}
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 16px 18px;
  background: #f6f3ee;
  border-bottom: 1px solid #e1dbd2;
}
.panel-heading {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.model-mark {
  display: inline-grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex: 0 0 auto;
  color: #147976;
  background: #e3f0ee;
  border: 1px solid #b9d9d5;
  border-radius: 8px;
  font: 800 10px/1 'Outfit', sans-serif;
  letter-spacing: 0.04em;
}
.panel-head h2 { margin: 0; color: #1b2a2e; font-size: 15px; font-weight: 800; }
.panel-head p { margin: 3px 0 0; color: #8a9796; font-size: 10px; }
.source-badge {
  display: inline-flex;
  align-items: center;
  margin-left: 5px;
  padding: 1px 5px;
  border: 1px solid #e8c88f;
  border-radius: 4px;
  color: #a96b2b;
  background: #fbefd9;
  font-size: 9px;
  font-weight: 750;
}
.btn-close {
  width: 30px;
  height: 30px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  color: #718083;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 7px;
  font-size: 22px;
  cursor: pointer;
  line-height: 1;
}
.btn-close:hover { color: #1b2a2e; background: #ebe7df; border-color: #d9d3ca; }
.panel-body { flex: 1; min-height: 0; overflow-y: auto; padding: 14px 18px 18px; }
.loading { text-align: center; padding: 34px 20px; color: #718083; font-size: 12px; }
.model-list { list-style: none; display: flex; flex-direction: column; gap: 9px; }
.model-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  padding: 12px 13px;
  background: #fbfaf7;
  border: 1px solid #e1dbd2;
  border-radius: 9px;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}
.model-item:hover { border-color: #b9d9d5; box-shadow: 0 8px 18px rgba(39, 48, 48, 0.08); transform: translateY(-1px); }
.model-info { min-width: 0; }
.model-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; font-weight: 750; color: #1b2a2e; }
.model-ver { margin-left: 5px; color: #147976; font-weight: 550; font-size: 11px; }
.model-meta { display: flex; flex-wrap: wrap; gap: 7px 10px; align-items: center; margin-top: 6px; font-size: 10px; color: #718083; }
.model-tag { padding: 2px 6px; border-radius: 5px; font-weight: 750; }
.model-tag.released { background: #e3f0ee; color: #147976; border: 1px solid #b9d9d5; }
.model-tag.draft { background: #f0efeb; color: #718083; border: 1px solid #d9d3ca; }
.model-tag.validating { background: #fbefd9; color: #a96b2b; border: 1px solid #e8c88f; }
.model-tag.deprecated { background: #f9e6e2; color: #b5574d; border: 1px solid #e8b3aa; }
.model-tag.rolled_back { background: #eeeae3; color: #536367; border: 1px solid #d2cbc1; }
.model-runtime, .model-date { white-space: nowrap; }
.btn-deploy {
  min-width: 58px;
  padding: 6px 11px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  background: #147976;
  color: #fff;
  border: 1px solid #147976;
  border-radius: 7px;
  font-size: 11px;
  font-weight: 750;
  cursor: pointer;
}
.btn-deploy:hover:not(:disabled) { background: #0f6865; border-color: #0f6865; }
.btn-deploy:disabled { background: #e5e2dc; color: #9da4a1; border-color: #d9d3ca; cursor: not-allowed; }
.deploy-mark { width: 7px; height: 7px; border: 1.5px solid currentColor; border-radius: 2px; position: relative; }
.deploy-mark::after { content: ''; position: absolute; width: 4px; height: 1px; left: 5px; top: 2px; background: currentColor; transform: rotate(-35deg); transform-origin: left center; }

@media (max-width: 560px) {
  .model-manage-overlay { padding: 12px; }
  .model-manage-panel { max-height: 82vh; }
  .panel-head { padding: 14px; }
  .panel-body { padding: 12px 14px 14px; }
  .model-item { align-items: flex-start; }
  .btn-deploy { align-self: center; }
}
</style>
