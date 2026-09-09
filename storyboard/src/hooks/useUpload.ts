import { useCallback } from 'react'
import { uid } from '../lib/id'
import { resizeImage } from '../lib/image'
import { putImage } from '../store/db'
import { useProject } from '../store/useProject'

/** Upload image files onto a shot as candidate frames. */
export function useUpload() {
  const addFrame = useProject((s) => s.addFrame)
  const toast = useProject((s) => s.toast)
  return useCallback(async (shotId: string, files: FileList | File[] | null | undefined) => {
    if (!files) return
    const list = Array.from(files).filter((f) => f.type.startsWith('image/'))
    if (!list.length) { toast('Drop image files (png, jpg, webp).', 'error'); return }
    for (const f of list) {
      try {
        const blob = await resizeImage(f)
        const id = uid('img')
        await putImage(id, blob)
        addFrame(shotId, { kind: 'upload', imageId: id }, true)
      } catch (e) {
        toast(`Could not read ${f.name}: ${(e as Error).message}`, 'error')
      }
    }
  }, [addFrame, toast])
}

export function filesFromDataTransfer(dt: DataTransfer | null): File[] {
  if (!dt) return []
  const out: File[] = []
  if (dt.items) for (const it of Array.from(dt.items)) { if (it.kind === 'file') { const f = it.getAsFile(); if (f) out.push(f) } }
  else out.push(...Array.from(dt.files))
  return out
}
