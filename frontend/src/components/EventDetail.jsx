import React from 'react'
import {
  SEVERITY_LABEL, EVENT_STATUS_LABEL, ORDER_STATUS_LABEL, fmtTime,
} from '../api'

export default function EventDetail({ event, impact, workOrder, notifications, onAnalyze, onDispatch, onProgress, busy }) {
  if (!event) {
    return (
      <div className="panel" style={{ color: 'var(--muted)' }}>
        选择左侧事件或在“事件上报”页创建漏损事件。
      </div>
    )
  }
  const sev = SEVERITY_LABEL[event.severity] || SEVERITY_LABEL.minor
  const canAnalyze = ['reported', 'analyzed'].includes(event.status)
  const canDispatch = ['analyzed', 'reported'].includes(event.status)

  const orderActions = [
    { action: 'depart', label: '① 队伍出发', when: ['assigned', 'blocked_road'] },
    { action: 'arrive', label: '② 到达现场', when: ['enroute'] },
    { action: 'close_valves', label: '③ 关阀停水', when: ['enroute', 'valves_closed'] },
    { action: 'start_repair', label: '④ 开始修复', when: ['valves_closed', 'repairing', 'blocked_material'] },
    { action: 'pressure_test', label: '⑤ 打压测试', when: ['repairing'] },
    { action: 'reopen_valves', label: '⑥ 开阀复水', when: ['pressure_test', 'valves_reopened'] },
    { action: 'complete', label: '⑦ 抢修完成', when: ['valves_reopened'] },
  ]

  const blocked = workOrder && ['blocked_material', 'blocked_road'].includes(workOrder.status)

  return (
    <div className="panel">
      <h3>
        <span className="badge" style={{ background: sev.color }}>{sev.text}</span>
        {event.code} · {event.title}
        <span className={`badge ${event.status === 'restored' ? 'green' : 'amber'}`}>
          {EVENT_STATUS_LABEL[event.status]}
        </span>
      </h3>
      <div className="kv">
        <span className="k">报单人</span><span>{event.reporter} {event.reporter_phone}</span>
        <span className="k">位置</span><span>{event.address || '—'}（坐标 {event.location_x}, {event.location_y}）</span>
        <span className="k">管径</span><span>DN{event.pipe_diameter_mm}</span>
        <span className="k">上报时间</span><span>{fmtTime(event.created_at)}</span>
        <span className="k">预计复水</span><span style={{ color: 'var(--warn)' }}>{fmtTime(event.estimated_restore_at)}</span>
      </div>
      {event.description && <div className="note-box blue">{event.description}</div>}

      <div className="actions">
        {canAnalyze && <button className="btn" disabled={busy} onClick={() => onAnalyze(event.id)}>🔍 影响区域分析</button>}
        {canDispatch && <button className="btn ghost" disabled={busy} onClick={() => onDispatch(event.id)}>🚚 智能派工</button>}
      </div>

      {impact && impact.event_id === event.id && (
        <div style={{ marginTop: 10 }}>
          <div className="note-box blue">
            影响分析：受影响区域 <strong>{impact.affected_zones.map((z) => z.name).join('、') || '—'}</strong>，
            停水用户 <strong style={{ color: 'var(--warn)' }}>{impact.affected_users_count}</strong> 户，
            其中重点保障单位 <strong style={{ color: 'var(--danger)' }}>{impact.priority_users_count}</strong> 家，
            需关闭边界阀门 <strong>{impact.valves_to_close.length}</strong> 个，
            预计作业 {impact.estimated_repair_minutes} 分钟。
          </div>
          <details>
            <summary style={{ color: 'var(--muted)', cursor: 'pointer', fontSize: 12 }}>
              受影响用户名单（{impact.affected_users_count}）/ 待关阀门（{impact.valves_to_close.length}）
            </summary>
            <div style={{ maxHeight: 180, overflow: 'auto', marginTop: 6 }}>
              {impact.affected_users.map((u) => (
                <div key={u.id} style={{ fontSize: 12, padding: '2px 0' }}>
                  {u.priority && <span className="badge red" style={{ marginRight: 6 }}>重点</span>}
                  {u.name} · {u.address} · {u.phone}
                </div>
              ))}
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 6 }}>
                待关阀门：{impact.valves_to_close.map((v) => v.code).join('、')}
              </div>
            </div>
          </details>
        </div>
      )}

      {workOrder && (
        <div style={{ marginTop: 12, borderTop: '1px solid var(--border)', paddingTop: 10 }}>
          <h3>
            抢修工单 {workOrder.code}
            <span className={`badge ${blocked ? 'red' : workOrder.status === 'completed' ? 'green' : 'purple'}`}>
              {ORDER_STATUS_LABEL[workOrder.status]}
            </span>
          </h3>
          <div className="kv">
            <span className="k">抢修队</span><span>{workOrder.team?.name}（{workOrder.team?.leader} {workOrder.team?.phone}）</span>
            <span className="k">预计到场</span><span>{workOrder.planned_eta_minutes} 分钟{workOrder.route_detour && '（含绕行）'}</span>
          </div>
          <div className="progress-track">
            <div className={`progress-fill ${blocked ? 'blocked' : ''}`} style={{ width: `${workOrder.progress_pct}%` }} />
          </div>
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>进度 {workOrder.progress_pct}%</div>

          {workOrder.route_detour && workOrder.status !== 'blocked_road' && (
            <div className="note-box">路线受道路封闭影响，已自动绕行，到场时间增加 30 分钟。</div>
          )}
          {workOrder.status === 'blocked_road' && (
            <div className="note-box red">⛔ 道路封闭阻断抢修路线，计划已自动调整（绕行 +30 分钟），受影响用户已收到延时通知。道路恢复后工单自动继续。</div>
          )}
          {!workOrder.material_ready && (
            <div className="note-box red">📦 物料不足：{workOrder.shortage_note || '存在缺料'}。已延长预计复水时间并通知用户，可在“物料库存”页紧急调拨后补料到货。</div>
          )}

          {workOrder.status !== 'completed' && (
            <div className="actions">
              {orderActions
                .filter((a) => a.when.includes(workOrder.status))
                .map((a) => (
                  <button key={a.action} className="btn small" disabled={busy}
                          onClick={() => onProgress(workOrder.id, a.action)}>
                    {a.label}
                  </button>
                ))}
              {['valves_closed', 'repairing'].includes(workOrder.status) && workOrder.material_ready && (
                <button className="btn small danger" disabled={busy}
                        onClick={() => onProgress(workOrder.id, 'report_material_shortage', '现场反馈关键物料不足')}>
                  📦 报告物料不足
                </button>
              )}
              {workOrder.status === 'blocked_material' && (
                <button className="btn small" disabled={busy}
                        onClick={() => onProgress(workOrder.id, 'materials_received')}>
                  ✅ 补料已到货，继续抢修
                </button>
              )}
            </div>
          )}
          {workOrder.completed_at && (
            <div className="note-box" style={{ borderColor: 'var(--ok)' }}>
              已于 {fmtTime(workOrder.completed_at)} 完成抢修并恢复供水。
            </div>
          )}

          {workOrder.logs?.length > 0 && (
            <details style={{ marginTop: 8 }}>
              <summary style={{ color: 'var(--muted)', cursor: 'pointer', fontSize: 12 }}>进度日志（{workOrder.logs.length}）</summary>
              <div className="timeline" style={{ marginTop: 8 }}>
                {workOrder.logs.map((log) => (
                  <div key={log.id} className="t-entry">
                    <div>{log.note} <span className="badge gray" style={{ marginLeft: 6 }}>{log.progress_pct}%</span></div>
                    <div className="t-time">{fmtTime(log.created_at)} · {log.action}</div>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}

      {notifications?.length > 0 && (
        <details style={{ marginTop: 10 }} open={false}>
          <summary style={{ color: 'var(--muted)', cursor: 'pointer', fontSize: 12 }}>
            用户通知记录（{notifications.length} 条短信/推送）
          </summary>
          <div className="scroll" style={{ maxHeight: 200, marginTop: 6 }}>
            {notifications.map((n) => (
              <div key={n.id} style={{ fontSize: 12, borderBottom: '1px solid var(--border)', padding: '5px 0' }}>
                <span className={`badge ${n.kind === 'restored' ? 'green' : n.kind === 'shutdown' ? 'blue' : 'amber'}`}>
                  {n.title}
                </span>
                <div style={{ color: 'var(--muted)', marginTop: 2 }}>{n.content}</div>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  )
}
