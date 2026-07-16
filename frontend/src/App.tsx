import { useState, useCallback, useEffect } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { StatsBar } from './components/StatsBar'
import { LogPanel } from './components/LogPanel'
import { PlacesPanel } from './components/PlacesPanel'
import { ExplorePanel } from './components/ExplorePanel'
import type { Place, LogEntry, ScrapingStats, WsMessage } from './types'

const INITIAL_STATS: ScrapingStats = {
  places_found: 0,
  cities_done: 0,
  cities_total: 0,
  current_city: '',
  current_department: '',
  errors: 0,
  status: 'idle',
}

const PER_PAGE = 200

export default function App() {
  const [view, setView] = useState<'monitor' | 'explorar'>('monitor')
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [livePlaces, setLivePlaces] = useState<Place[]>([])
  const [dataset, setDataset] = useState<Place[]>([])
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState<ScrapingStats>(INITIAL_STATS)

  const addToDataset = useCallback((incoming: Place[]) => {
    setDataset(prev => {
      const ids = new Set(prev.map(p => p.id))
      const fresh = incoming.filter(p => !ids.has(p.id))
      return fresh.length ? [...fresh, ...prev] : prev
    })
  }, [])

  // Carga inicial: estado del scraper + todos los lugares acumulados en la DB
  useEffect(() => {
    let cancelled = false

    fetch('/api/scrape/status')
      .then(r => r.json())
      .then(s => {
        if (cancelled) return
        setStats(prev => ({
          ...prev,
          places_found: s.placesCount ?? 0,
          cities_done: s.citiesDone ?? 0,
          cities_total: s.citiesTotal ?? 0,
          current_city: s.currentCity ?? '',
          errors: s.errors ?? 0,
          status: s.running ? (s.paused ? 'paused' : 'running') : 'idle',
        }))
      })
      .catch(() => {})

    async function loadAll() {
      try {
        let page = 1
        let total = Infinity
        let acc: Place[] = []
        while (acc.length < total && !cancelled) {
          const res = await fetch(`/api/places?page=${page}&per_page=${PER_PAGE}`)
          const data = await res.json()
          total = data.total
          acc = acc.concat(data.places)
          if (data.places.length === 0) break
          page++
        }
        if (!cancelled) setDataset(prev => {
          const ids = new Set(prev.map(p => p.id))
          return [...prev, ...acc.filter(p => !ids.has(p.id))]
        })
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    loadAll()

    return () => { cancelled = true }
  }, [])

  const handleMessage = useCallback((msg: WsMessage) => {
    switch (msg.type) {
      case 'log':
        setLogs(prev => [...prev.slice(-500), {
          level: msg.level,
          message: msg.message,
          timestamp: msg.timestamp,
        }])
        break
      case 'place_found':
        setLivePlaces(prev => [msg.place, ...prev.slice(0, 300)])
        addToDataset([msg.place])
        setStats(prev => ({ ...prev, places_found: prev.places_found + 1 }))
        break
      case 'progress':
        setStats(prev => ({
          ...prev,
          cities_done: msg.citiesDone,
          cities_total: msg.citiesTotal,
          places_found: msg.placesFound,
          current_city: msg.currentCity,
          current_department: msg.currentDepartment,
          status: 'running',
        }))
        break
      case 'city_completed':
        setLogs(prev => [...prev.slice(-500), {
          level: 'info',
          message: `✓ ${msg.city} → ${msg.placesCount} lugares (${msg.duplicatesSkipped} duplicados omitidos)`,
          timestamp: new Date().toISOString(),
        }])
        break
      case 'scrape_complete':
        setStats(prev => ({ ...prev, status: 'completed' }))
        break
      case 'error':
        setStats(prev => ({ ...prev, errors: prev.errors + 1 }))
        break
    }
  }, [addToDataset])

  const wsUrl = `ws://${window.location.host}/ws`
  const { connected } = useWebSocket(wsUrl, { onMessage: handleMessage })

  const handleStart = () =>
    fetch('/api/scrape/start', { method: 'POST' })
      .then(() => setStats(prev => ({ ...prev, status: 'running' })))

  const handlePause = () =>
    fetch('/api/scrape/pause', { method: 'POST' })
      .then(() => setStats(prev => ({ ...prev, status: 'paused' })))

  const handleStop = () =>
    fetch('/api/scrape/stop', { method: 'POST' })
      .then(() => setStats(prev => ({ ...prev, status: 'idle' })))

  const handleExport = () => window.open('/api/export/json', '_blank')

  return (
    <div className="app">
      <StatsBar
        stats={stats}
        connected={connected}
        onStart={handleStart}
        onPause={handlePause}
        onStop={handleStop}
        onExport={handleExport}
      />

      <nav className="tabs" aria-label="Vistas">
        <button
          className={view === 'monitor' ? 'tab active' : 'tab'}
          onClick={() => setView('monitor')}
        >
          📡 Monitor en vivo
        </button>
        <button
          className={view === 'explorar' ? 'tab active' : 'tab'}
          onClick={() => setView('explorar')}
        >
          🔎 Explorar datos ({dataset.length.toLocaleString('es-CO')})
        </button>
      </nav>

      {view === 'monitor' ? (
        <div className="split">
          <LogPanel logs={logs} currentCity={stats.current_city || undefined} />
          <PlacesPanel places={livePlaces} />
        </div>
      ) : (
        <ExplorePanel places={dataset} loading={loading} />
      )}
    </div>
  )
}
