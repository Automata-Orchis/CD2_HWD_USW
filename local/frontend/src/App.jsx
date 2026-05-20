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
  const [uploaded, setUploaded] = useState([]) // 업로드 전체 누적 — Image List 의 소스
  const [jobId, setJobId] = useState(null)
  const [job, setJob] = useState(null)
  const [selectedImage, setSelectedImage] = useState(null)
  const [summary, setSummary] = useState(null)
  // image_id → SheetRow. 새 job 으로 바꿔도 이전 done 행이 유지되도록 frontend 에서 누적한다.
  const [accumulatedRows, setAccumulatedRows] = useState({})
  const [error, setError] = useState('')
  const fileRef = useRef(null)
  // done 처리된 이미지의 마지막 ImageSummary 캐시. 새 job 으로 재분석할 때 backend 는
  // 이전 job_id 의 field_results 를 모르므로 빈 fields 가 돌아오는데, 그 자리에 채워 넣는다.
  const doneSummariesRef = useRef({})

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

  // 잡 폴링 + 시트 누적
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
        if (s.rows.length) {
          setAccumulatedRows((prev) => {
            const merged = { ...prev }
            for (const row of s.rows) merged[row.image_id] = row
            return merged
          })
        }
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
        if (!alive) return
        // 새 job 에서 이전에 done 처리된 이미지를 조회하면 fields 가 비어 들어온다.
        // 그 경우 캐시해 둔 직전 결과로 채워 표시한다.
        const cached = doneSummariesRef.current[selectedImage]
        const next = (s.fields.length === 0 && cached) ? cached : s
        if (next.status === 'done' && next.fields.length > 0) {
          doneSummariesRef.current[next.image_id] = next
        }
        setSummary(next)
      } catch (e) { setError(e.message) }
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => { alive = false; clearInterval(id) }
  }, [jobId, selectedImage])

  // Image List: 업로드된 모든 이미지를 표시하고, 현재 job 의 status 만 덮어쓴다.
  // blank 상태는 다루지 않기로 했으므로 done 이 아니면 working 으로 정규화한다.
  const statusMap = useMemo(() => {
    if (!job) return {}
    return Object.fromEntries(job.images.map((i) => [i.image_id, i.status]))
  }, [job])

  // 한 번이라도 done 으로 들어간 적이 있는 image_id 는 새 job 의 statusMap 에 없어도
  // done 으로 유지한다 (accumulatedRows 는 시트 누적과 동일한 done 집합을 이미 갖고 있다).
  const imagesForList = useMemo(() => uploaded.map((u) => ({
    ...u,
    status: (statusMap[u.image_id] === 'done' || accumulatedRows[u.image_id]) ? 'done' : 'working',
  })), [uploaded, statusMap, accumulatedRows])

  const fieldSpec = job?.field_spec ?? DEFAULT_FIELD_SPEC
  const sheetRows = useMemo(() => Object.values(accumulatedRows), [accumulatedRows])

  const isRunning = job?.status === 'running'
  const undoneCount = imagesForList.filter((i) => i.status !== 'done').length
  const canAnalyze = model && device && undoneCount > 0 && !isRunning

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
      // 이미 done 인 이미지는 다시 보내지 않는다 → 기존 작업 결과 보존.
      const undone = imagesForList.filter((i) => i.status !== 'done')
      if (!undone.length) { setError('처리할 새 이미지가 없습니다'); return }
      const { job_id } = await api.analyze({
        image_ids: undone.map((i) => i.image_id),
        model, device, field_spec: DEFAULT_FIELD_SPEC,
      })
      setJobId(job_id)
      setSelectedImage(undone[0].image_id)
    } catch (err) { setError(err.message) }
  }

  const handleStop = async () => {
    if (!jobId) return
    try { await api.stop(jobId) } catch (e) { setError(e.message) }
  }

  const handleCommitFields = async (fields) => {
    if (!jobId || !selectedImage) return
    try { setSummary(await api.putSummary(jobId, selectedImage, fields)) }
    catch (e) { setError(e.message) }
  }

  const handleComplete = async () => {
    if (!jobId || !selectedImage) return
    try {
      await api.complete(jobId, selectedImage)
      // done 직후 selectedImage 를 다음 이미지로 옮기기 전, 방금 완료된 이미지의 summary 를
      // 한 번 더 읽어 캐시한다 (다음 job 에서 빈 fields 로 돌아왔을 때의 폴백용).
      const done = await api.getSummary(jobId, selectedImage)
      if (done.fields.length > 0) doneSummariesRef.current[selectedImage] = done
      const idx = imagesForList.findIndex((i) => i.image_id === selectedImage)
      const next = imagesForList.slice(idx + 1).find((i) => i.status !== 'done')
      if (next) setSelectedImage(next.image_id)
    } catch (e) { setError(e.message) }
  }

  const selectedFile = uploaded.find((u) => u.image_id === selectedImage)
  const isPdf = !!selectedFile?.filename?.toLowerCase().endsWith('.pdf')
  const imageUrl = selectedImage ? api.imageUrl(selectedImage) : null

  return (
    <div className="app">
      <h1>project_gamma · 손글씨 인식 시연</h1>
      {error && <div className="err">{error}</div>}

      <section className="toolbar">
        <label>
          <span className="cap">Model</span>
          <select value={model} onChange={(e) => setModel(e.target.value)} disabled={isRunning}>
            {models.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </label>

        <div className="device-field">
          <span className="cap">Device</span>
          <div className="device">
            {devices.map((d) => (
              <label key={d}>
                <input type="radio" name="device" value={d}
                       checked={device === d} disabled={isRunning}
                       onChange={() => setDevice(d)} /> {d.toUpperCase()}
              </label>
            ))}
          </div>
        </div>

        <label className="upload">
          <span className="cap">Upload Images</span>
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
          <ImageView url={imageUrl} isPdf={isPdf} />
          <ImageSummary
            summary={summary}
            fieldSpec={fieldSpec}
            onCommitFields={handleCommitFields}
            onComplete={handleComplete}
          />
        </section>
      )}

      {(jobId || sheetRows.length > 0) && (
        <>
          <h2>Preview · Sheet</h2>
          <section className="preview">
            <div className="sheet-scroll">
              <PreviewSheet columns={fieldSpec} rows={sheetRows} />
            </div>
          </section>
        </>
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

function ImageView({ url, isPdf }) {
  // Chromium PDF viewer 상단 툴바 제거: #toolbar=0&navpanes=0.
  const pdfSrc = url ? `${url}#toolbar=0&navpanes=0` : ''
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const stageRef = useRef(null)
  const imgRef = useRef(null)

  // 이미지가 바뀌면 줌/팬을 초기화한다.
  useEffect(() => { setZoom(1); setPan({ x: 0, y: 0 }) }, [url])

  // 스케일 적용 후 이미지 끝이 stage 경계를 넘지 않도록 pan 을 클램프한다.
  // stage 중앙 정렬이므로 한 축에서의 허용 오프셋은 max(0, (scaledDim - stageDim)/2).
  const clampPan = (px, py, z) => {
    const img = imgRef.current
    const stage = stageRef.current
    if (!img || !stage) return { x: px, y: py }
    const sw = stage.offsetWidth, sh = stage.offsetHeight
    const dw = img.offsetWidth * z, dh = img.offsetHeight * z
    const maxX = Math.max(0, (dw - sw) / 2)
    const maxY = Math.max(0, (dh - sh) / 2)
    return {
      x: Math.max(-maxX, Math.min(maxX, px)),
      y: Math.max(-maxY, Math.min(maxY, py)),
    }
  }

  // 줌 변경 시 현재 pan 을 새 경계로 다시 끌어다 놓는다 (줌아웃 시 밖으로 새는 것 방지).
  useEffect(() => {
    setPan((p) => (zoom <= 1 ? { x: 0, y: 0 } : clampPan(p.x, p.y, zoom)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zoom])

  // React 의 onWheel 은 passive listener 라 preventDefault 가 무시된다.
  // 페이지 스크롤을 막고 줌으로만 동작시키기 위해 native 로 직접 바인딩한다.
  useEffect(() => {
    const el = stageRef.current
    if (!el || isPdf || !url) return
    const onWheel = (e) => {
      e.preventDefault()
      const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15
      setZoom((z) => Math.max(1, Math.min(8, z * factor)))
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [isPdf, url])

  const onMouseDown = (e) => {
    if (zoom <= 1) return
    e.preventDefault()
    const start = { x: e.clientX, y: e.clientY, px: pan.x, py: pan.y }
    const onMove = (ev) => {
      setPan(clampPan(
        start.px + (ev.clientX - start.x),
        start.py + (ev.clientY - start.y),
        zoom,
      ))
    }
    const onUp = () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  const onDoubleClick = () => { setZoom(1); setPan({ x: 0, y: 0 }) }

  // 우하단 미니맵: 전체 이미지 사각형 + 현재 보이는 영역 사각형.
  // 줌 > 1 일 때만, 그리고 refs 가 준비된 이후에만 그린다.
  let minimap = null
  if (zoom > 1 && imgRef.current && stageRef.current) {
    const iw = imgRef.current.offsetWidth
    const ih = imgRef.current.offsetHeight
    const sw = stageRef.current.offsetWidth
    const sh = stageRef.current.offsetHeight
    if (iw && ih) {
      const aspect = iw / ih
      const MAX = 100
      const mw = aspect >= 1 ? MAX : MAX * aspect
      const mh = aspect >= 1 ? MAX / aspect : MAX
      const fracW = Math.min(1, sw / (iw * zoom))
      const fracH = Math.min(1, sh / (ih * zoom))
      const cx = 0.5 - pan.x / (iw * zoom)
      const cy = 0.5 - pan.y / (ih * zoom)
      minimap = (
        <div className="minimap" style={{ width: mw, height: mh }}>
          <div className="minimap-viewport"
               style={{
                 left: mw * (cx - fracW / 2),
                 top: mh * (cy - fracH / 2),
                 width: mw * fracW,
                 height: mh * fracH,
               }} />
        </div>
      )
    }
  }

  return (
    <div className="panel image-view">
      <h3>Image</h3>
      {!url
        ? <div className="empty">선택된 이미지 없음</div>
        : isPdf
          ? <embed src={pdfSrc} type="application/pdf" className="pdf-embed" />
          : (
            <div ref={stageRef}
                 className={`zoom-stage ${zoom > 1 ? 'zoomed' : ''}`}
                 onMouseDown={onMouseDown}
                 onDoubleClick={onDoubleClick}>
              <img ref={imgRef} src={url} alt="" draggable={false}
                   style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }} />
              {minimap}
            </div>
          )}
    </div>
  )
}

function ImageSummary({ summary, fieldSpec, onCommitFields, onComplete }) {
  // 입력값은 컴포넌트 로컬 draft 로 관리한다.
  // - 키 입력마다 부모 상태를 비동기로 갈아끼우면 React 가 컨트롤드 input 의 값을 되돌리며
  //   커서가 튀고 한글 IME composition 이 끊긴다. 로컬 동기 업데이트로만 input 값을 굴린다.
  // - 서버 PUT 은 Complete 시점에 한 번만 보낸다.
  const [drafts, setDrafts] = useState({})

  useEffect(() => {
    if (!summary) { setDrafts({}); return }
    const byKey = Object.fromEntries(summary.fields.map((f) => [f.key, f]))
    const init = {}
    for (const spec of fieldSpec) {
      const f = byKey[spec.key]
      init[spec.key] = (f?.edited ?? f?.predicted ?? '')
    }
    setDrafts(init)
    // image_id 가 바뀔 때, 그리고 같은 이미지의 field 결과 개수가 변할 때 재초기화한다.
    // 후자는 Stop 으로 결과가 폐기되어 fields 가 비워지는 경우를 잡기 위함이다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [summary?.image_id, summary?.fields.length])

  if (!summary) {
    return <div className="panel summary"><h3>Image Summary</h3><div className="empty">분석 결과 없음</div></div>
  }

  const byKey = Object.fromEntries(summary.fields.map((f) => [f.key, f]))

  const handleComplete = async () => {
    const fields = fieldSpec.map((spec) => {
      const f = byKey[spec.key]
      return {
        key: spec.key,
        predicted: f?.predicted ?? null,
        accuracy: f?.accuracy ?? null,
        edited: drafts[spec.key] ?? null,
      }
    })
    await onCommitFields(fields)
    onComplete()
  }

  return (
    <div className="panel summary">
      <h3>Image Summary</h3>
      <table>
        <tbody>
          {fieldSpec.map((spec) => {
            const f = byKey[spec.key]
            return (
              <tr key={spec.key}>
                <th>{spec.label}</th>
                <td>
                  <input
                    value={drafts[spec.key] ?? ''}
                    onChange={(e) => setDrafts((d) => ({ ...d, [spec.key]: e.target.value }))}
                  />
                </td>
                <td className="acc">{f?.accuracy != null ? `${(f.accuracy * 100).toFixed(0)}%` : '—'}</td>
              </tr>
            )
          })}
          {!fieldSpec.length && <tr><td className="empty" colSpan={3}>대기 중…</td></tr>}
        </tbody>
      </table>
      <button onClick={handleComplete} disabled={summary.status === 'done'}>Complete</button>
    </div>
  )
}

function PreviewSheet({ columns, rows }) {
  return (
    <table className="sheet">
      <thead>
        <tr>
          <th>image_id</th>
          {columns.map((c) => <th key={c.key}>{c.label}</th>)}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.image_id}>
            <td>{r.image_id}</td>
            {columns.map((c) => <td key={c.key}>{r.values?.[c.key] ?? ''}</td>)}
          </tr>
        ))}
        {!rows.length && (
          <tr><td className="empty" colSpan={columns.length + 1}>— Complete 처리된 이미지가 시트에 누적됩니다 —</td></tr>
        )}
      </tbody>
    </table>
  )
}
