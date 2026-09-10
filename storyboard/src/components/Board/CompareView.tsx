import { useState } from 'react'
import type { Scene, Shot } from '../../types'
import { useLens, useProject } from '../../store/useProject'
import { resolveLens } from '../../lens'
import { FrameImage } from '../FrameImage'
import { heroFrame } from '../../export/pdf'
import { aspectToRatio, MOVEMENTS, SHOT_SIZES } from '../../taxonomy'

function lensLabel(directorId: string, dpId: string, p: { customDirector: string; customDp: string }): string {
  return resolveLens({ directorId, dpId, customDirector: p.customDirector, customDp: p.customDp }).name
}

function MiniShot({ shot, ratio, sceneNo, onCopy }: { shot: Shot; ratio: number; sceneNo: string; onCopy?: () => void }) {
  const size = SHOT_SIZES.find((s) => s.value === shot.shotSize)?.label ?? shot.shotSize
  const move = MOVEMENTS.find((m) => m.value === shot.movement)?.label.split(' ')[0] ?? shot.movement
  return (
    <div className="border border-line rounded bg-panel overflow-hidden">
      <div className="relative">
        <FrameImage frame={heroFrame(shot)} ratio={ratio} />
        <div className="absolute top-1 left-1 bg-accent text-ink text-[10px] font-bold px-1 rounded">{sceneNo}.{shot.shotNo}</div>
      </div>
      <div className="p-1.5 text-[11px] leading-snug">
        <div className="font-medium">{size} · {move} · {shot.lensMm ? `${shot.lensMm}mm ` : ''}{shot.lensCharacter}</div>
        <div className="text-mute line-clamp-2">{shot.subject || shot.action}</div>
        {shot.durationSec ? <div className="text-mute">{shot.durationSec}s</div> : null}
        {onCopy && <button className="btn btn-ghost !px-1.5 !py-0 mt-1" onClick={onCopy} title="Append a copy of this shot to the active list">＋ copy to active</button>}
      </div>
    </div>
  )
}

export function CompareView({ scene, onClose }: { scene: Scene; onClose: () => void }) {
  const project = useProject((s) => s.project)!
  const lens = useLens()
  const saveVariant = useProject((s) => s.saveVariant)
  const restoreVariant = useProject((s) => s.restoreVariant)
  const deleteVariant = useProject((s) => s.deleteVariant)
  const renameVariant = useProject((s) => s.renameVariant)
  const copyVariantShot = useProject((s) => s.copyVariantShot)
  const toast = useProject((s) => s.toast)
  const [label, setLabel] = useState('')
  const ratio = aspectToRatio(project.aspectRatio)
  const active = scene.shotIds.map((id) => project.shots[id]).filter(Boolean)
  const variants = scene.variants ?? []
  const total = (shots: Shot[]) => shots.reduce((n, s) => n + (s.durationSec ?? 0), 0)

  return (
    <div className="fixed inset-0 z-40 bg-black/70 flex flex-col" onClick={onClose}>
      <div className="m-4 flex-1 min-h-0 bg-ink border border-line rounded-lg flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="px-4 py-3 border-b border-line flex items-center gap-3">
          <div className="text-sm font-semibold">Compare lenses · Sc {scene.sceneNo} {scene.heading}</div>
          <div className="flex-1" />
          <input className="field !w-56 !py-1" value={label} onChange={(e) => setLabel(e.target.value)} placeholder={`Save active as… (${lens.name})`} />
          <button className="btn !py-1" disabled={!active.length} onClick={() => { saveVariant(scene.id, label || undefined); setLabel(''); toast('Saved the active list as a variant.') }}>💾 Save variant</button>
          <button className="btn btn-ghost" onClick={onClose}>✕</button>
        </div>
        <div className="flex-1 min-h-0 overflow-auto p-4">
          {variants.length === 0 && (
            <div className="text-mute text-xs mb-3 max-w-2xl leading-relaxed">
              No variants yet. Change the director or cinematographer on the left and press <b>Re-direct current scene</b>: the current list is kept here automatically, so you can compare Villeneuve against Kashyap, or the same director with two different DPs, side by side.
            </div>
          )}
          <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${1 + variants.length}, minmax(260px, 1fr))` }}>
            <div>
              <div className="sticky top-0 bg-ink pb-2">
                <div className="text-[11px] uppercase tracking-wide text-accent">Active</div>
                <div className="font-semibold text-sm">{scene.activeLens?.label ?? lens.name}</div>
                <div className="text-mute text-[11px]">{active.length} shots · ~{total(active)}s</div>
              </div>
              <div className="space-y-2">{active.map((s) => <MiniShot key={s.id} shot={s} ratio={ratio} sceneNo={scene.sceneNo} />)}</div>
            </div>
            {variants.map((v) => (
              <div key={v.id}>
                <div className="sticky top-0 bg-ink pb-2">
                  <div className="text-[11px] uppercase tracking-wide text-mute">Variant</div>
                  <input className="bg-transparent outline-none font-semibold text-sm w-full" value={v.label} onChange={(e) => renameVariant(scene.id, v.id, e.target.value)} />
                  <div className="text-mute text-[11px] truncate" title={lensLabel(v.directorId, v.dpId, project)}>{lensLabel(v.directorId, v.dpId, project)} · {v.shots.length} shots · ~{total(v.shots)}s</div>
                  <div className="flex gap-1 mt-1">
                    <button className="btn btn-primary !py-0.5" onClick={() => { restoreVariant(scene.id, v.id); toast(`"${v.label}" is now the active list; the previous one was parked as a variant.`) }}>Make active</button>
                    <button className="btn btn-ghost !py-0.5 text-danger" onClick={() => { if (confirm(`Delete variant "${v.label}"?`)) deleteVariant(scene.id, v.id) }}>Delete</button>
                  </div>
                </div>
                <div className="space-y-2">{v.shots.map((s) => <MiniShot key={s.id} shot={s} ratio={ratio} sceneNo={scene.sceneNo} onCopy={() => copyVariantShot(scene.id, v.id, s.id)} />)}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
