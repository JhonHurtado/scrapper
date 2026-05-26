export interface Place {
  id: string
  name: string
  slug: string
  description: string
  shortDescription: string | null
  address: string
  city: string
  department: string
  country: string
  latitude: number | null
  longitude: number | null
  mainImage: string | null
  phone: string | null
  email: string | null
  website: string | null
  category: 'monuments' | 'nature' | 'viewpoints' | 'cultural'
}

export interface LogEntry {
  level: 'info' | 'warn' | 'error'
  message: string
  timestamp: string
}

export interface ScrapingStats {
  places_found: number
  cities_done: number
  cities_total: number
  current_city: string
  current_department: string
  errors: number
  status: 'idle' | 'running' | 'paused' | 'completed'
}

export type WsMessage =
  | { type: 'connected'; session_id: string }
  | { type: 'log'; level: LogEntry['level']; message: string; timestamp: string }
  | { type: 'place_found'; place: Place }
  | { type: 'progress'; cities_done: number; cities_total: number; places_found: number; current_city: string; current_department: string }
  | { type: 'city_completed'; city: string; places_count: number; duplicates_skipped: number }
  | { type: 'scrape_complete'; total_places: number; duration_seconds: number; errors: number }
  | { type: 'error'; message: string; city?: string }
