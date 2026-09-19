import React from 'react'

export default function NotificationPanel({ notifications, consumers }) {
  const nameById = Object.fromEntries(consumers.map((c) => [c.id, c.name]))

  return (
    <section className="card">
      <h3>📲 受影响用户通知记录（短信 / App / 公告）</h3>
      <div className="list">
        {notifications.length === 0 && <div className="empty">暂无通知，派工与计划调整时会自动生成</div>}
        {notifications.map((n) => (
          <div key={n.id} className="list-item notif">
            <div className="li-head">
              <b>{n.title}</b>
              <span className="badge st-dispatched">{n.channel.toUpperCase()} · {n.scope}</span>
            </div>
            <p className="notif-msg">{n.message}</p>
            <div className="li-meta">
              <span>👥 推送居民 {n.affected_residents} 人</span>
              <span>
                用户：
                {(n.affected_consumer_ids || []).map((id) => nameById[id] || `#${id}`).join('、') || '—'}
              </span>
              <span>{new Date(n.created_at + 'Z').toLocaleString('zh-CN')}</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
