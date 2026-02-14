import { useEffect, useMemo, useRef, useState } from 'react'

const API_BASE = ''

function api(path, options = {}) {
  return fetch(`${API_BASE}${path}`, options)
}

function fmtDate(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function fmtMoney(value) {
  if (value === null || value === undefined) return '-'
  const num = Number(value)
  if (Number.isNaN(num)) return String(value)
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(num)
}

function toArtifactUrl(path, cacheKey = '') {
  if (!path) return ''
  const suffix = cacheKey ? `?v=${encodeURIComponent(cacheKey)}` : ''
  if (path.startsWith('/artifacts/')) {
    return `/api/artifacts/${path.replace('/artifacts/', '')}${suffix}`
  }
  return `${path}${suffix}`
}

function usePathname() {
  const [pathname, setPathname] = useState(window.location.pathname)
  useEffect(() => {
    const onPop = () => setPathname(window.location.pathname)
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])
  return pathname
}

function navigate(path) {
  if (window.location.pathname === path) return
  window.history.pushState({}, '', path)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

function EventTimeline({ events }) {
  if (!events.length) {
    return <p className="panel-muted">No run events yet.</p>
  }

  return (
    <ul className="event-log">
      {events.map((event, idx) => (
        <li key={`${event.timestamp || 'ts'}-${idx}`}>
          <span>{event.type}</span>
          <small>{fmtDate(event.timestamp)}</small>
        </li>
      ))}
    </ul>
  )
}

function LatestPropertiesTable({ rows, emptyMessage }) {
  if (!rows.length) {
    return <p className="panel-muted">{emptyMessage}</p>
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Property Address</th>
            <th>Total Due</th>
            <th>Scraped At</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.property_address}-${row.id}`}>
              <td>{row.property_address}</td>
              <td>{fmtMoney(row.total_due)}</td>
              <td>{fmtDate(row.scraped_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function DashboardPage() {
  const [bots, setBots] = useState([])
  const [latestRows, setLatestRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [runId, setRunId] = useState(null)
  const [running, setRunning] = useState(false)
  const [events, setEvents] = useState([])

  const streamRef = useRef(null)

  const taxBot = useMemo(() => bots.find((bot) => bot.slug === 'tax') || null, [bots])

  const loadDashboardData = async () => {
    const [botsRes, rowsRes] = await Promise.all([
      api('/api/bots'),
      api('/api/bots/tax/properties/latest'),
    ])

    if (!botsRes.ok) {
      const body = await botsRes.text()
      throw new Error(`Failed loading bots: ${body}`)
    }
    if (!rowsRes.ok) {
      const body = await rowsRes.text()
      throw new Error(`Failed loading latest properties: ${body}`)
    }

    const [botsData, rowsData] = await Promise.all([botsRes.json(), rowsRes.json()])
    setBots(botsData)
    setLatestRows(rowsData)
  }

  const stopStream = () => {
    if (streamRef.current) {
      streamRef.current.close()
      streamRef.current = null
    }
  }

  const connectStream = (nextRunId) => {
    stopStream()
    const source = new EventSource(`/api/bots/tax/runs/${nextRunId}/events`)
    streamRef.current = source

    source.onmessage = async (message) => {
      const payload = JSON.parse(message.data)
      setEvents((prev) => [...prev, payload])

      if (payload.type === 'db_committed') {
        await loadDashboardData()
      }

      if (payload.type === 'run_finished') {
        setRunning(false)
        stopStream()
        await loadDashboardData()
      }
    }

    source.onerror = () => {
      setRunning(false)
      stopStream()
    }
  }

  const refreshTaxBot = async () => {
    setError('')
    setEvents([])
    setRunning(true)

    try {
      const res = await api('/api/bots/tax/refresh', { method: 'POST' })
      if (!res.ok) {
        const body = await res.text()
        throw new Error(body || 'Refresh request failed')
      }
      const data = await res.json()
      setRunId(data.run_id)
      connectStream(data.run_id)
    } catch (exc) {
      setError(String(exc.message || exc))
      setRunning(false)
    }
  }

  useEffect(() => {
    const run = async () => {
      setLoading(true)
      setError('')
      try {
        await loadDashboardData()
      } catch (exc) {
        setError(String(exc.message || exc))
      } finally {
        setLoading(false)
      }
    }
    run()

    return () => stopStream()
  }, [])

  return (
    <main className="page-shell">
      <header className="top-bar">
        <div>
          <p className="eyebrow">Agent Admin Dashboard</p>
          <h1>Operations Index</h1>
        </div>
        <button className="ghost" onClick={() => navigate('/bots/tax')}>Tax Bot Details</button>
      </header>

      {loading && <p className="panel-muted">Loading dashboard...</p>}
      {error && <p className="error-banner">{error}</p>}

      {taxBot && (
        <section className="card-grid">
          <article className="bot-card">
            <h2>{taxBot.name}</h2>
            <div className="bot-stats">
              <p><strong>Last Run ID:</strong> {taxBot.last_run_id ?? '-'}</p>
              <p><strong>Status:</strong> {taxBot.last_run_status || '-'}</p>
              <p><strong>Last Run At:</strong> {fmtDate(taxBot.last_run_at)}</p>
              <p><strong>Latest Properties:</strong> {taxBot.latest_property_count}</p>
              <p><strong>Last Error:</strong> {taxBot.last_error_summary || '-'}</p>
            </div>
            <div className="action-row">
              <button onClick={refreshTaxBot} disabled={running}>
                {running ? 'Refreshing...' : 'Refresh Data'}
              </button>
              <button className="ghost" onClick={() => navigate('/bots/tax')}>Open Detail Page</button>
            </div>
            {runId && <p className="panel-muted">Live run: #{runId}</p>}
          </article>

          <article className="panel-card">
            <h3>Latest Database Rows</h3>
            <LatestPropertiesTable rows={latestRows} emptyMessage="No snapshots committed yet." />
          </article>

          <article className="panel-card full-width">
            <h3>Live Run Timeline</h3>
            <EventTimeline events={events} />
          </article>
        </section>
      )}
    </main>
  )
}

function TaxBotDetailPage() {
  const [bot, setBot] = useState(null)
  const [latestRows, setLatestRows] = useState([])
  const [selectedRun, setSelectedRun] = useState(null)
  const [events, setEvents] = useState([])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  const streamRef = useRef(null)

  const stopStream = () => {
    if (streamRef.current) {
      streamRef.current.close()
      streamRef.current = null
    }
  }

  const loadBot = async () => {
    const res = await api('/api/bots/tax')
    if (!res.ok) {
      const body = await res.text()
      throw new Error(`Failed loading bot: ${body}`)
    }
    const data = await res.json()
    setBot(data)

    if (Array.isArray(data.recent_runs) && data.recent_runs.length > 0 && !selectedRun) {
      await loadRun(data.recent_runs[0].id)
    }
  }

  const loadLatestRows = async () => {
    const res = await api('/api/bots/tax/properties/latest')
    if (!res.ok) {
      const body = await res.text()
      throw new Error(`Failed loading latest rows: ${body}`)
    }
    setLatestRows(await res.json())
  }

  const loadRun = async (runId) => {
    const res = await api(`/api/bots/tax/runs/${runId}`)
    if (!res.ok) {
      const body = await res.text()
      throw new Error(`Failed loading run details: ${body}`)
    }
    setSelectedRun(await res.json())
  }

  const loadAll = async () => {
    await Promise.all([loadBot(), loadLatestRows()])
  }

  const connectStream = (runId) => {
    stopStream()
    const source = new EventSource(`/api/bots/tax/runs/${runId}/events`)
    streamRef.current = source

    source.onmessage = async (message) => {
      const payload = JSON.parse(message.data)
      setEvents((prev) => [...prev, payload])

      if (payload.type === 'db_committed') {
        await loadLatestRows()
      }

      if (payload.type === 'run_finished') {
        setRunning(false)
        stopStream()
        await Promise.all([loadBot(), loadLatestRows(), loadRun(runId)])
      }
    }

    source.onerror = () => {
      setRunning(false)
      stopStream()
    }
  }

  const refresh = async () => {
    setError('')
    setEvents([])
    setRunning(true)

    try {
      const res = await api('/api/bots/tax/refresh', { method: 'POST' })
      if (!res.ok) {
        const body = await res.text()
        throw new Error(body || 'Refresh request failed')
      }
      const payload = await res.json()
      connectStream(payload.run_id)
      await loadRun(payload.run_id)
    } catch (exc) {
      setError(String(exc.message || exc))
      setRunning(false)
    }
  }

  useEffect(() => {
    const run = async () => {
      setError('')
      try {
        await loadAll()
      } catch (exc) {
        setError(String(exc.message || exc))
      }
    }
    run()

    return () => stopStream()
  }, [])

  return (
    <main className="page-shell">
      <header className="top-bar">
        <div>
          <p className="eyebrow">Tax Bot v0</p>
          <h1>Bot Detail</h1>
        </div>
        <div className="action-row">
          <button className="ghost" onClick={() => navigate('/')}>Back to Index</button>
          <button onClick={refresh} disabled={running}>{running ? 'Refreshing...' : 'Refresh Data'}</button>
        </div>
      </header>

      {error && <p className="error-banner">{error}</p>}

      <section className="card-grid">
        <article className="panel-card">
          <h3>Source URLs (Hard-coded)</h3>
          <ul className="source-list">
            {(bot?.source_urls || []).map((url) => <li key={url}>{url}</li>)}
          </ul>
        </article>

        <article className="panel-card">
          <h3>Latest Per-Property Snapshot</h3>
          <LatestPropertiesTable rows={latestRows} emptyMessage="No snapshots available yet." />
        </article>

        <article className="panel-card">
          <h3>Recent Runs</h3>
          {!bot?.recent_runs?.length && <p className="panel-muted">No runs yet.</p>}
          {!!bot?.recent_runs?.length && (
            <ul className="run-list">
              {bot.recent_runs.map((run) => (
                <li key={run.id}>
                  <button className="run-row" onClick={() => loadRun(run.id)}>
                    <span>Run #{run.id}</span>
                    <span>{run.status}</span>
                    <span>{fmtDate(run.started_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </article>

        <article className="panel-card full-width">
          <h3>Live Events</h3>
          <EventTimeline events={events} />
        </article>

        {selectedRun && (
          <article className="panel-card full-width">
            <h3>Run #{selectedRun.run_id} Diagnostics</h3>
            <p><strong>Status:</strong> {selectedRun.status}</p>
            <p><strong>Started:</strong> {fmtDate(selectedRun.started_at)}</p>
            <p><strong>Finished:</strong> {fmtDate(selectedRun.finished_at)}</p>
            <p><strong>Error:</strong> {selectedRun.error_summary || '-'}</p>

            <h4>Per URL Results</h4>
            <div className="url-results">
              {(selectedRun.details_json?.url_results || []).map((item, idx) => (
                <div className="url-result" key={`${item.source_url}-${idx}`}>
                  <p><strong>URL:</strong> {item.source_url}</p>
                  <p><strong>Status:</strong> {item.status}</p>
                  <p><strong>Final URL:</strong> {item.final_url || '-'}</p>
                  <p><strong>Property:</strong> {item.property_address || '-'}</p>
                  <p><strong>Total Due:</strong> {item.total_due ? fmtMoney(item.total_due) : '-'}</p>
                  <p><strong>Error:</strong> {item.error || '-'}</p>
                  <div className="artifact-strip">
                    {Object.entries(item.artifacts || {}).map(([label, path]) => (
                      path ? (
                        <a key={`${label}-${path}`} href={toArtifactUrl(path, selectedRun.run_id)} target="_blank" rel="noreferrer">
                          {label}
                        </a>
                      ) : null
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </article>
        )}
      </section>
    </main>
  )
}

export default function App() {
  const pathname = usePathname()
  if (pathname === '/bots/tax') {
    return <TaxBotDetailPage />
  }
  return <DashboardPage />
}
