import type { ScrapingStats } from '../types'

interface Props {
  stats: ScrapingStats
  connected: boolean
  onStart: () => void
  onPause: () => void
  onStop: () => void
  onExport: () => void
}

const STATUS_COLORS: Record<ScrapingStats['status'], string> = {
  idle: 'var(--text-dim)',
  running: 'var(--accent-green)',
  paused: 'var(--accent-yellow)',
  completed: 'var(--accent-blue)',
}

const STATUS_LABELS: Record<ScrapingStats['status'], string> = {
  idle: 'Inactivo',
  running: 'Scrapeando',
  paused: 'Pausado',
  completed: 'Completado',
}

export function StatsBar({ stats, connected, onStart, onPause, onStop, onExport }: Props) {
  const progress = stats.cities_total > 0
    ? Math.round((stats.cities_done / stats.cities_total) * 100)
    : 0

  const isRunning = stats.status === 'running'
  const statusColor = STATUS_COLORS[stats.status]

  return (
    <div style={{
      background: 'var(--bg-surface)',
      borderBottom: '1px solid var(--border)',
      padding: '10px 20px',
      display: 'flex',
      alignItems: 'center',
      gap: '16px',
      flexWrap: 'wrap',
    }}>
      <div style={{ fontWeight: 700, fontSize: 15, display: 'flex', alignItems: 'center', gap: 8, whiteSpace: 'nowrap' }}>
        <span>🗺️</span> Colombia Tourist Scraper
      </div>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <Chip value={stats.places_found} label="Lugares" color="var(--accent-green)" />
        <Chip value={`${stats.cities_done}/${stats.cities_total}`} label="Ciudades" color="var(--accent-blue)" />
        <Chip value={`${progress}%`} label="Progreso" color="var(--accent-purple)" />
        <Chip value={stats.errors} label="Errores" color={stats.errors > 0 ? 'var(--accent-red)' : 'var(--text-dim)'} />
      </div>

      <div style={{ flex: 1, minWidth: 150 }}>
        {stats.current_city && (
          <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 4 }}>
            ⟳ {stats.current_city}, {stats.current_department}
          </div>
        )}
        <div style={{ height: 5, background: 'var(--bg-card)', borderRadius: 3, overflow: 'hidden' }}>
          <div style={{
            width: `${progress}%`,
            height: '100%',
            background: 'linear-gradient(90deg, #6366f1, #8b5cf6)',
            borderRadius: 3,
            transition: 'width 0.5s ease',
          }} />
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap' }}>
        <span style={{
          width: 8, height: 8, borderRadius: '50%',
          background: statusColor,
          animation: isRunning ? 'pulse 1.5s infinite' : 'none',
          display: 'inline-block',
        }} />
        <span style={{ color: statusColor }}>{STATUS_LABELS[stats.status]}</span>
        {!connected && <span style={{ color: 'var(--accent-red)', marginLeft: 6 }}>· WS desconectado</span>}
      </div>

      <div style={{ display: 'flex', gap: 8 }}>
        {!isRunning && (
          <Btn onClick={onStart} bg="#16a34a" label="▶ Iniciar" />
        )}
        {isRunning && (
          <>
            <Btn onClick={onPause} bg="#d97706" label="⏸ Pausar" />
            <Btn onClick={onStop} bg="#dc2626" label="⏹ Detener" />
          </>
        )}
        <Btn onClick={onExport} bg="#1e40af" label="⬇ Exportar JSON" />
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  )
}

function Chip({ value, label, color }: { value: string | number; label: string; color: string }) {
  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 8,
      padding: '5px 12px',
      textAlign: 'center',
      minWidth: 70,
    }}>
      <div style={{ fontSize: 18, fontWeight: 700, color, lineHeight: 1.2 }}>{value}</div>
      <div style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 2 }}>{label}</div>
    </div>
  )
}

function Btn({ onClick, bg, label }: { onClick: () => void; bg: string; label: string }) {
  return (
    <button onClick={onClick} style={{
      background: bg,
      color: 'white',
      border: 'none',
      borderRadius: 8,
      padding: '7px 14px',
      fontSize: 12,
      fontWeight: 600,
      cursor: 'pointer',
      whiteSpace: 'nowrap',
    }}>
      {label}
    </button>
  )
}
