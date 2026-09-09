import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { useState, type DragEvent } from 'react'
import type { Shot } from '../../types'
import { FrameImage } from '../FrameImage'
import { heroFrame } from '../../export/pdf'
import { useProject } from '../../store/useProject'
import { filesFromDataTransfer, useUpload } from '../../hooks/useUpload'
import { CAMERA_ANGLES, MOVEMENTS, SHOT_SIZES } from '../../taxonomy'

export function ShotCard({ shot, ratio, sceneNo }: { shot: Shot; ratio: number; sceneNo: string }) {
  const selected = useProject((s) => s.selectedShotId === shot.id)
  const selectShot = useProject((s) => s.selectShot)
  const removeShot = useProject((s) => s.removeShot)
  const duplicateShot = useProject((s) => s.duplicateShot)
  const setRightTab = useProject((s) => s.setRightTab)
  const upload = useUpload()
  const [over, setOver] = useState(false)
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: shot.id })
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 }
  const hero = heroFrame(shot)
  const size = SHOT_SIZES.find((s) => s.value === shot.shotSize)
  const move = MOVEMENTS.find((m) => m.value === shot.movement)
  const angle = CAMERA_ANGLES.find((a) => a.value === shot.cameraAngle)

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setOver(false)
    void upload(shot.id, filesFromDataTransfer(e.dataTransfer))
  }

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}
      onClick={() => selectShot(shot.id)}
      onDragOver={(e) => { if (e.dataTransfer.types.includes('Files')) { e.preventDefault(); setOver(true) } }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
      className={`group relative rounded-md border bg-panel overflow-hidden cursor-grab active:cursor-grabbing select-none transition-colors ${selected ? 'border-accent shadow-[0_0_0_1px_var(--color-accent)]' : 'border-line hover:border-mute/60'} ${over ? 'ring-2 ring-accent-2' : ''}`}>
      <FrameImage frame={hero} ratio={ratio} />
      <div className="absolute top-1.5 left-1.5 bg-accent text-ink text-[10px] font-bold px-1.5 py-0.5 rounded">{sceneNo}.{shot.shotNo}</div>
      {shot.frames.length > 1 && <div className="absolute top-1.5 right-1.5 chip bg-black/60">{shot.frames.length} frames</div>}
      {hero?.kind === 'reference' && <div className="absolute bottom-[calc(100%-100%)] right-1.5 chip bg-black/60" style={{ bottom: 'auto', top: shot.frames.length > 1 ? 24 : 6 }}>ref</div>}
      <div className="p-2 space-y-1">
        <div className="flex flex-wrap gap-1">
          <span className="chip text-text border-accent/40">{size?.label ?? shot.shotSize}</span>
          {angle && angle.value !== 'eye-level' && <span className="chip">{angle.label}</span>}
          {move && <span className="chip">{move.label.split(' ')[0]}</span>}
          {shot.lensMm && <span className="chip">{shot.lensMm}mm</span>}
        </div>
        <div className="text-[11px] leading-snug text-text/90 line-clamp-2 min-h-[2.4em]">{shot.subject || shot.action || <span className="text-mute">Untitled shot</span>}</div>
        {shot.dialogue && <div className="text-[11px] text-mute italic line-clamp-1">“{shot.dialogue}”</div>}
      </div>
      <div className="absolute inset-x-0 bottom-0 translate-y-full group-hover:translate-y-0 transition-transform flex justify-end gap-1 p-1 bg-gradient-to-t from-black/80 to-transparent"
        onPointerDown={(e) => e.stopPropagation()}>
        <button className="btn btn-ghost !px-2 !py-0.5 text-[11px]" title="Generate a frame" onClick={(e) => { e.stopPropagation(); selectShot(shot.id); setRightTab('generate') }}>✦ gen</button>
        <button className="btn btn-ghost !px-2 !py-0.5 text-[11px]" title="Find references" onClick={(e) => { e.stopPropagation(); selectShot(shot.id); setRightTab('refs') }}>⌕ refs</button>
        <button className="btn btn-ghost !px-2 !py-0.5 text-[11px]" title="Duplicate" onClick={(e) => { e.stopPropagation(); duplicateShot(shot.id) }}>⧉</button>
        <button className="btn btn-ghost !px-2 !py-0.5 text-[11px] text-danger" title="Delete shot" onClick={(e) => { e.stopPropagation(); if (confirm('Delete this shot?')) removeShot(shot.id) }}>✕</button>
      </div>
    </div>
  )
}
