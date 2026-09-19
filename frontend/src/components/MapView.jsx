import React, { useMemo, useRef } from 'react'
import { SEVERITY_LABEL, ORDER_STATUS_LABEL, TEAM_STATUS_LABEL } from '../api'

const SCALE = 8 // 0..100 map units -> 800px viewBox

export default function MapView({ data, selectedEventId, onSelectEvent, onMapClick, drawMode }) {
  const svgRef = useRef(null)

  const impactedZoneIds = useMemo(() => {
    const ev = data.impact && data.impact.event_id === selectedEventId ? data.impact : null
    return new Set((ev ? ev.affected_zones : []).map((z) => z.id))
  }, [data.impact, selectedEventId])

  const impactedValveIds = useMemo(() => {
    const ev = data.impact && data.impact.event_id === selectedEventId ? data.impact : null
    return new Set((ev ? ev.valves_to_close : []).map((v) => v.id))
  }, [data.impact, selectedEventId])

  const impactedUserIds = useMemo(() => {
    const ev = data.impact && data.impact.event_id === selectedEventId ? data.impact : null
    return new Set((ev ? ev.affected_users : []).map((u) => u.id))
  }, [data.impact, selectedEventId])

  const polygonPoints = (polygon) =>
    polygon
      .split(';')
      .filter(Boolean)
      .map((p) => {
        const [x, y] = p.split(',')
        return `${x * SCALE},${y * SCALE}`
      })
      .join(' ')

  const handleClick = (e) => {
    if (!drawMode || !onMapClick || !svgRef.current) return
    const pt = svgRef.current.createSVGPoint()
    pt.x = e.clientX
    pt.y = e.clientY
    const ctm = svgRef.current.getScreenCTM()
    if (!ctm) return
    const loc = pt.matrixTransform(ctm.inverse())
    onMapClick({ x: +(loc.x / SCALE).toFixed(1), y: +(loc.y / SCALE).toFixed(1) })
  }

  const teamColor = (status) =>
    ({ available: '#34d399', enroute: '#38bdf8', onsite: '#a78bfa', repairing: '#fbbf24',
       blocked_material: '#f87171', blocked_road: '#f87171' }[status] || '#94a3b8')

  return (
    <div className="map-wrap">
      <svg ref={svgRef} className="map" viewBox="0 0 800 800" onClick={handleClick}
           style={{ cursor: drawMode ? 'crosshair' : 'default' }}>
        <rect x="0" y="0" width="800" height="800" fill="#0a1626" />

        {/* zones */}
        {data.zones.map((z) => {
          const hit = impactedZoneIds.has(z.id)
          return (
            <g key={`z${z.id}`}>
              <polygon
                points={polygonPoints(z.polygon)}
                fill={hit ? 'rgba(56,189,248,0.22)' : 'rgba(56,189,248,0.05)'}
                stroke={hit ? '#38bdf8' : '#23405f'}
                strokeWidth={hit ? 2 : 1}
                strokeDasharray={hit ? '0' : '4 3'}
              />
              <text x={z.centroid_x * SCALE} y={z.centroid_y * SCALE}
                    fill={hit ? '#bae6fd' : '#54708f'} fontSize="15" fontWeight="700" textAnchor="middle">
                {z.name}{hit ? '（受影响）' : ''}
              </text>
            </g>
          )
        })}

        {/* pipes */}
        {data.pipes.map((p) => (
          <line key={`p${p.id}`} x1={p.from_x * SCALE} y1={p.from_y * SCALE}
                x2={p.to_x * SCALE} y2={p.to_y * SCALE}
                stroke="#3b5d83" strokeWidth={Math.max(2, p.diameter_mm / 120)} />
        ))}

        {/* users */}
        {data.users.map((u) => (
          <circle key={`u${u.id}`} cx={u.location_x * SCALE} cy={u.location_y * SCALE}
                  r={u.priority ? 4.5 : 2.6}
                  fill={impactedUserIds.has(u.id) ? (u.priority ? '#f87171' : '#fbbf24') : (u.priority ? '#fb7185' : '#47617e')}
                  opacity={impactedUserIds.size === 0 || impactedUserIds.has(u.id) ? 1 : 0.5} />
        ))}

        {/* valves */}
        {data.valves.map((v) => {
          const hit = impactedValveIds.has(v.id)
          return (
            <g key={`v${v.id}`}>
              <rect x={v.location_x * SCALE - 5} y={v.location_y * SCALE - 5} width="10" height="10"
                    fill={v.is_open ? (hit ? '#fbbf24' : '#2f7d6e') : '#f87171'}
                    stroke={hit ? '#fde68a' : '#0a1626'}
                    transform={`rotate(45 ${v.location_x * SCALE} ${v.location_y * SCALE})`} />
            </g>
          )
        })}

        {/* closures */}
        {data.closures.map((c) => (
          <g key={`c${c.id}`}>
            <line x1={c.from_x * SCALE} y1={c.from_y * SCALE} x2={c.to_x * SCALE} y2={c.to_y * SCALE}
                  stroke="#f87171" strokeWidth="5" strokeDasharray="10 6" opacity="0.85" />
            <text x={(c.from_x + c.to_x) / 2 * SCALE} y={(c.from_y + c.to_y) / 2 * SCALE - 10}
                  fill="#fca5a5" fontSize="11" textAnchor="middle">⛔ {c.reason}</text>
          </g>
        ))}

        {/* teams */}
        {data.teams.map((t) => (
          <g key={`t${t.id}`}>
            <circle cx={t.location_x * SCALE} cy={t.location_y * SCALE} r="9"
                    fill={teamColor(t.status)} stroke="#0a1626" strokeWidth="2" />
            <text x={t.location_x * SCALE} y={t.location_y * SCALE + 3.5}
                  fontSize="10" fontWeight="700" textAnchor="middle" fill="#08121f">修</text>
            <text x={t.location_x * SCALE} y={t.location_y * SCALE - 14}
                  fontSize="10" textAnchor="middle" fill={teamColor(t.status)}>
              {t.name.slice(0, 5)}·{TEAM_STATUS_LABEL[t.status]}
            </text>
          </g>
        ))}

        {/* events */}
        {data.events.map((ev) => {
          const color = SEVERITY_LABEL[ev.severity]?.color || '#ccc'
          const selected = ev.id === selectedEventId
          return (
            <g key={`e${ev.id}`} style={{ cursor: 'pointer' }}
               onClick={(e) => { e.stopPropagation(); onSelectEvent && onSelectEvent(ev) }}>
              <circle cx={ev.location_x * SCALE} cy={ev.location_y * SCALE} r={selected ? 16 : 11}
                      fill="none" stroke={color} strokeWidth="2" opacity="0.5">
                <animate attributeName="r" values={`${selected ? 14 : 9};${selected ? 20 : 15};${selected ? 14 : 9}`}
                         dur="1.6s" repeatCount="indefinite" />
              </circle>
              <circle cx={ev.location_x * SCALE} cy={ev.location_y * SCALE} r="7" fill={color} stroke="#0a1626" strokeWidth="1.5" />
              <text x={ev.location_x * SCALE} y={ev.location_y * SCALE - 14} fontSize="11" fontWeight="700"
                    fill={color} textAnchor="middle">💧{ev.code}</text>
            </g>
          )
        })}
      </svg>

      <div className="legend">
        <span><i className="dot" style={{ background: '#fbbf24' }} />待关阀门</span>
        <span><i className="dot" style={{ background: '#f87171' }} />已关阀/封路</span>
        <span><i className="dot" style={{ background: '#2f7d6e' }} />正常阀门</span>
        <span><i className="dot" style={{ background: '#34d399' }} />待命队伍</span>
        <span><i className="dot" style={{ background: '#38bdf8' }} />出动队伍</span>
        <span><i className="dot" style={{ background: '#fb7185' }} />重点用户</span>
        <span>点击事件标记查看详情；上报模式下点击地图定位漏点</span>
      </div>
    </div>
  )
}
