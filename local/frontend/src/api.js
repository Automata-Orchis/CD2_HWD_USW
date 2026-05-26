const BASE = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

async function j(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) {
    let detail = {}
    try { detail = await res.json() } catch {}
    throw new Error(detail.message || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  base: BASE,
  listModels:  () => j('/models'),
  listDevices: () => j('/devices'),
  listTemplates: () => j('/templates'),
  upload: (files) => {
    const fd = new FormData()
    for (const f of files) fd.append('files', f)
    return j('/upload', { method: 'POST', body: fd })
  },
  analyze: (body) => j('/analyze', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
  }),
  stop: (jobId) => j(`/jobs/${jobId}/stop`, { method: 'POST' }),
  getJob: (jobId) => j(`/jobs/${jobId}`),
  getSummary: (jobId, appId) => j(`/jobs/${jobId}/applications/${appId}`),
  putSummary: (jobId, appId, fields) => j(`/jobs/${jobId}/applications/${appId}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ fields })
  }),
  complete: (jobId, appId) => j(`/jobs/${jobId}/applications/${appId}/complete`, { method: 'POST' }),
  getSheet: (jobId) => j(`/jobs/${jobId}/sheet`),
  pageUrl: (appId, ord) => `${BASE}/applications/${appId}/pages/${ord}/file`,
}
