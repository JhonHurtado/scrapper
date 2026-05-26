import type { Place } from '../types'
import { PlaceCard } from './PlaceCard'

interface Props {
  places: Place[]
}

export function PlacesPanel({ places }: Props) {
  return (
    <div style={{ background: '#111827', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{
        padding: '9px 16px',
        borderBottom: '1px solid var(--border-dim)',
        fontSize: 11, fontWeight: 700, letterSpacing: '1.5px', color: 'var(--text-dim)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <span>🏛️ LUGARES ENCONTRADOS · {places.length}</span>
        <span style={{ background: 'var(--bg-card)', color: 'var(--text-dim)', borderRadius: 4, padding: '2px 8px', fontSize: 10 }}>
          últimos primero
        </span>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {places.length === 0 && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: '100%', color: 'var(--text-dimmer)', fontStyle: 'italic',
            flexDirection: 'column', gap: 12,
          }}>
            <span style={{ fontSize: 40 }}>🇨🇴</span>
            <span>Los lugares aparecerán aquí en tiempo real</span>
          </div>
        )}
        {places.map((place) => (
          <PlaceCard key={place.id} place={place} />
        ))}
      </div>
    </div>
  )
}
