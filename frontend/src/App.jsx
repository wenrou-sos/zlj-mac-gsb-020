import React, { useCallback, useEffect, useState } from 'react'
import { api } from './api/client'
import MapView from './components/MapView'
import IncidentPanel from './components/IncidentPanel'
import WorkOrderPanel from './components/WorkOrderPanel'
import NotificationPanel from './components/NotificationPanel'
import { RoadClosurePanel, MaterialPanel } from './components/DisruptionPanel'

const TABS = [
  { key: 'incidents', label: '事件上报 / 派工' },
  { key: 'orders', label: '停复水进度' },
  { key: 'disruptions', label: '道路封闭 / 物料' },
  { key: 'notify', label: '用户通知' }
]

export default function App() {
  const [tab, setTab] = useState('incidents')
  const [data, setData] = useState({
    nodes: [], pipes: [], consumers: [], teams: [],
    incidents: [], orders: [], closures: [], materials: [],
    shortages: [], notifications: [], stats: null
  })
  const [selectedPipeId, setSelectedPipeId] = useState(null)
  const [highlight, setHighlight] = useState({})
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState('')
  const [healthy, setHealthy] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const [nodes, pipes, consumers, teams, incidents, orders,
             closures, materials, shortages, notifications, stats] = await Promise.all([
        api.nodes(), api.pipes(), api.consumers(), api.teams(),
        api.incidents(), api.workOrders(), api.closures(false),
        api.materials(), api.shortages(), api.notifications(), api.stats()
      ])
      setData({ nodes, pipes, consumers, teams, incidents, orders,
                closures, materials, shortages, notifications, stats })
      setHealthy(true)
    } catch (e) {
      setHealthy(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])
  useEffect(() => {
    const t = setInterval(refresh, 8000)
    return () => clearInterval(t)
  }, [refresh])

  function flash(msg, ok = true) {
    setToast(msg)
    setTimeout(() => setToast(''), 3500)
    if (!ok) console.error(msg)
  }

  async function run(label, fn) {
    setBusy(true)
    try {
      await fn()
      await refresh()
      flash(`✓ ${label}`)
    } catch (e) {
      flash(`✗ ${label}：${e.message}`, false)
    } finally {
      setBusy(false)
    }
  }

  async function showPipeImpact(pipe) {
    setSelectedPipeId(pipe.id)
    try {
      const impact = await api.pipeImpact(pipe.id)
      setHighlight({
        consumerIds: impact.affected_consumer_ids,
        valveIds: impact.isolation_valve_ids
      })
      flash(`管段 ${pipe.code}：影响 ${impact.affected_residents} 人，隔离阀 ${impact.isolation_valve_ids.length} 个`)
    } catch (e) {
      flash(e.message, false)
    }
  }

  async function showIncidentImpact(inc) {
    setTab('incidents')
    setSelectedPipeId(inc.pipe_id)
    setHighlight({
      consumerIds: inc.affected_consumer_ids || [],
      valveIds: inc.isolation_valve_ids || []
    })
  }

  const s = data.stats

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">💧 城市供水管网抢修管理平台</div>
        <nav className="tabs">
          {TABS.map((t) => (
            <button key={t.key} className={`tab ${tab === t.key ? 'active' : ''}`}
                    onClick={() => setTab(t.key)}>{t.label}</button>
          ))}
        </nav>
        <span className={`health ${healthy ? 'ok' : 'bad'}`}>
          {healthy ? '● 服务正常' : '● 后端离线'}
        </span>
      </header>

      {s && (
        <div className="statbar">
          <div className="stat"><b>{s.open_incidents}</b><span>未闭环事件</span></div>
          <div className="stat"><b>{s.active_work_orders}</b><span>进行中工单</span></div>
          <div className="stat warn"><b>{s.affected_residents}</b><span>受影响居民</span></div>
          <div className="stat"><b>{s.teams_busy}</b><span>出勤队伍</span></div>
          <div className={`stat ${s.water_off_orders ? 'warn' : ''}`}>
            <b>{s.water_off_orders}</b><span>停水中</span></div>
          <div className={`stat ${s.open_road_closures ? 'warn' : ''}`}>
            <b>{s.open_road_closures}</b><span>道路封闭</span></div>
          <div className={`stat ${s.pending_shortages ? 'warn' : ''}`}>
            <b>{s.pending_shortages}</b><span>缺料待拨</span></div>
        </div>
      )}

      <main className="content">
        <div className="map-wrap card">
          <div className="map-title">
            🗺 管网态势图
            <span className="map-legend">
              <i className="lg lg-source" />水厂
              <i className="lg lg-valve" />阀门
              <i className="lg lg-junction" />节点
              <i className="lg lg-team" />抢修队
              <i className="lg lg-zone" />受影响区
            </span>
          </div>
          <MapView
            nodes={data.nodes}
            pipes={data.pipes}
            consumers={data.consumers}
            teams={data.teams}
            closures={data.closures}
            incidents={data.incidents}
            highlight={highlight}
            selectedPipeId={selectedPipeId}
            onPipeClick={showPipeImpact}
          />
          <div className="hint map-hint">点击任意管段可查看其关阀停水影响范围；红色阀门=已关闭。</div>
        </div>

        {tab === 'incidents' && (
          <IncidentPanel
            pipes={data.pipes}
            incidents={data.incidents}
            selectedPipeId={selectedPipeId}
            onSelectPipe={(pid) => {
              setSelectedPipeId(pid)
              const p = data.pipes.find((x) => x.id === pid)
              if (p) showPipeImpact(p)
            }}
            busy={busy}
            onCreate={async (body) => {
              const inc = await api.createIncident(body)
              setHighlight({
                consumerIds: inc.affected_consumer_ids || [],
                valveIds: inc.isolation_valve_ids || []
              })
              await refresh()
              flash(`✓ 事件已上报，自动分析影响 ${inc.affected_residents} 人`)
            }}
            onDispatch={(id) => run('派工成功', () => api.dispatchIncident(id))}
            onShowImpact={showIncidentImpact}
          />
        )}

        {tab === 'orders' && (
          <WorkOrderPanel
            workOrders={data.orders}
            incidents={data.incidents}
            materials={data.materials}
            busy={busy}
            onAdvance={(id) => run('进度已更新', () => api.advanceWorkOrder(id))}
            onComplete={(id) => run('已复水', () => api.completeWorkOrder(id))}
            onShortage={(id, code, qty) =>
              run('缺料已上报，计划已调整', () => api.reportShortage(id, code, qty))}
          />
        )}

        {tab === 'disruptions' && (
          <>
            <RoadClosurePanel
              nodes={data.nodes}
              pipes={data.pipes}
              closures={data.closures}
              busy={busy}
              onCreate={(body) => run('道路封闭已登记，在途工单已重算', () => api.createClosure(body))}
              onResolve={(id) => run('已解封并恢复调度', () => api.resolveClosure(id))}
            />
            <MaterialPanel
              materials={data.materials}
              shortages={data.shortages}
              busy={busy}
              onRestock={(code, qty) => run('物料入库，延期工单已恢复', () => api.restock(code, qty))}
            />
          </>
        )}

        {tab === 'notify' && (
          <NotificationPanel
            notifications={data.notifications}
            consumers={data.consumers}
          />
        )}
      </main>

      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}
