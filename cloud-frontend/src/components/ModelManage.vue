<template>
  <div class="model-manage-overlay" v-if="visible" @click.self="$emit('close')">
    <div class="model-manage-panel">
      <div class="panel-head">
        <h2>🧠 模型版本管理</h2>
        <button class="btn-close" @click="$emit('close')">&times;</button>
      </div>
      <div class="panel-body">
        <div v-if="loading" class="loading">加载中...</div>
        <div v-else-if="models.length === 0" class="loading">暂无模型记录</div>
        <ul v-else class="model-list">
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
              下发
            </button>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import api from '../api/index.js'

const props = defineProps({ visible: Boolean })
const emit = defineEmits(['close'])

const models = ref([])
const loading = ref(false)

const statusLabel = (s) => ({ draft: '草稿', validating: '验证中', released: '已发布', deprecated: '已弃用', rolled_back: '已回滚' }[s] || s)

const loadModels = async () => {
  loading.value = true
  try {
    const res = await api.getModels()
    models.value = res.data?.data || []
  } catch (e) {
    console.error('加载模型失败', e)
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
  background: rgba(0,0,0,0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}
.model-manage-panel {
  background: #fff;
  border-radius: 10px;
  width: 520px;
  max-height: 70vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3);
}
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid #eee;
}
.panel-head h2 { font-size: 15px; margin: 0; color: #1d2129; }
.btn-close { background: none; border: none; font-size: 22px; color: #86909c; cursor: pointer; }
.panel-body { flex: 1; overflow-y: auto; padding: 12px 16px; }
.loading { text-align: center; padding: 30px; color: #86909c; font-size: 12px; }
.model-list { list-style: none; display: flex; flex-direction: column; gap: 8px; }
.model-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  background: #f5f9ff;
  border: 1px solid #d6e4ff;
  border-radius: 6px;
}
.model-name { font-size: 13px; font-weight: 600; color: #1d2129; }
.model-ver { color: #1677ff; font-weight: 400; font-size: 11px; }
.model-meta { display: flex; gap: 8px; align-items: center; margin-top: 4px; font-size: 10px; color: #86909c; }
.model-tag { padding: 1px 5px; border-radius: 3px; font-weight: 600; }
.model-tag.released { background: #e8f8e8; color: #00b42a; border: 1px solid #b7eb8f; }
.model-tag.draft { background: #f5f5f5; color: #86909c; border: 1px solid #e5e5e5; }
.model-tag.validating { background: #fff7e6; color: #fa8c16; border: 1px solid #ffd9a8; }
.model-tag.deprecated { background: #fff0f0; color: #f53f3f; border: 1px solid #ffccc7; }
.model-tag.rolled_back { background: #f5f5f5; color: #4e5969; border: 1px solid #e5e5e5; }
.btn-deploy {
  padding: 4px 12px;
  background: #1677ff;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
}
.btn-deploy:disabled { background: #d9d9d9; color: #aaa; cursor: not-allowed; }
</style>
