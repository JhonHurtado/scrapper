import { useEffect, useRef } from 'react'
import type { LogEntry } from '../types'

interface Props {
  logs: LogEntry[]
  currentCity?: string
}

const LEVEL_COLORS: Record<LogEntry['level'], string> = {
  info: 'var(--accent-green)',
  warn: 'var(--accent-yellow)',
  error: 'var(--accent-red)',
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString('es-CO', {
      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    })
  } catch {
    return '--:--:--'
  }
}

export function LogPanel({ logs, currentCity }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  return (
    <div style={{
      background: 'var(--bg-panel)',
      borderRight: '1px solid var(--border-dim)',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }}>
      <div style={{
        padding: '9px 16px',
        borderBottom: '1px solid var(--border-dim)',
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: '1.5px',
        color: 'var(--text-dim)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <span>📋 LOGS EN TIEMPO REAL</span>
        {currentCity && (
          <span style={{
            background: 'var(--bg-card)',
            color: 'var(--accent-blue)',
            borderRadius: 4,
            padding: '2px 8px',
            fontSize: 10,
            fontWeight: 600,
          }}>
            ⟳ {currentCity}
          </span>
        )}
      </div>

      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '10px 14px',
        fontFamily: 'var(--font-mono)',
        fontSize: 11,
        lineHeight: 1.75,
      }}>
        {logs.length === 0 && (
          <div style={{ color: 'var(--text-dimmer)', fontStyle: 'italic' }}>
            Esperando inicio del scraping...
          </div>
        )}
        {logs.map((log, i) => (
          <div key={i} style={{ display: 'flex', gap: 10 }}>
            <span style={{ color: 'var(--text-dimmer)', minWidth: 60, flexShrink: 0 }}>
              {formatTime(log.timestamp)}
            </span>
            <span style={{ color: LEVEL_COLORS[log.level], wordBreak: 'break-word' }}>
              {log.message}
            </span>
          </div>
        ))}
        <div ref={bottomRef} style={{ height: 1 }} />
      </div>
    </div>
  )
}
