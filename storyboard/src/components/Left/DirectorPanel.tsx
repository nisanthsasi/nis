import { useState } from 'react'
import { ALL_DIRECTORS } from '../../directors'
import { ALL_CINEMATOGRAPHERS } from '../../cinematographers'
import { useCurrentScene, useLens, useProject } from '../../store/useProject'
import { parseScreenplay, textToLines } from '../../lib/screenplay'
import { generateShotList } from '../../lib/shotlist'
import { Tabs } from '../ui'

type Sub = 'director' | 'dp'

export function DirectorPanel() {
  const project = useProject((s) => s.project)!
  const lens = useLens()
  const scene = useCurrentScene()
  const setDirector = useProject((s) => s.setDirector)
  const setDp = useProject((s) => s.setDp)
  const redirectScene = useProject((s) => s.redirectScene)
  const toast = useProject((s) => s.toast)
  const [sub, setSub] = useState<Sub>('director')

  const redirect = () => {
    if (!scene) return
    const text = scene.scriptText?.trim() ? scene.scriptText : `${scene.heading}\n\n${scene.synopsis || ''}`
    const ps = parseScreenplay(textToLines(text))[0]
    if (!ps) { toast('This scene has no script text or synopsis.', 'error'); return }
    const drafts = generateShotList(ps, lens)
    redirectScene(scene.id, drafts)
    toast(scene.shotIds.length ? `Re-directed as ${lens.name}. The previous list is saved as a variant.` : `Scene directed as ${lens.name}: ${drafts.length} shots.`)
  }

  const dpIsUsual = project.dpId === 'same'

  return (
    <div className="flex flex-col h-full text-xs">
      <div className="p-3 border-b border-line">
        <div className="text-[11px] uppercase tracking-wide text-mute">Directing as</div>
        <div className="text-sm font-semibold">{lens.directorName}</div>
        <div className="text-[11px] uppercase tracking-wide text-mute mt-1.5">Shot by</div>
        <div className="text-sm font-semibold">{lens.dpName}{dpIsUsual && lens.dp.id !== 'same' ? <span className="text-mute font-normal"> (usual)</span> : null}</div>
        <div className="flex flex-wrap gap-1 mt-2">
          <span className="chip">{lens.coverageStyle}</span>
          <span className="chip">{lens.format}</span>
          <span className="chip">{lens.lensLadder ? `${lens.lensLadder.wide} / ${lens.lensLadder.normal} / ${lens.lensLadder.long}mm` : `${lens.lensRange[0]}–${lens.lensRange[1]}mm`}</span>
          <span className="chip">{lens.lightingKey}</span><span className="chip">{lens.aspectRatio}</span><span className="chip">{lens.pacing}</span>
        </div>
        <div className="flex gap-1 mt-1">{lens.palette.map((c) => <span key={c} className="w-5 h-3 rounded-sm border border-line" style={{ background: c }} />)}</div>
        {scene && <button className="btn w-full justify-center mt-3" onClick={redirect} title="Rebuild this scene's shot list in the current lens. The current list is kept as a variant.">🎬 Re-direct current scene</button>}
      </div>

      <Tabs value={sub} onChange={setSub} tabs={[{ value: 'director', label: 'Director' }, { value: 'dp', label: 'Cinematographer' }]} />

      {sub === 'director' && project.directorId === 'custom' && (
        <div className="p-3 border-b border-line">
          <span className="label">Your directing grammar</span>
          <textarea className="field min-h-[80px]" value={project.customDirector} onChange={(e) => setDirector('custom', e.target.value)}
            placeholder="e.g. Long takes, observational, wide masters, cut only on a look, slow pacing" />
        </div>
      )}
      {sub === 'dp' && project.dpId === 'custom' && (
        <div className="p-3 border-b border-line">
          <span className="label">Your lensing</span>
          <textarea className="field min-h-[80px]" value={project.customDp} onChange={(e) => setDp('custom', e.target.value)}
            placeholder="e.g. Alexa 65, 24mm 40mm 75mm, anamorphic, low key practicals, teal-orange, handheld, shallow focus" />
          <div className="text-mute mt-1">Focal lengths, anamorphic, handheld, low key, neon, golden and palette words are picked up; the rest becomes prompt vocabulary.</div>
        </div>
      )}

      <div className="flex-1 overflow-auto">
        {sub === 'director' && ALL_DIRECTORS.map((d) => (
          <button key={d.id} onClick={() => setDirector(d.id)}
            className={`block w-full text-left px-3 py-2 border-b border-line/60 cursor-pointer ${project.directorId === d.id ? 'bg-panel-2 border-l-2 border-l-accent' : 'hover:bg-panel-2/50'}`}>
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-medium">{d.name}</span>
              <span className="text-mute text-[10px] whitespace-nowrap">{d.region}</span>
            </div>
            <div className="text-mute line-clamp-2 leading-snug mt-0.5">{d.summary}</div>
            <div className="flex gap-1 mt-1 flex-wrap">
              <span className="chip !text-[9px]">{d.coverageStyle}</span><span className="chip !text-[9px]">{d.pacing}</span>
              {d.defaultDpId && <span className="chip !text-[9px]">DP: {ALL_CINEMATOGRAPHERS.find((c) => c.id === d.defaultDpId)?.name.split(' (')[0]}</span>}
            </div>
          </button>
        ))}
        {sub === 'dp' && ALL_CINEMATOGRAPHERS.map((c) => (
          <button key={c.id} onClick={() => setDp(c.id)}
            className={`block w-full text-left px-3 py-2 border-b border-line/60 cursor-pointer ${project.dpId === c.id ? 'bg-panel-2 border-l-2 border-l-accent' : 'hover:bg-panel-2/50'}`}>
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-medium">{c.name}</span>
              <span className="text-mute text-[10px] whitespace-nowrap">{c.region}</span>
            </div>
            <div className="text-mute line-clamp-2 leading-snug mt-0.5">{c.summary}</div>
            <div className="flex gap-1 mt-1 flex-wrap">
              <span className="chip !text-[9px]">{c.format}</span>
              <span className="chip !text-[9px]">{c.lensLadder.wide}/{c.lensLadder.normal}/{c.lensLadder.long}mm</span>
              <span className="chip !text-[9px]">{c.lightingKey}</span><span className="chip !text-[9px]">{c.camera}</span>
            </div>
            {c.knownFor.length > 0 && <div className="text-mute text-[10px] mt-1 truncate">{c.knownFor.slice(0, 4).join(' · ')}</div>}
          </button>
        ))}
      </div>
    </div>
  )
}
