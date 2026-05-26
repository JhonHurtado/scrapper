import { useState, useCallback } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { StatsBar } from './components/StatsBar'
import { LogPanel } from './components/LogPanel'
import { PlacesPanel } from './components/PlacesPanel'
import type { Place, LogEntry, ScrapingStats, WsMessage } from './types'

const INITIAL_STATS: ScrapingStats = {
  places_found: 0,
  cities_done: 0,
  cities_total: 130,
  current_city: '',
  current_department: '',
  errors: 0,
  status: 'idle',
}

export default function App() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [places, setPlaces] = useState<Place[]>([])
  const [stats, setStats] = useState<ScrapingStats>(INITIAL_STATS)

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
        setPlaces(prev => [msg.place, ...prev])
        setStats(prev => ({ ...prev, places_found: prev.places_found + 1 }))
        break
      case 'progress':
        setStats(prev => ({
          ...prev,
          cities_done: msg.cities_done,
          cities_total: msg.cities_total,
          places_found: msg.places_found,
          current_city: msg.current_city,
          current_department: msg.current_department,
          status: 'running',
        }))
        break
      case 'city_completed':
        setLogs(prev => [...prev.slice(-500), {
          level: 'info',
          message: `✓ ${msg.city} → ${msg.places_count} lugares`,
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
  }, [])

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
      <div className="split">
        <LogPanel logs={logs} currentCity={stats.current_city || undefined} />
        <PlacesPanel places={places} />
      </div>
    </div>
  )
}
