import { useEffect, useState } from 'react'

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
  },
}

function fmt(value) {
  if (value === null || value === undefined) return '-'
  return value
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
  }, [])

  const runTaxBot = async () => {
    setRunning(true)
    setError('')
    try {
      const res = await fetch(`${API_BASE}/api/bots/tax/run`, { method: 'POST' })
      if (!res.ok) {
        const body = await res.json()
        throw new Error(body.detail || 'Run failed')
      }
      await Promise.all([loadBots(), loadNotifications()])
    } catch (e) {
      setError(`Run failed: ${e.message}`)
    } finally {
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

  return (
    <main className="container">
      <h1>Agents Dashboard</h1>
      {loading && <p>Loading...</p>}
      {error && <p className="error">{error}</p>}
      <section className="cards">
        {bots.map((bot) => (
          <article key={bot.slug} className="card">
            <h2>{bot.name}</h2>
            <p><strong>Last Run:</strong> {fmt(bot.last_run)}</p>
            <p><strong>Status:</strong> {fmt(bot.last_status)}</p>
            <p><strong>Current Balance:</strong> {fmt(bot.current_balance_due)}</p>
            <p><strong>Previous Balance:</strong> {fmt(bot.previous_balance_due)}</p>
            <p><strong>Changed:</strong> {bot.changed ? 'yes' : 'no'}</p>
            {bot.slug === 'tax' && (
              <>
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
            )}
          </article>
        ))}
      </section>

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
