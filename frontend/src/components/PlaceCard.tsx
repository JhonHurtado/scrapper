import type { Place } from '../types'

interface Props {
  place: Place
}

// Paleta categórica validada (CVD-safe sobre superficie oscura): un color por
// familia; el emoji distingue la categoría del backend dentro de la familia.
const HERITAGE = '#c98500'
const CULTURE = '#d55181'
const NATURE = '#199e70'
const VIEW = '#3987e5'

export const CATEGORY_CONFIG: Record<string, { emoji: string; label: string; color: string }> = {
  iglesias: { emoji: '⛪', label: 'Iglesias', color: HERITAGE },
  monumentos: { emoji: '🗿', label: 'Monumentos', color: HERITAGE },
  sitios_arqueologicos: { emoji: '🏺', label: 'Sitios Arqueológicos', color: HERITAGE },
  sitios_culturales: { emoji: '🏛️', label: 'Sitios Culturales', color: HERITAGE },
  puentes: { emoji: '🌉', label: 'Puentes', color: HERITAGE },
  cementerios: { emoji: '⚰️', label: 'Cementerios', color: HERITAGE },
  museos: { emoji: '🖼️', label: 'Museos', color: CULTURE },
  centros_culturales: { emoji: '🎭', label: 'Centros Culturales', color: CULTURE },
  plazas: { emoji: '🏙️', label: 'Plazas', color: CULTURE },
  parques: { emoji: '🌳', label: 'Parques', color: CULTURE },
  mercados: { emoji: '🛍️', label: 'Mercados', color: CULTURE },
  barrios_y_zonas_urbanas: { emoji: '🏘️', label: 'Barrios y Zonas Urbanas', color: CULTURE },
  miradores: { emoji: '🌄', label: 'Miradores', color: VIEW },
  naturaleza: { emoji: '🌿', label: 'Naturaleza', color: NATURE },
  reservas_naturales: { emoji: '🏞️', label: 'Reservas Naturales', color: NATURE },
  cascadas: { emoji: '💦', label: 'Cascadas', color: NATURE },
  lagos_y_lagunas: { emoji: '🏞️', label: 'Lagos y Lagunas', color: NATURE },
  rios_y_balnearios: { emoji: '🏊', label: 'Ríos y Balnearios', color: NATURE },
  cerros_y_montanas: { emoji: '⛰️', label: 'Cerros y Montañas', color: NATURE },
  playas_y_malecones: { emoji: '🏖️', label: 'Playas y Malecones', color: NATURE },
}

const FALLBACK = { emoji: '📍', label: 'Otro', color: HERITAGE }

const SOURCE_LABEL: Record<string, string> = {
  alcaldia: 'Alcaldía',
  gobernacion: 'Gobernación',
  oficina_turismo: 'Oficina de turismo',
  datos_abiertos: 'datos.gov.co',
}

const GEO_LABEL: Record<string, string> = {
  fuente_oficial: 'coordenadas de la fuente oficial',
  openstreetmap: 'OpenStreetMap',
  google_maps: 'Google Maps',
}

export type CategoryKey = string

export function PlaceCard({ place }: Props) {
  const config = CATEGORY_CONFIG[place.category] ?? FALLBACK

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
          {place.sourceUrl && (
            <a href={place.sourceUrl} target="_blank" rel="noopener noreferrer"
              title={`Fuente oficial: ${place.sourceEntity}`} style={{ textDecoration: 'none' }}>
              <Tag bg="rgba(99,102,241,0.1)" color="#818cf8" border="rgba(99,102,241,0.3)">
                🏛️ {SOURCE_LABEL[place.sourceType] ?? 'Fuente oficial'}
              </Tag>
            </a>
          )}
          {place.verified ? (
            <Tag bg="rgba(25,158,112,0.1)" color="#199e70" border="rgba(25,158,112,0.3)">
              <span title={`Ubicación verificada con ${GEO_LABEL[place.geoSource] ?? place.geoSource}`}>
                ✓ Ubicación verificada
              </span>
            </Tag>
          ) : (
            <Tag bg="rgba(201,133,0,0.1)" color="#c98500" border="rgba(201,133,0,0.3)">
              <span title="No se exporta al backend hasta tener coordenadas verificadas">
                ⚠ Sin ubicación
              </span>
            </Tag>
          )}
        </div>

        {place.sourceEntity && (
          <div style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 4,
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            Fuente: {place.sourceEntity}
          </div>
        )}

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
