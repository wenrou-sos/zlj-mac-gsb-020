import React from 'react'

const TYPE_STYLE = {
  source: { fill: '#2563eb', r: 11, label: '水厂' },
  junction: { fill: '#64748b', r: 6, label: '' },
  valve: { fill: '#f59e0b', r: 8, label: '阀' }
}

export default function MapView({
  nodes = [],
  pipes = [],
  consumers = [],
  teams = [],
  closures = [],
  incidents = [],
  highlight = {},
  selectedPipeId = null,
  onPipeClick
}) {
  const nodeById = Object.fromEntries(nodes.map((n) => [n.id, n]))
  const closureEdgeSet = new Set(
    (closures || [])
      .filter((c) => c.active)
      .map((c) => [c.start_node_id, c.end_node_id].sort().join('-'))
  )
  const affectedNodeIds = new Set(
    (consumers || [])
      .filter((c) => (highlight.consumerIds || []).includes(c.id))
      .map((c) => c.node_id)
  )
  const valveIds = new Set(highlight.valveIds || [])
  const incidentPipeIds = new Set(incidents.map((i) => i.pipe_id).filter(Boolean))

  return (
    <svg viewBox="0 0 900 560" className="net-svg" role="img" aria-label="管网示意图">
      {/* pipes */}
      {pipes.map((p) => {
        const a = nodeById[p.start_node_id]
        const b = nodeById[p.end_node_id]
        if (!a || !b) return null
        const edgeKey = [p.start_node_id, p.end_node_id].sort().join('-')
        const closed = closureEdgeSet.has(edgeKey)
        const broken = incidentPipeIds.has(p.id) || selectedPipeId === p.id
        const cls = ['pipe']
        if (closed) cls.push('closed')
        if (broken) cls.push('broken')
        return (
          <g key={p.id} onClick={() => onPipeClick?.(p)} className="pipe-g">
            <line
              x1={a.x} y1={a.y} x2={b.x} y2={b.y}
              className={cls.join(' ')}
              strokeWidth={p.diameter_mm >= 500 ? 7 : p.diameter_mm >= 300 ? 5 : 3}
            />
            {closed && (
              <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 8}
                    className="closure-tag" textAnchor="middle">🚧 封闭</text>
            )}
          </g>
        )
      })}

      {/* highlighted affected zones */}
      {[...affectedNodeIds].map((nid) => {
        const n = nodeById[nid]
        return n && <circle key={`z${nid}`} cx={n.x} cy={n.y} r={26} className="zone" />
      })}

      {/* consumers */}
      {consumers.map((c, i) => {
        const n = nodeById[c.node_id]
        if (!n) return null
        const angle = (i % 5) * 1.25
        const dx = Math.cos(angle) * 34
        const dy = 30 + Math.sin(angle) * 10
        const affected = (highlight.consumerIds || []).includes(c.id)
        return (
          <g key={c.id} transform={`translate(${n.x + dx},${n.y + dy})`}>
            <circle r={7} className={`consumer ${affected ? 'affected' : ''}`} />
            <text y={3} textAnchor="middle" className="consumer-icon">🏠</text>
            <text y={20} textAnchor="middle" className="consumer-label">
              {c.name.length > 6 ? c.name.slice(0, 6) : c.name}
            </text>
          </g>
        )
      })}

      {/* nodes */}
      {nodes.map((n) => {
        const st = TYPE_STYLE[n.type] || TYPE_STYLE.junction
        const isClosedValve = n.type === 'valve' && !n.is_open
        const isIsolation = valveIds.has(n.id)
        return (
          <g key={n.id} transform={`translate(${n.x},${n.y})`}>
            {(isIsolation || isClosedValve) && <circle r={13} className="valve-ring" />}
            <circle r={st.r} fill={isClosedValve ? '#dc2626' : st.fill}
                    stroke="#0f172a" strokeWidth={1} />
            {n.type !== 'junction' && (
              <text y={-14} textAnchor="middle" className="node-label">{n.code}</text>
            )}
            {n.type === 'source' && (
              <text y={3} textAnchor="middle" className="source-icon">💧</text>
            )}
          </g>
        )
      })}

      {/* repair teams */}
      {teams.map((t) => (
        <g key={t.id} transform={`translate(${t.x},${t.y})`}>
          <circle r={9} className={`team team-${t.status}`} />
          <text y={3.5} textAnchor="middle" className="team-icon">🚛</text>
          <text y={-14} textAnchor="middle" className="team-label">{t.name}</text>
        </g>
      ))}
    </svg>
  )
}
