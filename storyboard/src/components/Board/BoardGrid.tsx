import { DndContext, PointerSensor, closestCenter, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core'
import { SortableContext, rectSortingStrategy } from '@dnd-kit/sortable'
import { useState } from 'react'
import { useCurrentScene, useDirector, useProject } from '../../store/useProject'
import { aspectToRatio } from '../../taxonomy'
import { ShotCard } from './ShotCard'
import { Empty, Spinner } from '../ui'
import { parseScreenplay, textToLines } from '../../lib/screenplay'
import { generateShotList } from '../../lib/shotlist'
import { claudeShotList } from '../../api/shotlist'

export function BoardGrid() {
  const project = useProject((s) => s.project)!
  const scene = useCurrentScene()
  const director = useDirector()
  const moveShot = useProject((s) => s.moveShot)
  const addShot = useProject((s) => s.addShot)
  const updateScene = useProject((s) => s.updateScene)
  const addShotsFromDrafts = useProject((s) => s.addShotsFromDrafts)
  const selectShot = useProject((s) => s.selectShot)
  const providers = useProject((s) => s.providers)
  const toast = useProject((s) => s.toast)
  const [busy, setBusy] = useState<string | null>(null)
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }))
  const ratio = aspectToRatio(project.aspectRatio)

  if (!scene) return <Empty title="No scene selected">Add a scene on the left, or import a screenplay.</Empty>
  const shots = scene.shotIds.map((id) => project.shots[id]).filter(Boolean)

  const onDragEnd = (e: DragEndEvent) => {
    const { active, over } = e
    if (!over || active.id === over.id) return
    const from = scene.shotIds.indexOf(String(active.id))
    const to = scene.shotIds.indexOf(String(over.id))
    if (from >= 0 && to >= 0) moveShot(scene.id, from, to)
  }

  const parsedScene = () => {
    const text = scene.scriptText?.trim() ? scene.scriptText : `${scene.heading}\n\n${scene.synopsis || ''}`
    const parsed = parseScreenplay(textToLines(text))[0]
    if (!parsed) return null
    if (!parsed.characters.length && scene.characters.length) parsed.characters = [...scene.characters]
    return parsed
  }

  const autoShots = () => {
    const ps = parsedScene()
    if (!ps) { toast('Add script text or a synopsis to this scene first.', 'error'); return }
    if (shots.length && !confirm(`Replace the ${shots.length} existing shots in this scene?`)) return
    const drafts = generateShotList(ps, director)
    addShotsFromDrafts(scene.id, drafts, true)
    toast(`${drafts.length} shots laid out in the ${director.name} lens.`)
  }

  const claudeShots = async () => {
    const ps = parsedScene()
    if (!ps) { toast('Add script text or a synopsis to this scene first.', 'error'); return }
    if (shots.length && !confirm(`Replace the ${shots.length} existing shots in this scene?`)) return
    setBusy('Claude is breaking down the scene…')
    try {
      const res = await claudeShotList({ heading: scene.heading, text: ps.text, characters: ps.characters }, director, project.aspectRatio)
      if (!res) { toast('Claude is not configured on the server.', 'error'); return }
      addShotsFromDrafts(scene.id, res.shots.map((s) => ({ ...s, lensCharacter: s.lensCharacter ?? director.lensCharacter, aspectRatio: null, colorTags: s.colorTags?.length ? s.colorTags : [...director.colorTags] })), true)
      if (res.sceneSummary) updateScene(scene.id, { synopsis: res.sceneSummary })
      toast(`${res.shots.length} shots from Claude (${res.model}).`)
    } catch (e) {
      toast((e as Error).message, 'error')
    } finally { setBusy(null) }
  }

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-3 border-b border-line flex items-center gap-3 shrink-0">
        <span className="chip">Sc {scene.sceneNo}</span>
        <input className="bg-transparent outline-none text-sm font-semibold flex-1 min-w-0" value={scene.heading}
          onChange={(e) => updateScene(scene.id, { heading: e.target.value })} placeholder="INT. LOCATION - DAY" />
        <span className="text-mute text-xs whitespace-nowrap">{shots.length} shots</span>
        <button className="btn" onClick={() => addShot(scene.id)}>＋ Shot</button>
        <button className="btn" onClick={autoShots} title={`Lay out coverage in the ${director.name} lens (offline)`}>🎬 Auto shot list</button>
        {providers?.claude && (
          <button className="btn" onClick={() => void claudeShots()} disabled={!!busy} title="Claude directs the scene in this lens">
            {busy ? <Spinner /> : '✦'} Claude breakdown
          </button>
        )}
      </div>
      <div className="flex-1 overflow-auto p-4" onClick={(e) => { if (e.target === e.currentTarget) selectShot(null) }}>
        {shots.length === 0 ? (
          <Empty title="Empty scene">
            Add a shot, drop images anywhere on a card, or press <b>Auto shot list</b> to let the <b>{director.name}</b> lens lay out coverage from the scene text.
          </Empty>
        ) : (
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
            <SortableContext items={scene.shotIds} strategy={rectSortingStrategy}>
              <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(230px, 1fr))' }}>
                {shots.map((s) => <ShotCard key={s.id} shot={s} ratio={ratio} sceneNo={scene.sceneNo} />)}
              </div>
            </SortableContext>
          </DndContext>
        )}
      </div>
    </div>
  )
}
