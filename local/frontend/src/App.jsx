import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api.js'

// PLAN.md §3 예시 필드. 실제로는 백엔드 /analyze 의 field_spec 으로 가변 명세 가능.
const DEFAULT_FIELD_SPEC = [
  { key: 'full_name',  label: 'Full Name',                     type: 'text' },
  { key: 'account',    label: 'Account No. (Bank Name)',       type: 'text' },
  { key: 'rrn',        label: 'Resident Registration Number',  type: 'text' },
  { key: 'address',    label: 'Address',                       type: 'text' },
  { key: 'phone',      label: 'Phone Number',                  type: 'text' },
]

export default function App() {
  const [models, setModels] = useState([])
  const [devices, setDevices] = useState([])
  const [model, setModel] = useState('')
  const [device, setDevice] = useState('')
  const [uploaded, setUploaded] = useState([]) // 업로드 직후 ImageInfo 목록
  const [jobId, setJobId] = useState(null)
  const [job, setJob] = useState(null)
  const [selectedImage, setSelectedImage] = useState(null)
  const [summary, setSummary] = useState(null)
  const [sheet, setSheet] = useState({ columns: [], rows: [] })
  const [error, setError] = useState('')
  const fileRef = useRef(null)

  // 초기 메타데이터
  useEffect(() => {
    (async () => {
      try {
        const m = await api.listModels()
        const d = await api.listDevices()
        setModels(m.models); setDevices(d.devices)
        if (m.models[0]) setModel(m.models[0])
        if (d.devices[0]) setDevice(d.devices[0])
      } catch (e) { setError(`backend 연결 실패: ${e.message}`) }
    })()
  }, [])

  // 잡 폴링
  useEffect(() => {
    if (!jobId) return
    let alive = true
    const tick = async () => {
      try {
        const j = await api.getJob(jobId)
        if (!alive) return
        setJob(j)
        const s = await api.getSheet(jobId)
        if (!alive) return
        setSheet(s)
      } catch (e) { setError(e.message) }
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => { alive = false; clearInterval(id) }
  }, [jobId])

  // 선택된 이미지의 요약 폴링
  useEffect(() => {
    if (!jobId || !selectedImage) { setSummary(null); return }
    let alive = true
    const tick = async () => {
      try {
        const s = await api.getSummary(jobId, selectedImage)
        if (alive) setSummary(s)
      } catch (e) { setError(e.message) }
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => { alive = false; clearInterval(id) }
  }, [jobId, selectedImage])

  const isRunning = job?.status === 'running'
  const canAnalyze = model && device && uploaded.length > 0 && !isRunning

  const handleUpload = async (e) => {
    const files = [...(e.target.files || [])]
    if (!files.length) return
    setError('')
    try {
      const { images } = await api.upload(files)
      setUploaded((prev) => [...prev, ...images])
    } catch (err) { setError(err.message) }
    if (fileRef.current) fileRef.current.value = ''
  }

  const handleAnalyze = async () => {
    setError('')
    try {
      const { job_id } = await api.analyze({
        image_ids: uploaded.map((i) => i.image_id),
        model, device, field_spec: DEFAULT_FIELD_SPEC,
      })
      setJobId(job_id)
      setSelectedImage(uploaded[0]?.image_id || null)
    } catch (err) { setError(err.message) }
  }

  const handleStop = async () => {
    if (!jobId) return
    try { await api.stop(jobId) } catch (e) { setError(e.message) }
  }

  const handleSaveField = async (key, edited) => {
    if (!jobId || !selectedImage || !summary) return
    const fields = summary.fields.map((f) => (f.key === key ? { ...f, edited } : f))
    try { setSummary(await api.putSummary(jobId, selectedImage, fields)) }
    catch (e) { setError(e.message) }
  }

  const handleComplete = async () => {
    if (!jobId || !selectedImage) return
    try {
      await api.complete(jobId, selectedImage)
      // 다음 이미지로 이동
      const idx = job?.images.findIndex((i) => i.image_id === selectedImage) ?? -1
      const next = job?.images[idx + 1]?.image_id
      if (next) setSelectedImage(next)
    } catch (e) { setError(e.message) }
  }

  const imagesForList = job?.images ?? uploaded
  const imageUrl = selectedImage ? api.imageUrl(selectedImage) : null

  return (
    <div className="app">
      <h1>project_gamma · 손글씨 인식 시연</h1>
      {error && <div className="err">{error}</div>}

      <section className="toolbar">
        <label>
          Model
          <select value={model} onChange={(e) => setModel(e.target.value)} disabled={isRunning}>
            {models.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </label>

        <fieldset className="device">
          <legend>Device</legend>
          {devices.map((d) => (
            <label key={d}>
              <input type="radio" name="device" value={d}
                     checked={device === d} disabled={isRunning}
                     onChange={() => setDevice(d)} /> {d.toUpperCase()}
            </label>
          ))}
        </fieldset>

        <label className="upload">
          Upload Images
          <input ref={fileRef} type="file" multiple accept="image/*,application/pdf"
                 onChange={handleUpload} disabled={isRunning} />
        </label>

        {isRunning
          ? <button className="stop" onClick={handleStop}>Stop</button>
          : <button className="analyze" onClick={handleAnalyze} disabled={!canAnalyze}>Analysis</button>}
      </section>

      {(jobId || uploaded.length > 0) && (
        <section className="work">
          <ImageList images={imagesForList} selected={selectedImage} onSelect={setSelectedImage} />
          <ImageView url={imageUrl} />
          <ImageSummary summary={summary} onEdit={handleSaveField} onComplete={handleComplete} />
        </section>
      )}

      {jobId && (
        <section className="preview">
          <h2>Preview · Sheet</h2>
          <PreviewSheet sheet={sheet} />
        </section>
      )}
    </div>
  )
}

function ImageList({ images, selected, onSelect }) {
  return (
    <div className="panel image-list">
      <h3>Image List</h3>
      <ul>
        {images.map((i) => (
          <li key={i.image_id}
              className={i.image_id === selected ? 'sel' : ''}
              onClick={() => onSelect(i.image_id)}>
            <span className="fn">{i.filename}</span>
            <span className={`badge ${i.status}`}>{i.status}</span>
          </li>
        ))}
        {!images.length && <li className="empty">— 이미지 없음 —</li>}
      </ul>
    </div>
  )
}

function ImageView({ url }) {
  return (
    <div className="panel image-view">
      <h3>Image</h3>
      {url ? <img src={url} alt="" /> : <div className="empty">선택된 이미지 없음</div>}
    </div>
  )
}

function ImageSummary({ summary, onEdit, onComplete }) {
  if (!summary) {
    return <div className="panel summary"><h3>Image Summary</h3><div className="empty">분석 결과 없음</div></div>
  }
  return (
    <div className="panel summary">
      <h3>Image Summary</h3>
      <table>
        <tbody>
          {summary.fields.map((f) => (
            <tr key={f.key}>
              <th>{f.key}</th>
              <td>
                <input value={f.edited ?? f.predicted ?? ''}
                       onChange={(e) => onEdit(f.key, e.target.value)} />
              </td>
              <td className="acc">{f.accuracy != null ? `${(f.accuracy * 100).toFixed(0)}%` : '—'}</td>
            </tr>
          ))}
          {!summary.fields.length && <tr><td className="empty" colSpan={3}>대기 중…</td></tr>}
        </tbody>
      </table>
      <button onClick={onComplete} disabled={summary.status === 'done'}>Complete</button>
    </div>
  )
}

function PreviewSheet({ sheet }) {
  return (
    <table className="sheet">
      <thead>
        <tr>
          <th>image_id</th>
          {sheet.columns.map((c) => <th key={c.key}>{c.label}</th>)}
        </tr>
      </thead>
      <tbody>
        {sheet.rows.map((r) => (
          <tr key={r.image_id}>
            <td>{r.image_id}</td>
            {sheet.columns.map((c) => <td key={c.key}>{r.values[c.key] ?? ''}</td>)}
          </tr>
        ))}
        {!sheet.rows.length && (
          <tr><td className="empty" colSpan={sheet.columns.length + 1}>— Complete 처리된 이미지가 시트에 누적됩니다 —</td></tr>
        )}
      </tbody>
    </table>
  )
}
