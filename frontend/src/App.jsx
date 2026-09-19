import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { api, EVENT_STATUS_LABEL, ORDER_STATUS_LABEL, TEAM_STATUS_LABEL, fmtTime } from './api'
import MapView from './components/MapView'
import EventList from './components/EventList'
import EventDetail from './components/EventDetail'
import ReportForm from './components/ReportForm'
import Materials from './components/Materials'
import Closures from './components/Closures'

const TABS = [
  { key: 'ops', label: '🛠 抢修监控' },
  { key: 'report', label: '📮 事件上报' },
  { key: 'materials', label: '📦 物料库存' },
  { key: 'closures', label: '⛔ 道路封闭' },
  { key: 'notify', label: '🔔 通知中心' },
]

export default function App() {
  const [tab, setTab] = useState('ops')
  const [map, setMap] = useState({ zones: [], users: [], valves: [], pipes: [], teams: [], events: [], closures: [] })
  const [materials, setMaterials] = useState([])
  const [stats, setStats] = useState(null)
  const [orders, setOrders] = useState([])
  const [selectedEventId, setSelectedEventId] = useState(null)
  const [impact, setImpact] = useState(null)
  const [orderDetail, setOrderDetail] = useState(null)
  const [eventNotes, setEventNotes] = useState([])
  const [allNotifications, setAllNotifications] = useState([])
  const [toast, setToast] = useState(null)
  const [busy, setBusy] = useState(false)
  const [clickPoint, setClickPoint] = useState(null)

  const showToast = (msg, type = '') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 5200)
  }

  const loadBase = useCallback(async () => {
    const [m, mats, dash] = await Promise.all([
      api.get('/api/map'),
      api.get('/api/materials'),
      api.get('/api/dashboard'),
    ])
    setMap(m)
    setMaterials(mats)
    setStats(dash)
  }, [])

  const loadOrders = useCallback(async () => {
    setOrders(await api.get('/api/work-orders'))
  }, [])

  const loadEventExtras = useCallback(async (eventId) => {
    if (!eventId) return
    const ev = (await api.get('/api/events')).find((e) => e.id === eventId)
    if (ev && ev.status !== 'reported') {
      try { setImpact(await api.post(`/api/events/${eventId}/analyze`, {})) } catch { /* keep stale */ }
    } else {
      setImpact(null)
    }
    const list = await api.get('/api/work-orders')
    const wo = list.find((o) => o.event_id === eventId)
    if (wo) {
      setOrderDetail(await api.get(`/api/work-orders/${wo.id}`))
    } else {
      setOrderDetail(null)
    }
    setEventNotes(await api.get(`/api/notifications?event_id=${eventId}`))
  }, [])

  useEffect(() => { loadBase(); loadOrders() }, [loadBase, loadOrders])
  useEffect(() => {
    api.get('/api/notifications?limit=100').then(setAllNotifications).catch(() => {})
  }, [tab])

  useEffect(() => {
    if (selectedEventId) loadEventExtras(selectedEventId)
    else { setImpact(null); setOrderDetail(null); setEventNotes([]) }
  }, [selectedEventId, loadEventExtras])

  const refreshAll = async () => {
    await loadBase()
    await loadOrders()
    if (selectedEventId) await loadEventExtras(selectedEventId)
    try { setAllNotifications(await api.get('/api/notifications?limit=100')) } catch { /* */ }
  }

  const selectedEvent = useMemo(
    () => map.events.find((e) => e.id === selectedEventId) || null,
    [map.events, selectedEventId],
  )

  const run = async (fn, okMsg) => {
    setBusy(true)
    try {
      const r = await fn()
      await refreshAll()
      if (okMsg) showToast(okMsg, 'ok')
      return r
    } catch (e) {
      showToast(e.message, 'error')
      throw e
    } finally {
      setBusy(false)
    }
  }

  const handleAnalyze = (id) => run(
    async () => { const r = await api.post(`/api/events/${id}/analyze`, {}); setImpact(r); return r },
    '影响区域分析完成',
  )

  const handleDispatch = (id) => run(async () => {
    const r = await api.post('/api/dispatch', { event_id: id })
    const parts = [`已指派 ${r.team_name}，预计 ${r.eta_minutes} 分钟到场`]
    if (r.route_detour) parts.push('路线遇封路已自动绕行')
    parts.push(r.material_ready ? '物料齐备' : `物料不足（${r.shortages.map((s) => s.name).join('、')}），已自动延时并通知 ${r.affected_users_count} 户`)
    showToast(parts.join('；'), r.material_ready ? 'ok' : 'error')
    return r
  }).catch(() => {})

  const handleProgress = (orderId, action, note = '') => run(async () => {
    const r = await api.post(`/api/work-orders/${orderId}/progress`, { action, note })
    if (action === 'complete') showToast('抢修完成，已恢复供水并通知全部受影响用户', 'ok')
    else if (action === 'report_material_shortage') showToast('工单已因物料不足暂停，预计复水时间已顺延，用户已收到延时通知', 'error')
    return r
  }).catch(() => {})

  const handleCreateEvent = async (form) => {
    const ev = await api.post('/api/events', form)
    setSelectedEventId(ev.id)
    await refreshAll()
    showToast(`事件 ${ev.code} 已上报，可进行影响区域分析`, 'ok')
    setTab('ops')
  }

  const handleRestock = (id, qty) => run(
    () => api.post(`/api/materials/${id}/restock`, { quantity: qty, reason: '紧急调拨' }),
    `已紧急调拨 ${qty} 件物料`,
  )

  const handleCreateClosure = (form) => {
    let result
    return run(async () => {
      result = await api.post('/api/closures', form)
      return result
    }).then(() => result).catch(() => null)
  }

  const handleResolveClosure = (id) => run(async () => {
    const r = await api.post(`/api/closures/${id}/resolve`, {})
    if (r.resumed_orders.length) showToast(`道路恢复，工单 ${r.resumed_orders.join('、')} 已自动继续出动`, 'ok')
    return r
  }).catch(() => {})

  return (
    <div className="app">
      <header className="app-header">
        <div className="logo"><span className="drop" />城市供水管网抢修管理平台</div>
        {stats && (
          <div className="stats">
            <div className="stat"><div className="num">{stats.active_events}</div><div className="lbl">在处理事件</div></div>
            <div className="stat warn"><div className="num">{stats.open_work_orders}</div><div className="lbl">进行中工单</div></div>
            <div className="stat danger"><div className="num">{stats.affected_users_now}</div><div className="lbl">当前停水用户</div></div>
            <div className="stat ok"><div className="num">{stats.available_teams}/{stats.total_teams}</div><div className="lbl">待命抢修队</div></div>
            <div className="stat warn"><div className="num">{stats.low_stock_materials.length}</div><div className="lbl">库存预警</div></div>
            <div className="stat danger"><div className="num">{stats.active_closures}</div><div className="lbl">道路封闭</div></div>
          </div>
        )}
      </header>

      <nav className="tabs">
        {TABS.map((t) => (
          <button key={t.key} className={tab === t.key ? 'active' : ''} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
        <button style={{ marginLeft: 'auto', color: 'var(--muted)' }} onClick={() => refreshAll()}>🔄 刷新数据</button>
      </nav>

      {tab === 'ops' && (
        <div className="main">
          <div>
            <MapView
              data={map}
              selectedEventId={selectedEventId}
              onSelectEvent={(ev) => setSelectedEventId(ev.id)}
            />
            {orders.length > 0 && (
              <div className="panel" style={{ marginTop: 14 }}>
                <h3>抢修工单总览</h3>
                <table>
                  <thead>
                    <tr><th>工单</th><th>事件</th><th>抢修队</th><th>状态</th><th>进度</th><th>预计到场</th><th>备注</th></tr>
                  </thead>
                  <tbody>
                    {orders.map((o) => {
                      const ev = map.events.find((e) => e.id === o.event_id)
                      const team = map.teams.find((t) => t.id === o.team_id)
                      const blocked = ['blocked_material', 'blocked_road'].includes(o.status)
                      return (
                        <tr key={o.id} style={{ cursor: 'pointer' }}
                            onClick={() => { setSelectedEventId(o.event_id); }}>
                          <td>{o.code}</td>
                          <td>{ev?.code || o.event_id}</td>
                          <td>{team?.name}</td>
                          <td>
                            <span className={`badge ${o.status === 'completed' ? 'green' : blocked ? 'red' : 'purple'}`}>
                              {ORDER_STATUS_LABEL[o.status]}
                            </span>
                          </td>
                          <td style={{ width: 130 }}>
                            <div className="progress-track" style={{ margin: 0 }}>
                              <div className={`progress-fill ${blocked ? 'blocked' : ''}`} style={{ width: `${o.progress_pct}%` }} />
                            </div>
                            <small style={{ color: 'var(--muted)' }}>{o.progress_pct}%</small>
                          </td>
                          <td>{o.planned_eta_minutes} 分钟</td>
                          <td style={{ color: 'var(--warn)', maxWidth: 220 }}>
                            {o.route_detour && '绕行 '}
                            {!o.material_ready && `缺料：${o.shortage_note}`}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
          <div>
            <EventList events={map.events} selectedId={selectedEventId} onSelect={(ev) => setSelectedEventId(ev.id)} />
            <EventDetail
              event={selectedEvent}
              impact={impact}
              workOrder={orderDetail}
              notifications={eventNotes}
              busy={busy}
              onAnalyze={handleAnalyze}
              onDispatch={handleDispatch}
              onProgress={handleProgress}
            />
          </div>
        </div>
      )}

      {tab === 'report' && (
        <div className="main">
          <MapView
            data={map}
            selectedEventId={selectedEventId}
            onSelectEvent={(ev) => setSelectedEventId(ev.id)}
            drawMode
            onMapClick={(p) => { setClickPoint(p); showToast(`已选取漏点坐标 (${p.x}, ${p.y})`, 'ok') }}
          />
          <ReportForm preset={clickPoint} onSubmit={handleCreateEvent} />
        </div>
      )}

      {tab === 'materials' && (
        <div className="main full">
          <Materials materials={materials} onRestock={handleRestock} busy={busy} />
          <div className="panel">
            <h3>抢修队伍状态 <span className="sub">派工时系统按距离、实时路况、队伍状态自动择优</span></h3>
            <table>
              <thead>
                <tr><th>队伍</th><th>负责人</th><th>电话</th><th>技能</th><th>驻地坐标</th><th>当前状态</th></tr>
              </thead>
              <tbody>
                {map.teams.map((t) => (
                  <tr key={t.id}>
                    <td>{t.name}</td><td>{t.leader}</td><td>{t.phone}</td>
                    <td>{t.skills || '—'}</td><td>({t.home_x}, {t.home_y})</td>
                    <td><span className={`badge ${t.status === 'available' ? 'green' : 'purple'}`}>
                      {TEAM_STATUS_LABEL[t.status] || t.status}
                    </span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'closures' && (
        <div className="main full">
          <Closures
            closures={map.closures}
            busy={busy}
            onCreate={handleCreateClosure}
            onResolve={handleResolveClosure}
          />
        </div>
      )}

      {tab === 'notify' && (
        <div className="main full">
          <div className="panel">
            <h3>用户通知中心 <span className="sub">停水 / 物料延时 / 道路绕行 / 恢复供水 自动短信推送记录</span></h3>
            <table>
              <thead>
                <tr><th>时间</th><th>事件</th><th>类型</th><th>标题</th><th>内容</th></tr>
              </thead>
              <tbody>
                {allNotifications.map((n) => (
                  <tr key={n.id}>
                    <td style={{ whiteSpace: 'nowrap' }}>{fmtTime(n.created_at)}</td>
                    <td>{map.events.find((e) => e.id === n.event_id)?.code || n.event_id}</td>
                    <td>
                      <span className={`badge ${n.kind === 'restored' ? 'green' : n.kind === 'shutdown' ? 'blue' : 'amber'}`}>
                        {{ shutdown: '停水', delay_material: '物料延时', detour: '绕行延时', restored: '复水' }[n.kind] || n.kind}
                      </span>
                    </td>
                    <td style={{ whiteSpace: 'nowrap' }}>{n.title}</td>
                    <td style={{ color: 'var(--muted)', maxWidth: 560 }}>{n.content}</td>
                  </tr>
                ))}
                {allNotifications.length === 0 && (
                  <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--muted)' }}>暂无通知，派工与重规划后将自动生成</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {toast && <div className={`toast ${toast.type}`}>{toast.msg}</div>}
    </div>
  )
}
