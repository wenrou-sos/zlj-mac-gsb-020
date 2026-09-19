import React from 'react'
import { SEVERITY_LABEL, EVENT_STATUS_LABEL, fmtTime } from '../api'

export default function EventList({ events, selectedId, onSelect }) {
  if (!events.length) {
    return <div className="panel" style={{ color: 'var(--muted)' }}>暂无漏损事件。点击“事件上报”或地图上的标记开始处理。</div>
  }
  return (
    <div className="panel">
      <h3>漏损事件 <span className="sub">（{events.length}）</span></h3>
      <div className="scroll" style={{ maxHeight: '36vh' }}>
        {events.map((ev) => {
          const sev = SEVERITY_LABEL[ev.severity] || SEVERITY_LABEL.minor
          const active = ['reported', 'analyzed', 'dispatched', 'repairing'].includes(ev.status)
          return (
            <div key={ev.id} className={`list-item ${selectedId === ev.id ? 'selected' : ''}`}
                 onClick={() => onSelect(ev)}>
              <div className="head">
                <span className="badge" style={{ background: sev.color }}>{sev.text}</span>
                <strong>{ev.code}</strong>
                <span className={`badge ${ev.status === 'restored' ? 'green' : active ? 'blue' : 'gray'}`}>
                  {EVENT_STATUS_LABEL[ev.status]}
                </span>
              </div>
              <div>{ev.title}</div>
              <div className="meta">
                <span>📍 {ev.address || `(${ev.location_x}, ${ev.location_y})`}</span>
                <span>报单人：{ev.reporter}</span>
                <span>{fmtTime(ev.created_at)}</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
