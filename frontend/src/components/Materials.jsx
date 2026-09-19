import React, { useState } from 'react'

export default function Materials({ materials, onRestock, busy }) {
  const [amounts, setAmounts] = useState({})

  return (
    <div className="panel">
      <h3>物料库存 <span className="sub">低于安全库存自动预警；缺料工单在补料后可一键恢复</span></h3>
      <table>
        <thead>
          <tr>
            <th>编码</th><th>名称</th><th>库存</th><th>安全库存</th><th>状态</th><th>紧急调拨</th>
          </tr>
        </thead>
        <tbody>
          {materials.map((m) => {
            const low = m.stock <= m.safety_stock
            return (
              <tr key={m.id} className={low ? 'low' : ''}>
                <td>{m.code}</td>
                <td>{m.name}</td>
                <td>{m.stock} {m.unit}</td>
                <td>{m.safety_stock}</td>
                <td>
                  {low ? <span className="badge amber">库存预警</span> : <span className="badge green">充足</span>}
                </td>
                <td>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <input style={{ width: 90 }} type="number" min="1" placeholder="数量"
                           value={amounts[m.id] ?? ''}
                           onChange={(e) => setAmounts((a) => ({ ...a, [m.id]: Math.max(1, +e.target.value) }))} />
                    <button className="btn small" disabled={busy || !amounts[m.id]}
                            onClick={() => {
                              onRestock(m.id, amounts[m.id])
                              setAmounts((a) => ({ ...a, [m.id]: '' }))
                            }}>
                      调拨
                    </button>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
