import { useEffect, useState } from 'react'
import type { Frame } from '../types'
import { getImageUrl } from '../store/db'

/** Resolve a frame to something an <img> can show. Local images come from IndexedDB, references from their URL. */
export function useFrameSrc(frame: Frame | null | undefined, preferThumb = true): string | null {
  const imageId = frame?.imageId
  const url = frame ? (preferThumb ? frame.thumbUrl || frame.url : frame.url || frame.thumbUrl) : undefined
  const [resolved, setResolved] = useState<{ id: string; url: string | null } | null>(null)
  useEffect(() => {
    if (!imageId) return
    let alive = true
    void getImageUrl(imageId).then((u) => { if (alive) setResolved({ id: imageId, url: u ?? null }) })
    return () => { alive = false }
  }, [imageId])
  if (imageId) return resolved && resolved.id === imageId ? resolved.url : null
  return url ?? null
}
