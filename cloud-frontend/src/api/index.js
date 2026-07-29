import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  timeout: 10000
})

// ===== 病区与床位 =====
export const getWards = () => http.get('/wards')
export const getWard = (id) => http.get(`/wards/${id}`)

// ===== 安全事件 =====
export const getEvents = (params = {}) => http.get('/events', { params })
export const getEvent = (eventId) => http.get(`/events/${eventId}`)
export const ackEvent = (eventId, { action, operator_id, operator_name, operator_role, result, note }) =>
  http.post(`/events/${eventId}/ack`, { action, operator_id, operator_name, operator_role, result, note })

// ===== 节点健康 =====
export const getNodes = (wardId) => http.get('/nodes', { params: { ward_id: wardId } })

// ===== 观测数据 =====
export const getObservations = (params = {}) => http.get('/observations', { params })

// ===== 模型管理 =====
export const getModels = () => http.get('/models')
export const deployModel = (nodeId, payload) =>
  http.post('/models/deploy', payload, { params: { node_id: nodeId } })

// ===== 系统统计 =====
export const getStats = () => http.get('/stats')

// ===== 交接班摘要 =====
export const getShiftSummaries = (params = {}) => http.get('/shift-summaries', { params })
export const generateShiftSummary = (payload) => http.post('/shift-summaries/generate', payload)
export const deleteShiftSummary = (summaryId) => http.delete(`/shift-summaries/${summaryId}`)

// ===== 床位占用可视化 =====
export const getBedOccupancy = (wardId) => http.get('/beds/occupancy', { params: { ward_id: wardId } })

// ===== 环境控制 =====
export const triggerEnvControl = (payload) => http.post('/env/control', payload)

// ===== 手动注入 & 统计 =====
export const getEventsByType = (params = {}) => http.get('/events/by-type', { params })
export const injectEvent = (payload) => http.post('/events', payload)

export default {
  getWards,
  getWard,
  getEvents,
  getEvent,
  ackEvent,
  getNodes,
  getObservations,
  getModels,
  deployModel,
  getStats,
  getShiftSummaries,
  generateShiftSummary,
  deleteShiftSummary,
  getBedOccupancy,
  triggerEnvControl,
  getEventsByType,
  injectEvent
}
