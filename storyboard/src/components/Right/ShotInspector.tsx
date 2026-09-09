import { useRef } from 'react'
import { useCurrentScene, useCurrentShot, useProject } from '../../store/useProject'
import { ASPECT_RATIOS, CAMERA_ANGLES, COLOR_TAGS, LENS_CHARACTERS, LIGHTING_KEYS, LIGHTING_QUALITIES, MOVEMENTS, SHOT_SIZES, TIMES_OF_DAY, aspectToRatio } from '../../taxonomy'
import { Empty, Field, Select } from '../ui'
import { FrameImage } from '../FrameImage'
import { useUpload } from '../../hooks/useUpload'
import type { AspectRatio } from '../../types'

export function ShotInspector() {
  const shot = useCurrentShot()
  const scene = useCurrentScene()
  const project = useProject((s) => s.project)!
  const updateShot = useProject((s) => s.updateShot)
  const setHero = useProject((s) => s.setHero)
  const removeFrame = useProject((s) => s.removeFrame)
  const setRightTab = useProject((s) => s.setRightTab)
  const upload = useUpload()
  const fileRef = useRef<HTMLInputElement>(null)

  if (!shot || !scene) return <Empty title="No shot selected">Click a shot on the board to edit its taxonomy, frames and notes.</Empty>
  const ratio = aspectToRatio(shot.aspectRatio ?? project.aspectRatio)
  const up = (patch: Parameters<typeof updateShot>[1]) => updateShot(shot.id, patch)
  const toggleTag = (t: string) => up({ colorTags: shot.colorTags.includes(t) ? shot.colorTags.filter((x) => x !== t) : [...shot.colorTags, t] })

  return (
    <div className="p-3 space-y-4 text-xs">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold">Shot {scene.sceneNo}.{shot.shotNo}</div>
        <div className="flex gap-1">
          <button className="btn !py-1" onClick={() => setRightTab('refs')}>⌕ References</button>
          <button className="btn btn-primary !py-1" onClick={() => setRightTab('generate')}>✦ Generate</button>
        </div>
      </div>

      {/* Frames */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="label !mb-0">Frames ({shot.frames.length})</span>
          <button className="btn btn-ghost !py-0.5 !px-2" onClick={() => fileRef.current?.click()}>↑ Upload</button>
          <input ref={fileRef} type="file" accept="image/*" multiple hidden onChange={(e) => { void upload(shot.id, e.target.files); e.target.value = '' }} />
        </div>
        {shot.frames.length === 0 ? (
          <div className="border border-dashed border-line rounded p-3 text-mute text-center">No frames yet. Upload, find a reference, or generate one.</div>
        ) : (
          <div className="grid grid-cols-3 gap-1.5">
            {shot.frames.map((f) => (
              <div key={f.id} className={`relative rounded overflow-hidden border ${f.id === shot.heroFrameId ? 'border-accent' : 'border-line'}`}>
                <button className="block w-full cursor-pointer" onClick={() => setHero(shot.id, f.id)} title="Make hero frame">
                  <FrameImage frame={f} ratio={ratio} />
                </button>
                <span className="absolute top-0.5 left-0.5 chip bg-black/70 !text-[9px]">{f.kind === 'reference' ? 'ref' : f.kind === 'generated' ? f.provider ?? 'gen' : 'up'}</span>
                <button className="absolute top-0.5 right-0.5 bg-black/70 text-danger rounded px-1 text-[10px] cursor-pointer" onClick={() => removeFrame(shot.id, f.id)} title="Remove">✕</button>
                {f.credit?.film && <div className="absolute bottom-0 inset-x-0 bg-black/70 text-[9px] px-1 truncate" title={`${f.credit.film} (${f.credit.year ?? ''}) ${f.credit.dp ? 'DP ' + f.credit.dp : ''}`}>{f.credit.film}{f.credit.year ? ` (${f.credit.year})` : ''}</div>}
              </div>
            ))}
          </div>
        )}
      </div>

      <Field label="Subject / blocking"><input className="field" value={shot.subject} onChange={(e) => up({ subject: e.target.value })} placeholder="MEERA at the sink, back to camera" /></Field>
      <Field label="Action"><textarea className="field min-h-[56px]" value={shot.action} onChange={(e) => up({ action: e.target.value })} /></Field>
      <Field label="Dialogue"><textarea className="field min-h-[44px]" value={shot.dialogue} onChange={(e) => up({ dialogue: e.target.value })} placeholder="RAVI: Are you going to answer that?" /></Field>

      <div className="grid grid-cols-2 gap-2">
        <Field label="Shot size"><Select value={shot.shotSize} options={SHOT_SIZES} onChange={(v) => up({ shotSize: v })} /></Field>
        <Field label="Angle"><Select value={shot.cameraAngle} options={CAMERA_ANGLES} onChange={(v) => up({ cameraAngle: v })} /></Field>
        <Field label="Movement"><Select value={shot.movement} options={MOVEMENTS} onChange={(v) => up({ movement: v })} /></Field>
        <Field label="Lens">
          <div className="flex gap-1">
            <input className="field !w-16" type="number" min={8} max={400} value={shot.lensMm ?? ''} onChange={(e) => up({ lensMm: e.target.value ? Number(e.target.value) : null })} placeholder="mm" />
            <Select value={shot.lensCharacter} options={LENS_CHARACTERS} onChange={(v) => up({ lensCharacter: v })} />
          </div>
        </Field>
        <Field label="Lighting key"><Select value={shot.lightingKey} options={LIGHTING_KEYS} onChange={(v) => up({ lightingKey: v })} /></Field>
        <Field label="Light quality"><Select value={shot.lightingQuality} options={LIGHTING_QUALITIES} onChange={(v) => up({ lightingQuality: v })} /></Field>
        <Field label="Time of day"><Select value={shot.timeOfDay} options={TIMES_OF_DAY} onChange={(v) => up({ timeOfDay: v })} /></Field>
        <Field label="Duration (s)"><input className="field" type="number" min={0} value={shot.durationSec ?? ''} onChange={(e) => up({ durationSec: e.target.value ? Number(e.target.value) : null })} /></Field>
        <Field label="Aspect">
          <Select<AspectRatio | 'inherit'> value={shot.aspectRatio ?? 'inherit'} options={[{ value: 'inherit', label: `Project (${project.aspectRatio})` }, ...ASPECT_RATIOS]} onChange={(v) => up({ aspectRatio: v === 'inherit' ? null : v })} />
        </Field>
      </div>

      <div>
        <span className="label">Colour / mood tags</span>
        <div className="flex flex-wrap gap-1">
          {COLOR_TAGS.map((t) => (
            <button key={t} onClick={() => toggleTag(t)} className={`chip cursor-pointer ${shot.colorTags.includes(t) ? '!text-ink !bg-accent !border-accent' : 'hover:text-text'}`}>{t}</button>
          ))}
        </div>
      </div>

      <Field label="Notes for DP / artist"><textarea className="field min-h-[56px]" value={shot.notes} onChange={(e) => up({ notes: e.target.value })} /></Field>
    </div>
  )
}
