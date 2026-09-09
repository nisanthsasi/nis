import { api } from './client'

/** Mirrors the FrameThrower SDK Frame type (metadata + URLs only). */
export interface FTFrame {
  id: string
  imageUrl: string
  thumbUrl: string
  deepLink: string
  score?: number | null
  prompt?: string | null
  film: {
    title: string | null; year: number | null; slug: string | null; director: string | null; dp: string | null
    genres: string[]; frameCount?: number | null; posterUrl?: string | null
  }
  metadata: {
    sceneDescription: string | null; shotType: string | null; cameraAngle: string | null; composition: string | null
    setting: string | null; timeOfDay: string | null; visualStyle: string | null; lensCharacter: string | null
    lightingKey: string | null; lightingQuality?: string | null; lightingDescription: string | null
    moods: string[]; colorPalette: string[] | null; era: string | null
  }
}

export interface BrowseFilters {
  shot_type?: string; lens_character?: string; setting?: string; time_of_day?: string; camera_angle?: string
  visual_style?: string; director?: string; genre?: string; era?: string; limit?: number
}

const qs = (o: Record<string, string | number | undefined>) =>
  new URLSearchParams(Object.entries(o).filter(([, v]) => v !== undefined && v !== '').map(([k, v]) => [k, String(v)])).toString()

export const framesApi = {
  search: (q: string, limit = 24, mode: 'hybrid' | 'description' = 'hybrid') => api<FTFrame[]>(`/api/frames/search?${qs({ q, limit, mode })}`),
  browse: (f: BrowseFilters) => api<FTFrame[]>(`/api/frames/browse?${qs(f as Record<string, string | number | undefined>)}`),
  similar: (id: string, mode: 'semantic' | 'visual' | 'color' = 'visual', limit = 24) => api<FTFrame[]>(`/api/frames/similar/${encodeURIComponent(id)}?${qs({ mode, limit })}`),
  random: (limit = 24) => api<FTFrame[]>(`/api/frames/random?${qs({ limit })}`),
}

/** URL that goes through the server proxy so the image can be drawn to canvas / PDF. */
export const proxied = (url: string) => `/api/img?url=${encodeURIComponent(url)}`
