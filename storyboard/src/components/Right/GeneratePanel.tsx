import { useMemo, useState } from 'react'
import { generateApi } from '../../api/generate'
import { useCurrentScene, useCurrentShot, useDirector, useProject } from '../../store/useProject'
import { buildPrompt } from '../../lib/prompt'
import { PROVIDERS } from '../../taxonomy'
import { base64ToBlob, blobToDataUrl, resizeImage } from '../../lib/image'
import { getImageBlob, putImage } from '../../store/db'
import { uid } from '../../lib/id'
import { Empty, Field, Spinner } from '../ui'
import type { Frame, ProviderId } from '../../types'
import { FrameImage } from '../FrameImage'

export function GeneratePanel() {
  const shot = useCurrentShot()
  const scene = useCurrentScene()
  const director = useDirector()
  const project = useProject((s) => s.project)!
  const providers = useProject((s) => s.providers)
  const setSettings = useProject((s) => s.setSettings)
  const addFrame = useProject((s) => s.addFrame)
  const toast = useProject((s) => s.toast)
  const [prompt, setPrompt] = useState('')
  const [seed, setSeed] = useState<string>('')
  const [refs, setRefs] = useState<string[]>([])
  const [extraRef, setExtraRef] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [count, setCount] = useState(1)
  const [lastShotId, setLastShotId] = useState<string | null>(null)
  const provider = project.settings.provider
  const auto = useMemo(() => (shot ? buildPrompt(shot, director, scene, shot.aspectRatio ?? project.aspectRatio) : ''), [shot, director, scene, project.aspectRatio])

  // Adjust derived state when the selected shot changes (React "adjusting state during render" pattern).
  if (shot && shot.id !== lastShotId) { setLastShotId(shot.id); setPrompt(auto); setRefs([]) }

  if (!shot) return <Empty title="No shot selected">Select a shot, then generate a frame from its taxonomy and the director lens.</Empty>
  const supportsRefs = provider === 'gemini' || provider === 'openai'
  const localFrames = shot.frames.filter((f) => f.imageId)
  const allLocal: Frame[] = Object.values(project.shots).flatMap((s) => s.frames.filter((f) => f.imageId && f.kind === 'generated')).slice(-12)

  const toggleRef = (id: string) => setRefs((r) => (r.includes(id) ? r.filter((x) => x !== id) : [...r, id].slice(-3)))

  const run = async () => {
    if (!prompt.trim()) return
    setBusy('Preparing…')
    try {
      const referenceImages: string[] = []
      if (supportsRefs) {
        for (const id of refs) { const b = await getImageBlob(id); if (b) referenceImages.push(await blobToDataUrl(await resizeImage(b, 1024))) }
        if (extraRef) referenceImages.push(extraRef)
      }
      for (let i = 0; i < count; i++) {
        const s = seed ? Number(seed) + i : Math.floor(Math.random() * 1e9)
        setBusy(provider === 'pollinations' ? `Generating ${i + 1}/${count} on the free tier (can take 15 to 40 s)…` : `Generating ${i + 1}/${count}…`)
        const res = await generateApi.generate({ provider, prompt: prompt.trim(), aspect: shot.aspectRatio ?? project.aspectRatio, seed: s, referenceImages })
        const blob = base64ToBlob(res.pngBase64, res.mime)
        const id = uid('img')
        await putImage(id, blob)
        addFrame(shot.id, { kind: 'generated', imageId: id, prompt: prompt.trim(), provider: res.provider, seed: s }, i === 0)
      }
      toast(`Frame${count > 1 ? 's' : ''} added to shot ${shot.shotNo}.`)
    } catch (e) {
      toast((e as Error).message, 'error')
    } finally { setBusy(null) }
  }

  const onExtraRef = async (f: File | undefined) => {
    if (!f) return
    setExtraRef(await blobToDataUrl(await resizeImage(f, 1024)))
  }

  return (
    <div className="p-3 space-y-3 text-xs">
      <Field label="Provider">
        <select className="field" value={provider} onChange={(e) => setSettings({ provider: e.target.value as ProviderId })}>
          {PROVIDERS.map((p) => <option key={p.value} value={p.value} disabled={providers ? !providers[p.value] : false}>{p.label}{providers && !providers[p.value] ? ' (not configured)' : ''} · {p.cost}</option>)}
        </select>
        <span className="block text-mute mt-1">{PROVIDERS.find((p) => p.value === provider)?.note}</span>
      </Field>

      <Field label="Prompt (built from the shot + director lens; edit freely)">
        <textarea className="field min-h-[150px] font-mono text-[11px] leading-snug" value={prompt} onChange={(e) => setPrompt(e.target.value)} />
        <div className="flex gap-1 mt-1">
          <button className="btn !py-0.5" onClick={() => setPrompt(auto)}>↻ Rebuild from shot</button>
          <span className="text-mute self-center">{director.name} · {shot.aspectRatio ?? project.aspectRatio}</span>
        </div>
      </Field>

      <div className="grid grid-cols-2 gap-2">
        <Field label="Seed (blank = random)"><input className="field" value={seed} onChange={(e) => setSeed(e.target.value.replace(/\D/g, ''))} placeholder="e.g. 42" /></Field>
        <Field label="Variations"><input className="field" type="number" min={1} max={4} value={count} onChange={(e) => setCount(Math.max(1, Math.min(4, Number(e.target.value) || 1)))} /></Field>
      </div>

      <div>
        <span className="label">Reference images for consistency {supportsRefs ? '' : '(needs Gemini or OpenAI)'}</span>
        <div className={`space-y-2 ${supportsRefs ? '' : 'opacity-50 pointer-events-none'}`}>
          {(localFrames.length > 0 || allLocal.length > 0) && (
            <div className="grid grid-cols-4 gap-1">
              {[...localFrames, ...allLocal.filter((f) => !localFrames.some((l) => l.id === f.id))].slice(0, 12).map((f) => (
                <button key={f.id} onClick={() => toggleRef(f.imageId!)} className={`rounded overflow-hidden border cursor-pointer ${refs.includes(f.imageId!) ? 'border-accent' : 'border-line'}`} title="Use as reference">
                  <FrameImage frame={f} ratio={16 / 9} />
                </button>
              ))}
            </div>
          )}
          <div className="flex items-center gap-2">
            <label className="btn !py-1 cursor-pointer">↑ Character sheet<input type="file" accept="image/*" hidden onChange={(e) => void onExtraRef(e.target.files?.[0])} /></label>
            {extraRef && <><img src={extraRef} alt="" className="h-8 rounded" /><button className="btn btn-ghost !py-0.5" onClick={() => setExtraRef(null)}>✕</button></>}
          </div>
        </div>
      </div>

      <button className="btn btn-primary w-full justify-center" onClick={() => void run()} disabled={!!busy || !prompt.trim()}>
        {busy ? <><Spinner /> {busy}</> : `✦ Generate ${count > 1 ? count + ' frames' : 'frame'}`}
      </button>
      <p className="text-mute leading-relaxed">Generated frames are saved in this browser (IndexedDB) and attached to the shot. The first one becomes the hero frame; switch in the Shot tab.</p>
    </div>
  )
}
