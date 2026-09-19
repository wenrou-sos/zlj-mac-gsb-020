import React, { useState } from 'react'

export function RoadClosurePanel({ nodes, pipes, closures, busy, onCreate, onResolve }) {
  const [startCode, setStartCode] = useState('J1')
  const [endCode, setEndCode] = useState('V1')
  const [reason, setReason] = useState('道路施工封闭')
  const [err, setErr] = useState('')

  const codeToId = Object.fromEntries(nodes.map((n) => [n.code, n.id]))
  const idToCode = Object.fromEntries(nodes.map((n) => [n.id, n.code]))

  async function submit(e) {
    e.preventDefault()
    setErr('')
    try {
      await onCreate({
        start_node_id: codeToId[startCode],
        end_node_id: codeToId[endCode],
        reason
      })
    } catch (e) {
      setErr(e.message)
    }
  }

  const pipeOptions = new Set()
  pipes.forEach((p) => {
    const a = idToCode[p.start_node_id]
    const b = idToCode[p.end_node_id]
    if (a && b) pipeOptions.add(`${a}|${b}`)
  })

  return (
    <div className="panel-grid">
      <section className="card">
        <h3>🚧 道路封闭登记（自动调整抢修计划）</h3>
        <form onSubmit={submit} className="form">
          <label>封闭路段（沿管网管段）
            <select value={`${startCode}|${endCode}`}
                    onChange={(e) => {
                      const [a, b] = e.target.value.split('|')
                      setStartCode(a)
                      setEndCode(b)
                    }}>
              {[...pipeOptions].map((pair) => {
                const [a, b] = pair.split('|')
                return <option key={pair} value={pair}>{a} ↔ {b}</option>
              })}
            </select>
          </label>
          <label>
            封闭原因
            <input value={reason} onChange={(e) => setReason(e.target.value)} />
          </label>
          {err && <div className="error">{err}</div>}
          <button className="btn warn" disabled={busy}>登记封闭并重算派工</button>
          <p className="hint">登记后系统自动：① 为在途工单改道并更新ETA；② 绕行过久/无路可达时改派最近队伍；③ 向受影响用户范围推送变更通知。</p>
        </form>
      </section>

      <section className="card">
        <h3>🚦 封闭记录</h3>
        <div className="list">
          {closures.length === 0 && <div className="empty">当前没有道路封闭</div>}
          {closures.map((c) => (
            <div key={c.id} className="list-item">
              <div className="li-head">
                <b>{idToCode[c.start_node_id]} ↔ {idToCode[c.end_node_id]}</b>
                <span className={`badge ${c.active ? 'st-repairing' : 'st-completed'}`}>
                  {c.active ? '封闭中' : '已解封'}
                </span>
              </div>
              <div className="li-meta">
                <span>{c.reason}</span>
                <span>{new Date(c.created_at + 'Z').toLocaleString('zh-CN')}</span>
              </div>
              {c.active && (
                <div className="li-actions">
                  <button className="btn sm" disabled={busy} onClick={() => onResolve(c.id)}>
                    解封并恢复调度
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

export function MaterialPanel({ materials, shortages, busy, onRestock }) {
  const [qty, setQty] = useState({})

  return (
    <div className="panel-grid">
      <section className="card">
        <h3>🏗 物料库存（到货后自动恢复延期工单）</h3>
        <table className="tbl">
          <thead>
            <tr><th>编码</th><th>名称</th><th>单位</th><th>库存</th><th>安全库存</th><th>到货入库</th></tr>
          </thead>
          <tbody>
            {materials.map((m) => (
              <tr key={m.id} className={m.stock < m.safety_stock ? 'low-stock' : ''}>
                <td>{m.code}</td>
                <td>{m.name}</td>
                <td>{m.unit}</td>
                <td>{m.stock}</td>
                <td>{m.safety_stock}</td>
                <td>
                  <input type="number" min={1} defaultValue={m.safety_stock}
                         style={{ width: 70 }}
                         onChange={(e) => setQty({ ...qty, [m.code]: e.target.value })} />
                  <button className="btn sm" disabled={busy}
                          onClick={() => onRestock(m.code, qty[m.code] || m.safety_stock)}>
                    入库
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h3>📦 待处理缺料单</h3>
        <div className="list">
          {shortages.length === 0 && <div className="empty">暂无缺料，抢修物料充足</div>}
          {shortages.map((s) => (
            <div key={s.id} className="list-item warn-bg">
              <div className="li-head">
                <b>{s.material_code}</b>
                <span className="badge st-delayed_material">调拨中</span>
              </div>
              <div className="li-meta">
                <span>需要 {s.required_qty}</span>
                <span>当前库存 {s.available_qty}</span>
                <span>工单 #{s.work_order_id}</span>
              </div>
              <div className="hint">对应工单已延期并通知受影响用户；在左侧「入库」后工单自动恢复。</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
