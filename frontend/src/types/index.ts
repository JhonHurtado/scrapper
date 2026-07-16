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

// El backend emite camelCase (ver scrape_all en playwright_scraper.py)
export type WsMessage =
  | { type: 'connected'; session_id: string }
  | { type: 'log'; level: LogEntry['level']; message: string; timestamp: string }
  | { type: 'place_found'; place: Place }
  | { type: 'progress'; citiesDone: number; citiesTotal: number; placesFound: number; currentCity: string; currentDepartment: string }
  | { type: 'city_completed'; city: string; placesCount: number; duplicatesSkipped: number }
  | { type: 'scrape_complete'; totalPlaces: number; durationSeconds: number; errors: number }
  | { type: 'error'; message: string; city?: string }
