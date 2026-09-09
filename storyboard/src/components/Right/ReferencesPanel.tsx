import { useState } from 'react'
import { framesApi, type FTFrame } from '../../api/frames'
import { ApiError } from '../../api/client'
import { useCurrentScene, useCurrentShot, useDirector, useProject } from '../../store/useProject'
import { buildReferenceQuery } from '../../lib/prompt'
import { mapCameraAngle, mapLensCharacter, mapLightingKey, mapShotType, mapTimeOfDay, SHOT_SIZES } from '../../taxonomy'
import { Empty, Spinner } from '../ui'

type Mode = 'search' | 'lens' | 'similar'

export function ReferencesPanel() {
  const shot = useCurrentShot()
  const scene = useCurrentScene()
  const director = useDirector()
  const providers = useProject((s) => s.providers)
  const addFrame = useProject((s) => s.addFrame)
  const updateShot = useProject((s) => s.updateShot)
  const toast = useProject((s) => s.toast)
  const [q, setQ] = useState('')
  const [mode, setMode] = useState<Mode>('search')
  const [results, setResults] = useState<FTFrame[]>([])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<{ text: string; link?: string } | null>(null)
  const [lastShotId, setLastShotId] = useState<string | null>(null)

  // Adjust derived state when the selected shot changes (React "adjusting state during render" pattern).
  if (shot && shot.id !== lastShotId) {
    setLastShotId(shot.id)
    setQ(buildReferenceQuery(shot, scene))
  }

  if (!providers?.framethrower) {
    return (
      <Empty title="Reference library not connected">
        Reference stills come from <b>FrameThrower</b>, a searchable film-still library with an API (ShotDeck itself has no API and forbids scraping).<br /><br />
        1. Sign up free at framethrower.ai (no card, $2 of credits = ~1000 searches).<br />
        2. Settings → API → Create token.<br />
        3. Put it in <code>storyboard/.env</code> as <code>FRAMETHROWER_TOKEN</code> and restart <code>npm run dev</code>.
      </Empty>
    )
  }

  const run = async (fn: () => Promise<FTFrame[]>) => {
    setBusy(true); setErr(null)
    try { setResults(await fn()) } catch (e) {
      if (e instanceof ApiError) setErr({ text: e.message, link: typeof e.body.buy_credits === 'string' ? e.body.buy_credits : undefined })
      else setErr({ text: (e as Error).message })
    } finally { setBusy(false) }
  }

  const search = () => { if (q.trim()) void run(() => framesApi.search(q.trim())) }
  const browseLens = () => void run(() => framesApi.browse({
    director: director.frameThrowerDirector,
    shot_type: shot ? SHOT_SIZES.find((s) => s.value === shot.shotSize)?.label.toLowerCase() : undefined,
    time_of_day: shot && shot.timeOfDay !== 'unspecified' ? shot.timeOfDay.replace('-', ' ') : undefined,
    limit: 24,
  }))
  const similar = (id: string) => { setMode('similar'); void run(() => framesApi.similar(id, 'visual')) }

  const attach = (f: FTFrame) => {
    if (!shot) { toast('Select a shot first.', 'error'); return }
    addFrame(shot.id, {
      kind: 'reference', url: f.imageUrl, thumbUrl: f.thumbUrl, sourceId: f.id,
      credit: { film: f.film.title, year: f.film.year, director: f.film.director, dp: f.film.dp, deepLink: f.deepLink },
    }, shot.frames.length === 0)
    toast(`Added ${f.film.title ?? 'frame'} as a reference.`)
  }

  const copyMeta = (f: FTFrame) => {
    if (!shot) return
    const m = f.metadata
    const patch: Partial<typeof shot> = {}
    const size = mapShotType(m.shotType); if (size) patch.shotSize = size
    const ang = mapCameraAngle(m.cameraAngle); if (ang) patch.cameraAngle = ang
    const lens = mapLensCharacter(m.lensCharacter); if (lens) patch.lensCharacter = lens
    const lk = mapLightingKey(m.lightingKey || m.lightingDescription); if (lk) patch.lightingKey = lk
    const tod = mapTimeOfDay(m.timeOfDay); if (tod) patch.timeOfDay = tod
    if (m.moods?.length) patch.colorTags = [...new Set([...shot.colorTags, ...m.moods.slice(0, 3).map((x) => x.toLowerCase())])]
    if (!shot.notes && m.lightingDescription) patch.notes = m.lightingDescription
    updateShot(shot.id, patch)
    toast('Copied the frame\'s shot metadata onto this shot.')
  }

  return (
    <div className="flex flex-col h-full text-xs">
      <div className="p-3 space-y-2 border-b border-line">
        <div className="flex gap-1">
          <input className="field" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && search()} placeholder="neon-lit rainy street at night" />
          <button className="btn btn-primary" onClick={() => { setMode('search'); search() }} disabled={busy}>{busy && mode === 'search' ? <Spinner /> : 'Search'}</button>
        </div>
        <div className="flex gap-1 flex-wrap">
          {shot && <button className="btn !py-1" onClick={() => setQ(buildReferenceQuery(shot, scene))}>↻ From shot</button>}
          {director.frameThrowerDirector && <button className="btn !py-1" onClick={() => { setMode('lens'); browseLens() }} disabled={busy} title={`Browse ${director.name}'s frames matching this shot size`}>🎬 {director.name.split(' ').slice(-1)[0]}'s frames</button>}
          <button className="btn !py-1" onClick={() => void run(() => framesApi.random(24))} disabled={busy}>🎲 Random</button>
        </div>
        {err && <div className="text-danger">{err.text} {err.link && <a className="underline" href={err.link} target="_blank" rel="noreferrer">Buy credits</a>}</div>}
      </div>
      <div className="flex-1 overflow-auto p-3">
        {results.length === 0 && !busy && <div className="text-mute text-center pt-6">Search in plain language, or pull frames from the director lens. Click a frame to attach it to the selected shot.</div>}
        <div className="grid grid-cols-2 gap-2">
          {results.map((f) => (
            <div key={f.id} className="group rounded overflow-hidden border border-line bg-panel">
              <button className="block w-full cursor-pointer" onClick={() => attach(f)} title="Attach to shot">
                <div className="bg-black" style={{ aspectRatio: '16/9' }}><img src={f.thumbUrl || f.imageUrl} alt="" className="w-full h-full object-cover" loading="lazy" /></div>
              </button>
              <div className="p-1.5">
                <div className="truncate font-medium" title={f.film.title ?? ''}>{f.film.title}{f.film.year ? ` (${f.film.year})` : ''}</div>
                <div className="truncate text-mute">{[f.film.director, f.film.dp && `DP ${f.film.dp}`].filter(Boolean).join(' · ')}</div>
                <div className="truncate text-mute">{[f.metadata.shotType, f.metadata.lensCharacter, f.metadata.lightingKey].filter(Boolean).join(' · ')}</div>
                <div className="flex gap-1 mt-1 opacity-70 group-hover:opacity-100">
                  <button className="btn btn-ghost !px-1.5 !py-0.5" onClick={() => copyMeta(f)} title="Copy shot size, lens, light, time onto the selected shot">⇩ meta</button>
                  <button className="btn btn-ghost !px-1.5 !py-0.5" onClick={() => similar(f.id)}>≈ similar</button>
                  <a className="btn btn-ghost !px-1.5 !py-0.5" href={f.deepLink} target="_blank" rel="noreferrer">↗</a>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
