// Thin API client. In dev, Vite proxies these paths to FastAPI.
async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail || detail
    } catch {
      /* ignore */
    }
    throw new Error(Array.isArray(detail) ? JSON.stringify(detail) : detail)
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  health: () => request('/health'),
  stats: () => request('/stats'),

  nodes: () => request('/network/nodes'),
  pipes: () => request('/network/pipes'),
  consumers: () => request('/network/consumers'),
  pipeImpact: (id) => request(`/network/impact/pipe/${id}`),

  incidents: () => request('/incidents'),
  incident: (id) => request(`/incidents/${id}`),
  createIncident: (body) => request('/incidents', { method: 'POST', body: JSON.stringify(body) }),
  dispatchIncident: (id) => request(`/incidents/${id}/dispatch`, { method: 'POST' }),
  incidentImpact: (id) => request(`/incidents/${id}/impact`),

  workOrders: () => request('/work-orders'),
  advanceWorkOrder: (id, note) =>
    request(`/work-orders/${id}/advance`, { method: 'POST', body: JSON.stringify({ note }) }),
  completeWorkOrder: (id) => request(`/work-orders/${id}/complete`, { method: 'POST' }),
  reportShortage: (id, materialCode, requiredQty) =>
    request(`/work-orders/${id}/shortage`, {
      method: 'POST',
      body: JSON.stringify({ material_code: materialCode, required_qty: Number(requiredQty) })
    }),

  teams: () => request('/teams'),
  materials: () => request('/materials'),
  restock: (code, qty) =>
    request(`/materials/${code}/restock`, { method: 'POST', body: JSON.stringify({ qty: Number(qty) }) }),

  closures: (activeOnly = false) => request(`/road-closures${activeOnly ? '?active_only=true' : ''}`),
  createClosure: (body) => request('/road-closures', { method: 'POST', body: JSON.stringify(body) }),
  resolveClosure: (id) => request(`/road-closures/${id}/resolve`, { method: 'POST' }),

  shortages: () => request('/shortages?open_only=true'),
  notifications: (incidentId) =>
    request(`/notifications${incidentId ? `?incident_id=${incidentId}` : ''}`)
}
