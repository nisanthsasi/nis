import { ALL_DIRECTORS } from '../../directors'
import { useCurrentScene, useDirector, useProject } from '../../store/useProject'
import { parseScreenplay, textToLines } from '../../lib/screenplay'
import { generateShotList } from '../../lib/shotlist'

export function DirectorPanel() {
  const project = useProject((s) => s.project)!
  const director = useDirector()
  const scene = useCurrentScene()
  const setDirector = useProject((s) => s.setDirector)
  const addShotsFromDrafts = useProject((s) => s.addShotsFromDrafts)
  const toast = useProject((s) => s.toast)

  const redirect = () => {
    if (!scene) return
    const text = scene.scriptText?.trim() ? scene.scriptText : `${scene.heading}\n\n${scene.synopsis || ''}`
    const ps = parseScreenplay(textToLines(text))[0]
    if (!ps) { toast('This scene has no script text or synopsis.', 'error'); return }
    if (scene.shotIds.length && !confirm(`Re-direct "${scene.heading}" in the ${director.name} lens? This replaces its ${scene.shotIds.length} shots.`)) return
    const drafts = generateShotList(ps, director)
    addShotsFromDrafts(scene.id, drafts, true)
    toast(`Scene re-directed: ${drafts.length} shots.`)
  }

  return (
    <div className="flex flex-col h-full text-xs">
      <div className="p-3 border-b border-line">
        <div className="text-[11px] uppercase tracking-wide text-mute">Directing in</div>
        <div className="text-sm font-semibold">{director.name}</div>
        <div className="text-mute mt-1 leading-relaxed">{director.summary}</div>
        <div className="flex flex-wrap gap-1 mt-2">
          <span className="chip">{director.coverageStyle}</span><span className="chip">{director.lensCharacter} {director.lensRange[0]}–{director.lensRange[1]}mm</span>
          <span className="chip">{director.lightingKey}</span><span className="chip">{director.aspectRatio}</span><span className="chip">{director.pacing}</span>
        </div>
        <div className="flex gap-1 mt-1">{director.palette.map((c) => <span key={c} className="w-5 h-3 rounded-sm border border-line" style={{ background: c }} />)}</div>
        {scene && <button className="btn w-full justify-center mt-3" onClick={redirect}>🎬 Re-direct current scene in this lens</button>}
      </div>
      {project.directorId === 'custom' && (
        <div className="p-3 border-b border-line">
          <span className="label">Your grammar</span>
          <textarea className="field min-h-[90px]" value={project.customDirector} onChange={(e) => setDirector('custom', e.target.value)}
            placeholder="e.g. Long takes, handheld, 32mm on everything, sodium street light, teal-orange, slow pacing, 2.39 scope" />
          <div className="text-mute mt-1">Words like long take, handheld, anamorphic, low key, neon, golden, slow, 4:3 are picked up automatically; the rest becomes style vocabulary for image prompts.</div>
        </div>
      )}
      <div className="flex-1 overflow-auto">
        {ALL_DIRECTORS.map((d) => (
          <button key={d.id} onClick={() => setDirector(d.id)}
            className={`block w-full text-left px-3 py-2 border-b border-line/60 cursor-pointer ${project.directorId === d.id ? 'bg-panel-2 border-l-2 border-l-accent' : 'hover:bg-panel-2/50'}`}>
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-medium">{d.name}</span>
              <span className="text-mute text-[10px] whitespace-nowrap">{d.region}</span>
            </div>
            <div className="text-mute line-clamp-2 leading-snug mt-0.5">{d.summary}</div>
            <div className="flex gap-1 mt-1 flex-wrap">
              <span className="chip !text-[9px]">{d.coverageStyle}</span><span className="chip !text-[9px]">{d.lensCharacter}</span><span className="chip !text-[9px]">{d.aspectRatio}</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
