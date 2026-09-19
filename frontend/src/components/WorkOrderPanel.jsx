import React, { useState } from 'react'

const WO_STATUS = {
  planned: '待派工',
  en_route: '赶赴现场',
  on_site: '已到场(关阀停水)',
  repairing: '抢修中',
  delayed_material: '物料不足-延期',
  completed: '已完成复水',
  reassigned: '已改派'
}

const STEPS = [
  { key: 'en_route', label: '出发' },
  { key: 'on_site', label: '关阀停水' },
  { key: 'repairing', label: '现场抢修' },
  { key: 'completed', label: '开阀复水' }
]

export default function WorkOrderPanel({ workOrders, incidents, materials, busy, onAdvance, onComplete, onShortage }) {
  const [expanded, setExpanded] = useState(null)
  const [matCode, setMatCode] = useState('pipe_dn300')
  const [matQty, setMatQty] = useState(1)

  const incById = Object.fromEntries(incidents.map((i) => [i.id, i]))

  function stepIndex(wo) {
    if (wo.status === 'completed') return 4
    if (wo.status === 'repairing') return 3
    if (wo.status === 'on_site') return 2
    if (wo.status === 'en_route') return 1
    return 0
  }

  return (
    <section className="card">
      <h3>🛠 抢修工单与停复水进度</h3>
      <div className="list">
        {workOrders.length === 0 && <div className="empty">暂无工单，请先在「事件上报」中派工</div>}
        {workOrders.map((wo) => {
          const inc = incById[wo.incident_id]
          const idx = stepIndex(wo)
          const open = expanded === wo.id
          return (
            <div key={wo.id} className={`list-item wo st-${wo.status}`}>
              <div className="li-head">
                <b>工单 #{wo.id} · {inc?.title || `事件${wo.incident_id}`}</b>
                <span className={`badge st-${wo.status}`}>{WO_STATUS[wo.status]}</span>
              </div>

              {/* progress bar */}
              <div className="steps">
                {STEPS.map((s, i) => (
                  <React.Fragment key={s.key}>
                    <div className={`step ${i <= idx ? 'done' : ''} ${i === idx && wo.status !== 'completed' ? 'cur' : ''}`}>
                      <span className="dot">{i + 1}</span>
                      <span className="step-label">{s.label}</span>
                    </div>
                    {i < STEPS.length - 1 && <div className={`bar ${i < idx ? 'done' : ''}`} />}
                  </React.Fragment>
                ))}
              </div>

              <div className="li-meta">
                <span>🚛 {wo.team?.name || '未分配队伍'}</span>
                <span>📏 {Math.round(wo.route_distance_m)}m</span>
                <span>⏱ ETA {wo.eta_minutes} 分</span>
                <span>🔨 修复约 {wo.repair_minutes} 分</span>
                <span>{wo.water_off ? '🚱 已停水' : '💧 供水正常'}</span>
              </div>

              {wo.diverted && <div className="warning">🔁 {wo.replan_reason}</div>}
              {wo.status === 'delayed_material' && (
                <div className="warning">📦 {wo.replan_reason}</div>
              )}

              <div className="li-actions">
                {['en_route', 'on_site'].includes(wo.status) && (
                  <button className="btn sm primary" disabled={busy}
                          onClick={() => onAdvance(wo.id)}>
                    {wo.status === 'en_route' ? '到场并关阀停水' : '开始抢修'}
                  </button>
                )}
                {wo.status === 'repairing' && (
                  <button className="btn sm primary" disabled={busy}
                          onClick={() => onComplete(wo.id)}>维修完成 · 开阀复水</button>
                )}
                {['en_route', 'on_site', 'repairing'].includes(wo.status) && (
                  <button className="btn sm" disabled={busy}
                          onClick={() => onShortage(wo.id, matCode, matQty)}>
                    上报物料不足
                  </button>
                )}
                <select value={matCode} onChange={(e) => setMatCode(e.target.value)}>
                  {materials.map((m) => (
                    <option key={m.id} value={m.code}>{m.name}(库存{m.stock})</option>
                  ))}
                </select>
                <input type="number" min={1} value={matQty} style={{ width: 64 }}
                       onChange={(e) => setMatQty(e.target.value)} />
                <button className="btn sm ghost" onClick={() => setExpanded(open ? null : wo.id)}>
                  {open ? '收起日志' : '进度日志'}
                </button>
              </div>

              {open && (
                <ul className="events">
                  {wo.events?.map((ev) => (
                    <li key={ev.id}>
                      <span className={`ev-tag ev-${ev.type}`}>{ev.type}</span>
                      {ev.message}
                      <span className="ev-time">{new Date(ev.created_at + 'Z').toLocaleString('zh-CN')}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
