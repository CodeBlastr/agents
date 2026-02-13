import { useEffect, useState } from 'react'

const API_BASE = 'http://localhost:8000'

function fmt(value) {
  if (value === null || value === undefined) return '-'
  return value
}

export default function App() {
  const [bots, setBots] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [running, setRunning] = useState(false)

  const loadBots = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/bots`)
      const data = await res.json()
      setBots(data)
      setError('')
    } catch (e) {
      setError(`Failed to load bots: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadBots()
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
      await loadBots()
    } catch (e) {
      setError(`Run failed: ${e.message}`)
    } finally {
      setRunning(false)
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
              <button onClick={runTaxBot} disabled={running}>
                {running ? 'Running...' : 'Run Now'}
              </button>
            )}
          </article>
        ))}
      </section>
    </main>
  )
}
