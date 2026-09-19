import React, { useState } from 'react'

const STATUS_LABEL = {
  reported: '待派工',
  dispatched: '已派工',
  repairing: '抢修中',
  repaired: '已修复',
  closed: '已归档'
}

const SEV_LABEL = { low: '一般', medium: '较大', high: '重大' }

export default function IncidentPanel({
  pipes, incidents, selectedPipeId, onSelectPipe,
  onCreate, onDispatch, onShowImpact, busy
}) {
  const [title, setTitle] = useState('')
  const [severity, setSeverity] = useState('medium')
  const [desc, setDesc] = useState('')
  const [err, setErr] = useState('')

  const selectedPipe = pipes.find((p) => p.id === selectedPipeId)

  async function submit(e) {
    e.preventDefault()
    setErr('')
    if (!selectedPipe) {
      setErr('请先在地图上点击发生漏损的管段')
      return
    }
    try {
      await onCreate({
        title: title || `${selectedPipe.code} 管段漏损`,
        pipe_id: selectedPipe.id,
        severity,
        description: desc,
        reporter: '调度台'
      })
      setTitle('')
      setDesc('')
    } catch (e) {
      setErr(e.message)
    }
  }

  return (
    <div className="panel-grid">
      <section className="card">
        <h3>📢 漏损事件上报</h3>
        <form onSubmit={submit} className="form">
          <label>
            事件标题
            <input value={title} onChange={(e) => setTitle(e.target.value)}
                   placeholder="如：东风路DN300爆管" />
          </label>
          <label>
            严重程度
            <select value={severity} onChange={(e) => setSeverity(e.target.value)}>
              <option value="low">一般（小管渗漏）</option>
              <option value="medium">较大（干管爆漏）</option>
              <option value="high">重大（主干管断裂）</option>
            </select>
          </label>
          <label>
            情况描述
            <textarea rows={2} value={desc} onChange={(e) => setDesc(e.target.value)} />
          </label>
          <div className="hint">
            目标管段：<b>{selectedPipe ? selectedPipe.code : '未选择（点击地图管段）'}</b>
          </div>
          {err && <div className="error">{err}</div>}
          <button className="btn primary" disabled={busy}>上报并分析影响区域</button>
        </form>
      </section>

      <section className="card">
        <h3>🗂 事件列表</h3>
        <div className="list">
          {incidents.length === 0 && <div className="empty">暂无漏损事件</div>}
          {incidents.map((inc) => (
            <div key={inc.id} className={`list-item sev-${inc.severity}`}>
              <div className="li-head">
                <b>#{inc.id} {inc.title}</b>
                <span className={`badge st-${inc.status}`}>{STATUS_LABEL[inc.status]}</span>
              </div>
              <div className="li-meta">
                <span className={`tag sev-${inc.severity}`}>{SEV_LABEL[inc.severity]}</span>
                <span>👥 影响 {inc.affected_residents} 人</span>
                <span>🔧 阀 {inc.isolation_valve_ids?.length || 0} 个</span>
                <span>⏱ {inc.estimated_outage_minutes} 分钟</span>
              </div>
              {inc.description?.includes('[分析告警]') && (
                <div className="warning">
                  ⚠ {inc.description.split('[分析告警]')[1]}
                </div>
              )}
              <div className="li-actions">
                <button className="btn sm" onClick={() => onShowImpact(inc)}>影响区域</button>
                <button className="btn sm" onClick={() => onSelectPipe(inc.pipe_id)}
                        disabled={!inc.pipe_id}>定位管段</button>
                {inc.status === 'reported' && (
                  <button className="btn sm primary" disabled={busy}
                          onClick={() => onDispatch(inc.id)}>智能派工</button>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
