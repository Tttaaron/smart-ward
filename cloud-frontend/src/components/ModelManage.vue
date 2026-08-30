<template>
  <!-- 弹窗模式（默认） -->
  <div v-if="visible && !embedded" class="model-manage-overlay" @click.self="$emit('close')">
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
        <ModelList :models="models" :loading="loading" @deploy="openDeploy" />
      </div>
    </div>
  </div>

  <!-- 内嵌模式（系统视图内直接渲染列表，无遮罩） -->
  <div v-else-if="embedded" class="model-manage-embedded">
    <ModelList :models="models" :loading="loading" @deploy="openDeploy" />
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { h, defineComponent } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api/index.js'

const props = defineProps({
  visible: Boolean,
  demoMode: { type: Boolean, default: false },
  // 内嵌模式：渲染无遮罩的模型列表（供系统视图使用），visible 可省略
  embedded: { type: Boolean, default: false },
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

const openDeploy = async (m) => {
  let nodeId
  try {
    const result = await ElMessageBox.prompt(
      '输入目标节点 ID（留空则下发到所有节点）',
      `下发 ${m.model_name}@${m.model_version}`,
      {
        confirmButtonText: '下发',
        cancelButtonText: '取消',
        inputValue: 'EDGE-W01-B01',
        inputPlaceholder: 'EDGE-W01-B01',
      }
    )
    nodeId = result.value
  } catch (e) {
    return // 用户取消
  }

  try {
    await api.deployModel(nodeId || 'EDGE-W01-B01', {
      model_name: m.model_name,
      model_version: m.model_version,
      artifact_url: m.artifact_url || 'http://localhost:8001/models/' + m.model_name + '-' + m.model_version + '.onnx',
      checksum: m.checksum || 'sha256:demo',
      runtime: m.runtime || 'onnx',
      target_device: m.target_device || 'npu',
    })
    ElMessage.success('下发指令已发送')
  } catch (e) {
    ElMessage.error('下发失败')
  }
}

watch(() => props.visible, (v) => { if (v) loadModels() })
onMounted(() => {
  if (props.embedded) loadModels()
})

// ---- 内嵌复用的模型列表子组件（与弹窗共享同一份数据） ----
const ModelList = defineComponent({
  props: {
    models: { type: Array, default: () => [] },
    loading: { type: Boolean, default: false },
  },
  emits: ['deploy'],
  setup(props, { emit }) {
    return () => {
      if (props.loading) {
        return h('div', { class: 'loading' }, '加载中...')
      }
      if (props.models.length === 0) {
        return h('div', { class: 'loading' }, '暂无模型记录')
      }
      return h('ul', { class: 'model-list', 'aria-live': 'polite' }, props.models.map((m) =>
        h('li', { class: 'model-item', key: m.id }, [
          h('div', { class: 'model-info' }, [
            h('div', { class: 'model-name' }, [
              m.model_name,
              h('span', { class: 'model-ver' }, `@${m.model_version}`),
            ]),
            h('div', { class: 'model-meta' }, [
              h('span', { class: ['model-tag', m.status] }, statusLabel(m.status)),
              h('span', { class: 'model-runtime' }, `${m.runtime} / ${m.target_device}`),
              h('span', { class: 'model-date' }, `创建: ${m.created_at?.slice(0, 10)}`),
            ]),
          ]),
          h('button', {
            class: 'btn-deploy',
            disabled: m.status !== 'released',
            onClick: () => emit('deploy', m),
          }, [
            h('span', { class: 'deploy-mark', 'aria-hidden': 'true' }),
            '下发',
          ]),
        ])
      ))
    }
  },
})
</script>

<style scoped>
/* ---- 弹窗模式 ---- */
.model-manage-overlay {
  position: fixed;
  inset: 0;
  padding: 22px;
  background: rgba(24, 48, 76, 0.35);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}
.model-manage-panel {
  width: min(560px, 100%);
  max-height: min(72vh, 680px);
  background: var(--surface-2);
  border: 1px solid var(--line-strong);
  border-radius: 14px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 26px 70px rgba(24, 48, 76, 0.25), 0 0 0 1px rgba(255, 255, 255, 0.9) inset;
  overflow: hidden;
}
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 16px 18px;
  background: var(--surface-3);
  border-bottom: 1px solid var(--line);
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
  width: 34px;
  height: 34px;
  flex: 0 0 auto;
  color: var(--primary);
  background: var(--primary-soft);
  border: 1px solid rgba(42, 125, 225, 0.35);
  border-radius: 9px;
  font: 800 11.5px/1 'Outfit', sans-serif;
  letter-spacing: 0.04em;
  box-shadow: 0 0 10px rgba(42, 125, 225, 0.14);
}
.panel-head h2 { margin: 0; color: var(--text); font-size: 15px; font-weight: 800; }
.panel-head p { margin: 3px 0 0; color: var(--text-3); font-size: 11.5px; }
.source-badge {
  display: inline-flex;
  align-items: center;
  margin-left: 5px;
  padding: 1px 6px;
  border: 1px solid rgba(217, 119, 6, 0.4);
  border-radius: 4px;
  color: var(--warning);
  background: var(--warning-soft);
  font-size: 11px;
  font-weight: 750;
}
.btn-close {
  width: 30px;
  height: 30px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  color: var(--text-3);
  background: transparent;
  border: 1px solid transparent;
  border-radius: 7px;
  font-size: 20px;
  cursor: pointer;
  line-height: 1;
  transition: all 0.15s ease;
}
.btn-close:hover { color: var(--text); background: var(--surface-4); border-color: var(--line-strong); }
.panel-body { flex: 1; min-height: 0; overflow-y: auto; padding: 14px 18px 18px; }

/* ---- 内嵌模式 ---- */
.model-manage-embedded {
  width: 100%;
  min-width: 0;
}

/* ---- 模型列表（两种模式共享） ---- */
.loading { text-align: center; padding: 34px 20px; color: var(--text-3); font-size: 12.5px; }
.model-list { list-style: none; display: flex; flex-direction: column; gap: 9px; }
.model-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  padding: 12px 13px;
  background: var(--surface-3);
  border: 1px solid var(--line);
  border-radius: 10px;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}
.model-item:hover {
  border-color: rgba(42, 125, 225, 0.4);
  box-shadow: 0 8px 20px rgba(24, 48, 76, 0.10), 0 0 10px rgba(42, 125, 225, 0.06);
  transform: translateY(-1px);
}
.model-info { min-width: 0; }
.model-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 750;
  color: var(--text);
}
.model-ver { margin-left: 5px; color: var(--primary); font-weight: 600; font-size: 11.5px; }
.model-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 7px 10px;
  align-items: center;
  margin-top: 6px;
  font-size: 11.5px;
  color: var(--text-3);
}
.model-tag { padding: 2px 7px; border-radius: 5px; font-weight: 750; border: 1px solid transparent; }
.model-tag.released { background: var(--success-soft); color: var(--success); border-color: rgba(22, 163, 74, 0.3); }
.model-tag.draft { background: var(--info-soft); color: var(--info); border-color: rgba(100, 116, 139, 0.3); }
.model-tag.validating { background: var(--warning-soft); color: var(--warning); border-color: rgba(217, 119, 6, 0.3); }
.model-tag.deprecated { background: var(--danger-soft); color: var(--danger); border-color: rgba(220, 38, 38, 0.3); }
.model-tag.rolled_back { background: var(--info-soft); color: var(--text-2); border-color: rgba(100, 116, 139, 0.3); }
.model-runtime, .model-date { white-space: nowrap; }
.btn-deploy {
  min-width: 58px;
  padding: 6px 11px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  background: linear-gradient(135deg, #6BA6EC, var(--primary-strong));
  color: #FFFFFF;
  border: 1px solid rgba(42, 125, 225, 0.6);
  border-radius: 7px;
  font-size: 11.5px;
  font-weight: 750;
  cursor: pointer;
  transition: all 0.18s ease;
}
.btn-deploy:hover:not(:disabled) { box-shadow: 0 4px 14px rgba(42, 125, 225, 0.32); }
.btn-deploy:disabled {
  background: var(--surface-4);
  color: var(--text-3);
  border-color: var(--line);
  cursor: not-allowed;
}
.deploy-mark {
  width: 7px;
  height: 7px;
  border: 1.5px solid currentColor;
  border-radius: 2px;
  position: relative;
}
.deploy-mark::after {
  content: '';
  position: absolute;
  width: 4px;
  height: 1px;
  left: 5px;
  top: 2px;
  background: currentColor;
  transform: rotate(-35deg);
  transform-origin: left center;
}

@media (max-width: 560px) {
  .model-manage-overlay { padding: 12px; }
  .model-manage-panel { max-height: 82vh; }
  .panel-head { padding: 14px; }
  .panel-body { padding: 12px 14px 14px; }
  .model-item { align-items: flex-start; }
  .btn-deploy { align-self: center; }
}
</style>
