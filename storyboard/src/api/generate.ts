import { api } from './client'
import type { AspectRatio, ProviderId } from '../types'
import type { ProviderStatus } from '../store/useProject'

export interface GenerateResult { pngBase64: string; mime: string; provider: ProviderId; cost: string }

export const generateApi = {
  providers: () => api<ProviderStatus & { pollinationsWaitMs: number }>('/api/providers'),
  generate: (body: { provider: ProviderId; prompt: string; aspect: AspectRatio; seed?: number; referenceImages?: string[]; quality?: string }) =>
    api<GenerateResult>('/api/generate', { method: 'POST', body: JSON.stringify(body) }),
}
