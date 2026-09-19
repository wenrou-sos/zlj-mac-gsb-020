const BASE = import.meta.env.VITE_API_BASE || ''

async function request(path, options = {}) {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  const data = await resp.json().catch(() => ({}))
  if (!resp.ok) {
    throw new Error(data.detail || `请求失败 (${resp.status})`)
  }
  return data
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body: JSON.stringify(body) }),
}

export const SEVERITY_LABEL = {
  minor: { text: '轻微', color: '#38bdf8' },
  moderate: { text: '一般', color: '#facc15' },
  major: { text: '较大', color: '#fb923c' },
  critical: { text: '重大', color: '#f87171' },
}

export const EVENT_STATUS_LABEL = {
  reported: '已上报',
  analyzed: '影响分析完成',
  dispatched: '已派工',
  repairing: '抢修中',
  restored: '已复水',
  closed: '已归档',
}

export const ORDER_STATUS_LABEL = {
  assigned: '已指派',
  enroute: '赶赴现场',
  valves_closed: '已关阀停水',
  repairing: '修复中',
  blocked_material: '物料不足阻塞',
  blocked_road: '道路封闭阻塞',
  pressure_testing: '打压测试',
  valves_reopened: '开阀复水中',
  completed: '已完成',
  cancelled: '已取消',
}

export const TEAM_STATUS_LABEL = {
  available: '待命',
  enroute: '出动中',
  onsite: '现场',
  blocked_material: '缺料',
  blocked_road: '遇封路',
  repairing: '作业中',
  offduty: '休整',
}

export const fmtTime = (iso) => {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { hour12: false, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
