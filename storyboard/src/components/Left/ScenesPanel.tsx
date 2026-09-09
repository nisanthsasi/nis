import { useProject } from '../../store/useProject'

export function ScenesPanel() {
  const project = useProject((s) => s.project)!
  const selectedSceneId = useProject((s) => s.selectedSceneId)
  const selectScene = useProject((s) => s.selectScene)
  const addScene = useProject((s) => s.addScene)
  const removeScene = useProject((s) => s.removeScene)
  const moveScene = useProject((s) => s.moveScene)
  const updateScene = useProject((s) => s.updateScene)

  return (
    <div className="flex flex-col h-full">
      <div className="p-2 border-b border-line flex items-center justify-between">
        <span className="text-mute text-[11px] uppercase tracking-wide">{project.scenes.length} scenes · {Object.keys(project.shots).length} shots</span>
        <button className="btn !py-1" onClick={() => addScene()}>＋ Scene</button>
      </div>
      <div className="flex-1 overflow-auto">
        {project.scenes.map((sc, i) => (
          <div key={sc.id} onClick={() => selectScene(sc.id)}
            className={`group px-3 py-2 border-b border-line/60 cursor-pointer ${sc.id === selectedSceneId ? 'bg-panel-2' : 'hover:bg-panel-2/50'}`}>
            <div className="flex items-start gap-2">
              <input className="w-8 bg-transparent text-mute text-[11px] outline-none shrink-0 mt-0.5" value={sc.sceneNo} onClick={(e) => e.stopPropagation()} onChange={(e) => updateScene(sc.id, { sceneNo: e.target.value })} />
              <div className="flex-1 min-w-0">
                <div className="text-xs font-medium truncate">{sc.heading || 'Untitled scene'}</div>
                <div className="text-[11px] text-mute truncate">{sc.shotIds.length} shots{sc.characters.length ? ` · ${sc.characters.slice(0, 3).join(', ')}` : ''}</div>
              </div>
              <div className="opacity-0 group-hover:opacity-100 flex gap-0.5 shrink-0" onClick={(e) => e.stopPropagation()}>
                <button className="btn btn-ghost !px-1 !py-0" disabled={i === 0} onClick={() => moveScene(i, i - 1)}>↑</button>
                <button className="btn btn-ghost !px-1 !py-0" disabled={i === project.scenes.length - 1} onClick={() => moveScene(i, i + 1)}>↓</button>
                <button className="btn btn-ghost !px-1 !py-0 text-danger" onClick={() => { if (confirm(`Delete scene "${sc.heading}" and its ${sc.shotIds.length} shots?`)) removeScene(sc.id) }}>✕</button>
              </div>
            </div>
          </div>
        ))}
      </div>
      {selectedSceneId && <SceneMeta id={selectedSceneId} />}
    </div>
  )
}

function SceneMeta({ id }: { id: string }) {
  const scene = useProject((s) => s.project?.scenes.find((x) => x.id === id))
  const updateScene = useProject((s) => s.updateScene)
  if (!scene) return null
  return (
    <div className="border-t border-line p-3 space-y-2 text-xs">
      <div className="grid grid-cols-3 gap-1">
        <select className="field" value={scene.intExt} onChange={(e) => updateScene(id, { intExt: e.target.value as typeof scene.intExt })}>
          <option value="">—</option><option>INT</option><option>EXT</option><option>INT/EXT</option>
        </select>
        <input className="field col-span-2" value={scene.location} onChange={(e) => updateScene(id, { location: e.target.value })} placeholder="Location" />
      </div>
      <input className="field" value={scene.timeLabel} onChange={(e) => updateScene(id, { timeLabel: e.target.value })} placeholder="DAY / NIGHT / DUSK" />
      <textarea className="field min-h-[60px]" value={scene.synopsis} onChange={(e) => updateScene(id, { synopsis: e.target.value })} placeholder="Synopsis (used for the auto shot list when there is no script text)" />
      <details>
        <summary className="text-mute cursor-pointer">Script text ({scene.scriptText ? scene.scriptText.split('\n').length + ' lines' : 'none'})</summary>
        <textarea className="field min-h-[160px] font-mono text-[11px] mt-1" value={scene.scriptText} onChange={(e) => updateScene(id, { scriptText: e.target.value })} placeholder={'INT. KITCHEN - NIGHT\n\nAction line.\n\nMEERA\nDialogue.'} />
      </details>
    </div>
  )
}
