import React, { useState } from 'react'

const EMPTY = {
  title: '',
  description: '',
  reporter: '市民热线',
  reporter_phone: '',
  location_x: 15,
  location_y: 30,
  address: '',
  severity: 'moderate',
  pipe_diameter_mm: 300,
}

export default function ReportForm({ preset, onSubmitted, onSubmit }) {
  const [form, setForm] = useState(EMPTY)
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)

  React.useEffect(() => {
    if (preset) setForm((f) => ({ ...f, location_x: preset.x, location_y: preset.y }))
  }, [preset])

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const submit = async () => {
    if (!form.title.trim()) {
      setError('请填写事件标题')
      return
    }
    setError('')
    setSending(true)
    try {
      await onSubmit(form)
      setForm(EMPTY)
      onSubmitted && onSubmitted()
    } catch (e) {
      setError(e.message)
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="panel">
      <h3>漏损事件上报 <span className="sub">市民热线 / 巡检员 / 压力监测告警</span></h3>
      <label className="field">事件标题
        <input value={form.title} placeholder="如：望湖区DN300主管道爆管"
               onChange={(e) => set('title', e.target.value)} />
      </label>
      <div className="row2">
        <label className="field">上报来源
          <input value={form.reporter} onChange={(e) => set('reporter', e.target.value)} />
        </label>
        <label className="field">联系电话
          <input value={form.reporter_phone} onChange={(e) => set('reporter_phone', e.target.value)} />
        </label>
      </div>
      <label className="field">现场地址
        <input value={form.address} placeholder="如：望江街与春晖里交叉口"
               onChange={(e) => set('address', e.target.value)} />
      </label>
      <div className="row2">
        <label className="field">坐标 X（可在地图点选）
          <input type="number" value={form.location_x} onChange={(e) => set('location_x', +e.target.value)} />
        </label>
        <label className="field">坐标 Y
          <input type="number" value={form.location_y} onChange={(e) => set('location_y', +e.target.value)} />
        </label>
      </div>
      <div className="row2">
        <label className="field">漏损等级
          <select value={form.severity} onChange={(e) => set('severity', e.target.value)}>
            <option value="minor">轻微（支管渗漏）</option>
            <option value="moderate">一般（配水管漏损）</option>
            <option value="major">较大（干管漏损）</option>
            <option value="critical">重大（大口径爆管）</option>
          </select>
        </label>
        <label className="field">管道口径 DN (mm)
          <select value={form.pipe_diameter_mm} onChange={(e) => set('pipe_diameter_mm', +e.target.value)}>
            <option value={100}>DN100</option>
            <option value={200}>DN200</option>
            <option value={300}>DN300</option>
            <option value={500}>DN500</option>
            <option value="800">DN800</option>
          </select>
        </label>
      </div>
      <label className="field">现场描述
        <textarea rows={3} value={form.description} placeholder="涌水范围、道路积水、是否影响交通等"
                  onChange={(e) => set('description', e.target.value)} />
      </label>
      {error && <div className="note-box red">{error}</div>}
      <button className="btn" disabled={sending} onClick={submit}>
        {sending ? '上报中…' : '📮 提交漏损事件'}
      </button>
    </div>
  )
}
