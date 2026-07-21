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
  getStats
}
