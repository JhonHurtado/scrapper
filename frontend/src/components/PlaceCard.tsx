import type { Place } from '../types'

interface Props {
  place: Place
}

// Paleta categórica validada (CVD-safe sobre superficie oscura)
export const CATEGORY_CONFIG = {
  monuments: { emoji: '🏛️', label: 'Patrimonio', color: '#c98500' },
  nature: { emoji: '🌿', label: 'Naturaleza', color: '#199e70' },
  viewpoints: { emoji: '🌄', label: 'Mirador', color: '#3987e5' },
  cultural: { emoji: '🎭', label: 'Cultural', color: '#d55181' },
} as const

export type CategoryKey = keyof typeof CATEGORY_CONFIG

export function PlaceCard({ place }: Props) {
  const config = CATEGORY_CONFIG[place.category] ?? CATEGORY_CONFIG.cultural

  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 10,
      padding: 12,
      display: 'flex',
      gap: 12,
      animation: 'slideIn 0.3s ease',
    }}>
      <div style={{
        width: 48, height: 48, borderRadius: 8, flexShrink: 0,
        overflow: 'hidden', background: 'var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22,
      }}>
        {place.mainImage
          ? <img src={place.mainImage} alt={place.name}
              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
            />
          : config.emoji
        }
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 13, fontWeight: 600, color: 'var(--text-primary)',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        }}>
          {place.name}
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>
          {place.city} · {place.department}
        </div>

        <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
          <Tag bg={`${config.color}26`} color={config.color} border={`${config.color}4d`}>
            {config.emoji} {config.label}
          </Tag>
          {place.website && (
            <Tag bg="rgba(99,102,241,0.1)" color="#818cf8" border="rgba(99,102,241,0.3)">
              🔗 Web
            </Tag>
          )}
        </div>

        {place.latitude && place.longitude && (
          <div style={{ fontSize: 10, color: 'var(--text-dimmer)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
            {Math.abs(place.latitude).toFixed(4)}° {place.latitude >= 0 ? 'N' : 'S'}, {Math.abs(place.longitude).toFixed(4)}° {place.longitude >= 0 ? 'E' : 'W'}
          </div>
        )}
      </div>

      <style>{`
        @keyframes slideIn {
          from { opacity: 0; transform: translateY(-6px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  )
}

function Tag({ bg, color, border, children }: {
  bg: string; color: string; border: string; children: React.ReactNode
}) {
  return (
    <span style={{
      fontSize: 10, padding: '2px 8px', borderRadius: 20, fontWeight: 500,
      background: bg, color, border: `1px solid ${border}`,
    }}>
      {children}
    </span>
  )
}
