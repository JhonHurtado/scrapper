import { useMemo, useState } from 'react'
import type { Place } from '../types'
import { PlaceCard, CATEGORY_CONFIG, type CategoryKey } from './PlaceCard'

const PAGE_SIZE = 120
const CATS = Object.keys(CATEGORY_CONFIG) as CategoryKey[]

interface Props {
  places: Place[]
  loading: boolean
}

export function ExplorePanel({ places, loading }: Props) {
  const [q, setQ] = useState('')
  const [dept, setDept] = useState('')
  const [city, setCity] = useState('')
  const [cat, setCat] = useState<'' | CategoryKey>('')
  const [limit, setLimit] = useState(PAGE_SIZE)

  const departments = useMemo(
    () => [...new Set(places.map(p => p.department))].sort((a, b) => a.localeCompare(b)),
    [places],
  )
  const cities = useMemo(
    () => [...new Set(places.filter(p => !dept || p.department === dept).map(p => p.city))]
      .sort((a, b) => a.localeCompare(b)),
    [places, dept],
  )

  // Filtros sin categoría (para que los chips muestren conteos del contexto actual)
  const base = useMemo(() => {
    const nq = q.trim().toLowerCase()
    return places.filter(p =>
      (!dept || p.department === dept) &&
      (!city || p.city === city) &&
      (!nq || p.name.toLowerCase().includes(nq) || p.city.toLowerCase().includes(nq)
        || p.address.toLowerCase().includes(nq)),
    )
  }, [places, q, dept, city])

  const filtered = useMemo(
    () => (cat ? base.filter(p => p.category === cat) : base),
    [base, cat],
  )

  const catCounts = useMemo(() => {
    const counts = { monuments: 0, nature: 0, viewpoints: 0, cultural: 0 }
    for (const p of base) counts[p.category] = (counts[p.category] ?? 0) + 1
    return counts
  }, [base])

  // Segundo gráfico: departamentos, o ciudades si ya hay departamento elegido
  const regionRows = useMemo(() => {
    const counts = new Map<string, number>()
    const key = dept ? 'city' as const : 'department' as const
    for (const p of filtered) counts.set(p[key], (counts.get(p[key]) ?? 0) + 1)
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 12)
      .map(([label, value]) => ({ label, value, color: '#3987e5' }))
  }, [filtered, dept])

  const filteredCities = useMemo(() => new Set(filtered.map(p => p.city)).size, [filtered])
  const filteredDepts = useMemo(() => new Set(filtered.map(p => p.department)).size, [filtered])
  const hasFilters = q !== '' || dept !== '' || city !== '' || cat !== ''

  const resetLimit = () => setLimit(PAGE_SIZE)
  const clearFilters = () => { setQ(''); setDept(''); setCity(''); setCat(''); resetLimit() }

  return (
    <div style={{ overflowY: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>

      {/* Resumen */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 26, fontWeight: 700, color: 'var(--text-primary)' }}>
          {filtered.length.toLocaleString('es-CO')}
        </span>
        <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
          lugares turísticos · {filteredCities} ciudades · {filteredDepts} departamentos
        </span>
        {loading && <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>⟳ cargando…</span>}
        {hasFilters && (
          <button onClick={clearFilters} className="control" style={{ cursor: 'pointer', fontSize: 11 }}>
            ✕ Limpiar filtros
          </button>
        )}
      </div>

      {/* Filtros */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          className="control"
          style={{ flex: 1, minWidth: 200 }}
          placeholder="Buscar por nombre, ciudad o dirección…"
          value={q}
          onChange={e => { setQ(e.target.value); resetLimit() }}
          aria-label="Buscar lugares"
        />
        <select
          className="control"
          value={dept}
          onChange={e => { setDept(e.target.value); setCity(''); resetLimit() }}
          aria-label="Filtrar por departamento"
        >
          <option value="">Todos los departamentos</option>
          {departments.map(d => <option key={d} value={d}>{d}</option>)}
        </select>
        <select
          className="control"
          value={city}
          onChange={e => { setCity(e.target.value); resetLimit() }}
          aria-label="Filtrar por ciudad"
        >
          <option value="">Todas las ciudades</option>
          {cities.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      {/* Chips de categoría (filtro + leyenda) */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {CATS.map(key => {
          const c = CATEGORY_CONFIG[key]
          const active = cat === key
          return (
            <button
              key={key}
              onClick={() => { setCat(active ? '' : key); resetLimit() }}
              className="control"
              aria-pressed={active}
              style={{
                cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 7,
                borderColor: active ? c.color : 'var(--border)',
                background: active ? `${c.color}1f` : 'var(--bg-card)',
                color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
              }}
            >
              <span style={{ width: 8, height: 8, borderRadius: 2, background: c.color }} />
              {c.emoji} {c.label}
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)' }}>
                {catCounts[key]}
              </span>
            </button>
          )
        })}
      </div>

      {/* Distribución */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 12 }}>
        <BarChart
          title="Por categoría"
          rows={CATS.map(key => ({
            label: CATEGORY_CONFIG[key].label,
            icon: CATEGORY_CONFIG[key].emoji,
            value: catCounts[key],
            color: CATEGORY_CONFIG[key].color,
          }))}
        />
        <BarChart
          title={dept ? `Ciudades de ${dept}` : 'Top departamentos'}
          rows={regionRows}
        />
      </div>

      {/* Resultados */}
      {filtered.length === 0 ? (
        <div style={{
          padding: '48px 16px', textAlign: 'center', color: 'var(--text-dim)',
          display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'center',
        }}>
          <span style={{ fontSize: 36 }}>🔍</span>
          <span>
            {places.length === 0
              ? 'Todavía no hay lugares scrapeados.'
              : 'Ningún lugar coincide con estos filtros.'}
          </span>
          {hasFilters && (
            <button onClick={clearFilters} className="control" style={{ cursor: 'pointer' }}>
              Limpiar filtros
            </button>
          )}
        </div>
      ) : (
        <>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
            gap: 10,
          }}>
            {filtered.slice(0, limit).map(place => (
              <PlaceCard key={place.id} place={place} />
            ))}
          </div>
          {filtered.length > limit && (
            <button
              onClick={() => setLimit(l => l + PAGE_SIZE * 2)}
              className="control"
              style={{ cursor: 'pointer', alignSelf: 'center', padding: '9px 22px' }}
            >
              Mostrar más ({(filtered.length - limit).toLocaleString('es-CO')} restantes)
            </button>
          )}
        </>
      )}
    </div>
  )
}

function BarChart({ title, rows }: {
  title: string
  rows: { label: string; value: number; color: string; icon?: string }[]
}) {
  const max = Math.max(...rows.map(r => r.value), 1)
  return (
    <div style={{
      background: 'var(--bg-surface)', border: '1px solid var(--border-dim)',
      borderRadius: 10, padding: '12px 14px',
    }}>
      <div style={{
        fontSize: 11, fontWeight: 700, letterSpacing: 1.2, color: 'var(--text-dim)',
        marginBottom: 10, textTransform: 'uppercase',
      }}>
        {title}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        {rows.map(r => (
          <div
            key={r.label}
            title={`${r.label}: ${r.value}`}
            style={{ display: 'grid', gridTemplateColumns: '128px 1fr 44px', alignItems: 'center', gap: 8 }}
          >
            <span style={{
              fontSize: 11, color: 'var(--text-secondary)',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {r.icon ? `${r.icon} ` : ''}{r.label}
            </span>
            <div style={{ height: 10 }}>
              <div style={{
                width: `${(r.value / max) * 100}%`, minWidth: r.value > 0 ? 3 : 0,
                height: '100%', background: r.color, borderRadius: '0 4px 4px 0',
              }} />
            </div>
            <span style={{
              fontSize: 11, fontFamily: 'var(--font-mono)',
              color: 'var(--text-primary)', textAlign: 'right',
            }}>
              {r.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
