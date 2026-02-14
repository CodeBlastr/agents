import { useEffect, useRef, useState } from 'react'

const API_BASE = 'http://localhost:8000'

const EMPTY_CONFIG = {
  parcel_id: '',
  portal_url: '',
  portal_profile: {
    parcel_selector: '',
    search_button_selector: '',
    results_container_selector: '',
    balance_regex: '',
    pre_steps: [],
    checkpoint_selector: '',
    checkpoint_min_count: '',
    stop_after_checkpoint: false,
    scraper_mode: 'real',
    results_row_selector: 'table tr',
    row_first_link_selector: 'td:first-child a',
    detail_table_selector: 'table',
    max_properties: '3',
    direct_property_urls_text: '',
  },
}

function fmt(value) {
  if (value === null || value === undefined) return '-'
  return value
}

function modeLabel(mode) {
  if (!mode) return 'unknown'
  return mode.toUpperCase()
}

function toArtifactUrl(path) {
  if (!path) return ''
  if (path.startsWith('/artifacts/')) {
    return `${API_BASE}/api/artifacts/${path.replace('/artifacts/', '')}`
  }
  return path
}

function collectArtifactPaths(details) {
  const artifacts = details?.artifacts || {}
  const singles = Object.entries(artifacts)
    .filter(([key, value]) => key !== 'screenshots' && typeof value === 'string' && value.length > 0)
    .map(([key, value]) => ({ key, path: value, url: toArtifactUrl(value) }))

  const sequence = Array.isArray(artifacts.screenshots)
    ? artifacts.screenshots
      .filter((item) => item?.path)
      .map((item, idx) => ({
        key: item.label || `step_${idx + 1}`,
        path: item.path,
        url: toArtifactUrl(item.path),
      }))
    : []

  const dedup = new Map()
  ;[...sequence, ...singles].forEach((item) => {
    dedup.set(item.path, item)
  })
  return [...dedup.values()]
}

export default function App() {
  const [bots, setBots] = useState([])
  const [notifications, setNotifications] = useState([])
  const [config, setConfig] = useState(EMPTY_CONFIG)
  const [preStepsJson, setPreStepsJson] = useState('[]')
  const [showConfig, setShowConfig] = useState(false)
  const [savingConfig, setSavingConfig] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [running, setRunning] = useState(false)
  const [lastRunResult, setLastRunResult] = useState(null)
  const [lastRunDetails, setLastRunDetails] = useState(null)
  const [liveScreenshots, setLiveScreenshots] = useState([])
  const [liveRunInfo, setLiveRunInfo] = useState(null)
  const [livePropertyTotals, setLivePropertyTotals] = useState([])

  const streamRef = useRef(null)

  const loadBots = async () => {
    const res = await fetch(`${API_BASE}/api/bots`)
    const data = await res.json()
    setBots(data)
  }

  const loadConfig = async () => {
    const res = await fetch(`${API_BASE}/api/bots/tax/config`)
    const data = await res.json()
    const normalized = {
      ...data,
      portal_profile: {
        parcel_selector: data.portal_profile?.parcel_selector || '',
        search_button_selector: data.portal_profile?.search_button_selector || '',
        results_container_selector: data.portal_profile?.results_container_selector || '',
        balance_regex: data.portal_profile?.balance_regex || '',
        pre_steps: data.portal_profile?.pre_steps || [],
        checkpoint_selector: data.portal_profile?.checkpoint_selector || '',
        checkpoint_min_count: data.portal_profile?.checkpoint_min_count?.toString() || '',
        stop_after_checkpoint: Boolean(data.portal_profile?.stop_after_checkpoint),
        scraper_mode: data.portal_profile?.scraper_mode || 'real',
        results_row_selector: data.portal_profile?.results_row_selector || 'table tr',
        row_first_link_selector: data.portal_profile?.row_first_link_selector || 'td:first-child a',
        detail_table_selector: data.portal_profile?.detail_table_selector || 'table',
        max_properties: data.portal_profile?.max_properties?.toString() || '3',
        direct_property_urls_text: Array.isArray(data.portal_profile?.direct_property_urls)
          ? data.portal_profile.direct_property_urls.join('\n')
          : '',
      },
    }
    setConfig(normalized)
    setPreStepsJson(JSON.stringify(normalized.portal_profile.pre_steps, null, 2))
  }

  const loadNotifications = async () => {
    const res = await fetch(`${API_BASE}/api/notifications?bot=tax&limit=20`)
    const data = await res.json()
    setNotifications(data)
  }

  const loadRunDetails = async (runId) => {
    const res = await fetch(`${API_BASE}/api/bots/tax/runs/${runId}`)
    if (!res.ok) return
    const data = await res.json()
    setLastRunDetails(data)
    if (Array.isArray(data.property_details)) {
      setLivePropertyTotals(data.property_details.map((row) => ({
        property_address: row.property_address,
        total_due: row.total_due,
      })))
    }
  }

  const loadAll = async () => {
    setLoading(true)
    try {
      await Promise.all([loadBots(), loadConfig(), loadNotifications()])
      setError('')
    } catch (e) {
      setError(`Failed to load data: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAll()
    return () => {
      if (streamRef.current) {
        streamRef.current.close()
      }
    }
  }, [])

  const appendLiveScreenshot = (payload) => {
    if (!payload?.path) return
    setLiveScreenshots((prev) => {
      if (prev.some((item) => item.path === payload.path)) return prev
      return [...prev, {
        key: payload.label || `live_${prev.length + 1}`,
        path: payload.path,
        url: toArtifactUrl(payload.path),
      }]
    })
  }

  const upsertLiveProperty = (payload) => {
    if (!payload?.property_address) return
    setLivePropertyTotals((prev) => {
      const idx = prev.findIndex((item) => item.property_address === payload.property_address)
      const next = {
        property_address: payload.property_address,
        total_due: payload.total_due,
      }
      if (idx === -1) return [...prev, next]
      return prev.map((item, i) => i === idx ? next : item)
    })
  }

  const connectRunStream = (runId) => {
    if (streamRef.current) {
      streamRef.current.close()
    }
    const source = new EventSource(`${API_BASE}/api/bots/tax/runs/${runId}/events`)
    streamRef.current = source

    source.onmessage = async (event) => {
      const payload = JSON.parse(event.data)
      setLiveRunInfo(payload)

      if (payload.type === 'screenshot_created') {
        appendLiveScreenshot(payload)
      }

      if (payload.type === 'property_scraped') {
        upsertLiveProperty(payload)
      }

      if (payload.type === 'run_finished') {
        setRunning(false)
        source.close()
        streamRef.current = null
        if (payload.result) {
          setLastRunResult(payload.result)
          await loadRunDetails(payload.result.run_id)
        }
        await Promise.all([loadBots(), loadNotifications()])
      }
    }

    source.onerror = () => {
      source.close()
      streamRef.current = null
      setRunning(false)
    }
  }

  const runTaxBot = async () => {
    setRunning(true)
    setError('')
    setLiveScreenshots([])
    setLiveRunInfo(null)
    setLastRunResult(null)
    setLastRunDetails(null)
    setLivePropertyTotals([])
    try {
      const res = await fetch(`${API_BASE}/api/bots/tax/run/start`, { method: 'POST' })
      if (!res.ok) {
        const body = await res.json()
        throw new Error(body.detail || 'Run start failed')
      }
      const data = await res.json()
      connectRunStream(data.run_id)
    } catch (e) {
      setError(`Run failed: ${e.message}`)
      setRunning(false)
    }
  }

  const updateProfile = (key, value) => {
    setConfig((prev) => ({
      ...prev,
      portal_profile: {
        ...prev.portal_profile,
        [key]: value,
      },
    }))
  }

  const saveConfig = async () => {
    setSavingConfig(true)
    setError('')
    try {
      const parsedPreSteps = JSON.parse(preStepsJson || '[]')
      if (!Array.isArray(parsedPreSteps)) {
        throw new Error('Pre-steps JSON must be an array')
      }

      const payload = {
        parcel_id: config.parcel_id,
        portal_url: config.portal_url,
        portal_profile: {
          parcel_selector: config.portal_profile.parcel_selector || null,
          search_button_selector: config.portal_profile.search_button_selector || null,
          results_container_selector: config.portal_profile.results_container_selector || null,
          balance_regex: config.portal_profile.balance_regex || null,
          pre_steps: parsedPreSteps,
          checkpoint_selector: config.portal_profile.checkpoint_selector || null,
          checkpoint_min_count: config.portal_profile.checkpoint_min_count
            ? Number(config.portal_profile.checkpoint_min_count)
            : null,
          stop_after_checkpoint: Boolean(config.portal_profile.stop_after_checkpoint),
          scraper_mode: config.portal_profile.scraper_mode || 'real',
          results_row_selector: config.portal_profile.results_row_selector || 'table tr',
          row_first_link_selector: config.portal_profile.row_first_link_selector || 'td:first-child a',
          detail_table_selector: config.portal_profile.detail_table_selector || 'table',
          max_properties: config.portal_profile.max_properties ? Number(config.portal_profile.max_properties) : 3,
          direct_property_urls: (config.portal_profile.direct_property_urls_text || '')
            .split('\n')
            .map((line) => line.trim())
            .filter((line) => line.length > 0),
        },
      }
      const res = await fetch(`${API_BASE}/api/bots/tax/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        const body = await res.json()
        throw new Error(body.detail || 'Save failed')
      }
      await loadConfig()
    } catch (e) {
      setError(`Save failed: ${e.message}`)
    } finally {
      setSavingConfig(false)
    }
  }

  const artifactItems = collectArtifactPaths(lastRunDetails?.details)
  const streamItems = liveScreenshots.length > 0 ? liveScreenshots : artifactItems

  return (
    <main className="container">
      <h1>Agents Dashboard</h1>
      {loading && <p>Loading...</p>}
      {error && <p className="error">{error}</p>}
      <section className="cards">
        {bots.map((bot) => (
          <article key={bot.slug} className="card">
            <h2>{bot.name}</h2>
            {bot.slug === 'tax' ? (
              <>
                <div className="run-top-grid">
                  <div>
                    <p><strong>Last Run:</strong> {fmt(bot.last_run)}</p>
                    <p><strong>Status:</strong> {fmt(bot.last_status)}</p>
                    <p><strong>Run mode:</strong> <span className={`mode-badge mode-${(bot.mode || 'unknown').toLowerCase()}`}>{modeLabel(bot.mode)}</span></p>
                    <p><strong>Run type:</strong> {fmt(bot.run_type)}</p>
                    <p><strong>Current Balance:</strong> {fmt(bot.current_balance_due)}</p>
                    <p><strong>Previous Balance:</strong> {fmt(bot.previous_balance_due)}</p>
                    <p><strong>Changed:</strong> {bot.changed ? 'yes' : 'no'}</p>
                    {running && (
                      <p><strong>Live Event:</strong> {fmt(liveRunInfo?.type)}</p>
                    )}

                    <div className="property-table-wrap">
                      <h4>Property Address | Total Due</h4>
                      {livePropertyTotals.length === 0 ? (
                        <p>No properties scraped yet.</p>
                      ) : (
                        <table className="property-table">
                          <thead>
                            <tr>
                              <th>Property Address</th>
                              <th>Total Due</th>
                            </tr>
                          </thead>
                          <tbody>
                            {livePropertyTotals.map((row, idx) => (
                              <tr key={`${row.property_address}-${idx}`}>
                                <td>{row.property_address}</td>
                                <td>{row.total_due}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </div>
                  </div>
                  <div className="live-stream-panel">
                    <h4>Live Screens</h4>
                    {streamItems.length === 0 && <p>No screenshots yet.</p>}
                    {streamItems.map((item) => (
                      <figure key={`${item.path}-${item.key}`}>
                        <figcaption><strong>{item.key}</strong> — {item.path}</figcaption>
                        <img src={item.url} alt={item.key} className="artifact-image" />
                      </figure>
                    ))}
                  </div>
                </div>

                <button onClick={runTaxBot} disabled={running}>
                  {running ? 'Running...' : 'Run Now'}
                </button>

                <div className="config-header">
                  <button className="secondary" onClick={() => setShowConfig((v) => !v)}>
                    {showConfig ? 'Hide Config' : 'Edit Config'}
                  </button>
                </div>

                {showConfig && (
                  <div className="config-form">
                    <label>
                      Parcel ID
                      <input value={config.parcel_id} onChange={(e) => setConfig((c) => ({ ...c, parcel_id: e.target.value }))} />
                    </label>
                    <label>
                      Portal URL
                      <input value={config.portal_url} onChange={(e) => setConfig((c) => ({ ...c, portal_url: e.target.value }))} />
                    </label>
                    <label>
                      Scraper Mode
                      <select value={config.portal_profile.scraper_mode} onChange={(e) => updateProfile('scraper_mode', e.target.value)}>
                        <option value="real">Use Real Scraper</option>
                        <option value="stub">Use Stub Scraper</option>
                      </select>
                    </label>
                    <label>
                      Results Row Selector
                      <input value={config.portal_profile.results_row_selector} onChange={(e) => updateProfile('results_row_selector', e.target.value)} />
                    </label>
                    <label>
                      Row First Link Selector
                      <input value={config.portal_profile.row_first_link_selector} onChange={(e) => updateProfile('row_first_link_selector', e.target.value)} />
                    </label>
                    <label>
                      Detail Table Selector
                      <input value={config.portal_profile.detail_table_selector} onChange={(e) => updateProfile('detail_table_selector', e.target.value)} />
                    </label>
                    <label>
                      Max Properties
                      <input type="number" min="1" value={config.portal_profile.max_properties} onChange={(e) => updateProfile('max_properties', e.target.value)} />
                    </label>
                    <label>
                      Direct Property URLs (one per line, optional)
                      <textarea
                        rows={4}
                        value={config.portal_profile.direct_property_urls_text}
                        onChange={(e) => updateProfile('direct_property_urls_text', e.target.value)}
                      />
                    </label>
                    <label>
                      Parcel Selector (optional)
                      <input value={config.portal_profile.parcel_selector} onChange={(e) => updateProfile('parcel_selector', e.target.value)} />
                    </label>
                    <label>
                      Search Button Selector (optional)
                      <input value={config.portal_profile.search_button_selector} onChange={(e) => updateProfile('search_button_selector', e.target.value)} />
                    </label>
                    <label>
                      Results Container Selector (optional)
                      <input value={config.portal_profile.results_container_selector} onChange={(e) => updateProfile('results_container_selector', e.target.value)} />
                    </label>
                    <label>
                      Balance Regex (optional)
                      <input value={config.portal_profile.balance_regex} onChange={(e) => updateProfile('balance_regex', e.target.value)} />
                    </label>
                    <label>
                      Pre-steps JSON (optional)
                      <textarea
                        rows={8}
                        value={preStepsJson}
                        onChange={(e) => setPreStepsJson(e.target.value)}
                      />
                    </label>
                    <label>
                      Checkpoint Selector (optional)
                      <input value={config.portal_profile.checkpoint_selector} onChange={(e) => updateProfile('checkpoint_selector', e.target.value)} />
                    </label>
                    <label>
                      Checkpoint Min Count (optional)
                      <input
                        type="number"
                        min="1"
                        value={config.portal_profile.checkpoint_min_count}
                        onChange={(e) => updateProfile('checkpoint_min_count', e.target.value)}
                      />
                    </label>
                    <label>
                      <input
                        type="checkbox"
                        checked={config.portal_profile.stop_after_checkpoint}
                        onChange={(e) => updateProfile('stop_after_checkpoint', e.target.checked)}
                      />{' '}
                      Stop after checkpoint proof (for flow validation)
                    </label>
                    <button onClick={saveConfig} disabled={savingConfig}>
                      {savingConfig ? 'Saving...' : 'Save'}
                    </button>
                  </div>
                )}
              </>
            ) : (
              <>
                <p><strong>Last Run:</strong> {fmt(bot.last_run)}</p>
                <p><strong>Status:</strong> {fmt(bot.last_status)}</p>
                <p><strong>Run mode:</strong> <span className={`mode-badge mode-${(bot.mode || 'unknown').toLowerCase()}`}>{modeLabel(bot.mode)}</span></p>
                <p><strong>Run type:</strong> {fmt(bot.run_type)}</p>
                <p><strong>Current Balance:</strong> {fmt(bot.current_balance_due)}</p>
                <p><strong>Previous Balance:</strong> {fmt(bot.previous_balance_due)}</p>
                <p><strong>Changed:</strong> {bot.changed ? 'yes' : 'no'}</p>
              </>
            )}
          </article>
        ))}
      </section>

      {lastRunResult && (
        <section className="notifications">
          <h3>Last Run Details</h3>
          <p><strong>Run ID:</strong> {fmt(lastRunResult.run_id)}</p>
          <p><strong>Status:</strong> {fmt(lastRunResult.status)}</p>
          <p><strong>Mode:</strong> <span className={`mode-badge mode-${(lastRunResult.mode || 'unknown').toLowerCase()}`}>{modeLabel(lastRunResult.mode)}</span></p>
          <p><strong>Run Type:</strong> {fmt(lastRunResult.run_type)}</p>
          {lastRunResult.run_type === 'checkpoint_only' ? (
            <p><strong>Balance:</strong> Checkpoint validated; no balance extracted in this run.</p>
          ) : (
            <>
              <p><strong>Current Balance:</strong> {fmt(lastRunResult.current_balance_due)}</p>
              <p><strong>Previous Balance:</strong> {fmt(lastRunResult.previous_balance_due)}</p>
            </>
          )}
          <p><strong>Changed:</strong> {lastRunResult.changed ? 'yes' : 'no'}</p>
          <p><strong>Message:</strong> {fmt(lastRunResult.message)}</p>

          {lastRunDetails?.details?.checkpoint_selector && (
            <div className="run-proof">
              <h4>Checkpoint Proof</h4>
              <p><strong>Selector:</strong> {fmt(lastRunDetails.details.checkpoint_selector)}</p>
              <p><strong>Count:</strong> {fmt(lastRunDetails.details.checkpoint_count)}</p>
              <p><strong>Min Count:</strong> {fmt(lastRunDetails.details.checkpoint_min_count)}</p>
              <p><strong>URL:</strong> {fmt(lastRunDetails.details.checkpoint_url)}</p>
              <p><strong>Excerpt:</strong> {fmt(lastRunDetails.details.checkpoint_text_excerpt)}</p>
            </div>
          )}
        </section>
      )}

      <section className="notifications">
        <h3>Notifications</h3>
        {notifications.length === 0 && <p>No notifications yet.</p>}
        {notifications.map((item, idx) => (
          <p key={`${item.created_at}-${idx}`}>
            <strong>{fmt(item.created_at)}</strong>: {item.message}
          </p>
        ))}
      </section>
    </main>
  )
}
