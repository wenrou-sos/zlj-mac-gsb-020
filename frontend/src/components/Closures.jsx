import React, { useState } from 'react'
import { fmtTime } from '../api'

export default function Closures({ closures, onCreate, onResolve, busy }) {
  const [form, setForm] = useState({
    reason: '道路施工',
    from_x: 42, from_y: 18, to_x: 58, to_y: 18,
  })
  const [result, setResult] = useState(null)
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const submit = async () => {
    const r = await onCreate(form)
    setResult(r)
  }

  return (
    <div className="panel">
      <h3>道路封闭与自动改道 <span className="sub">登记后系统自动重算在途工单路线、到场时间并通知用户</span></h3>
      <div className="row2">
        <label className="field">封闭原因
          <input value={form.reason} onChange={(e) => set('reason', e.target.value)} />
        </label>
        <label className="field">&nbsp;</label>
      </div>
      <div className="row2">
        <label className="field">起点 X
          <input type="number" value={form.from_x} onChange={(e) => set('from_x', +e.target.value)} />
        </label>
        <label className="field">起点 Y
          <input type="number" value={form.from_y} onChange={(e) => set('from_y', +e.target.value)} />
        </label>
      </div>
      <div className="row2">
        <label className="field">终点 X
          <input type="number" value={form.to_x} onChange={(e) => set('to_x', +e.target.value)} />
        </label>
        <label className="field">终点 Y
          <input type="number" value={form.to_y} onChange={(e) => set('to_y', +e.target.value)} />
        </label>
      </div>
      <button className="btn danger" disabled={busy} onClick={submit}>⛔ 登记封闭并触发重规划</button>

      {result && (
        <div className="note-box red" style={{ marginTop: 10 }}>
          <strong>自动重规划结果：</strong>
          {result.adjusted_orders.length === 0
            ? '当前没有在途工单的路线经过该封闭路段。'
            : (
              <ul style={{ margin: '6px 0', paddingLeft: 18 }}>
                {result.adjusted_orders.map((o) => (
                  <li key={o.work_order_id}>
                    工单 {o.work_order_code}（{o.event_code}）：改道绕行 +{o.extra_eta_minutes} 分钟，
                    通知受影响用户 {o.affected_users} 户
                  </li>
                ))}
              </ul>
            )}
          共发送延时通知 <strong>{result.notified_users_count}</strong> 条。
        </div>
      )}

      <table style={{ marginTop: 12 }}>
        <thead>
          <tr><th>编号</th><th>原因</th><th>路段</th><th>状态</th><th>登记时间</th><th>操作</th></tr>
        </thead>
        <tbody>
          {closures.map((c) => (
            <tr key={c.id}>
              <td>{c.code}</td>
              <td>{c.reason}</td>
              <td>({c.from_x},{c.from_y}) → ({c.to_x},{c.to_y})</td>
              <td>{c.status === 'active' ? <span className="badge red">封闭中</span> : <span className="badge green">已恢复</span>}</td>
              <td>{fmtTime(c.created_at)}</td>
              <td>
                {c.status === 'active' && (
                  <button className="btn small" disabled={busy} onClick={() => onResolve(c.id)}>道路恢复</button>
                )}
              </td>
            </tr>
          ))}
          {closures.length === 0 && (
            <tr><td colSpan={6} style={{ color: 'var(--muted)', textAlign: 'center' }}>暂无封路记录</td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
