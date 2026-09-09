import { api, ApiError } from './client'
import type { DirectorProfile, ShotDraft } from '../types'

export interface ClaudeShotList { sceneSummary: string; shots: ShotDraft[]; model: string }

export async function claudeShotList(scene: { heading: string; text: string; characters: string[] }, director: DirectorProfile, aspectRatio: string): Promise<ClaudeShotList | null> {
  try {
    return await api<ClaudeShotList>('/api/shotlist', { method: 'POST', body: JSON.stringify({ scene, director, aspectRatio }) })
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null
    throw e
  }
}
