import { useState } from 'react'
import { fileToLines, parseScreenplay, textToLines } from '../../lib/screenplay'
import { useDirector, useProject } from '../../store/useProject'
import { claudeShotList } from '../../api/shotlist'
import type { ParsedScene } from '../../types'
import { Spinner } from '../ui'

export function ScriptPanel() {
  const director = useDirector()
  const providers = useProject((s) => s.providers)
  const importScenes = useProject((s) => s.importScenes)
  const addShotsFromDrafts = useProject((s) => s.addShotsFromDrafts)
  const toast = useProject((s) => s.toast)
  const setLeftTab = useProject((s) => s.setLeftTab)
  const [parsed, setParsed] = useState<ParsedScene[]>([])
  const [picked, setPicked] = useState<Set<number>>(new Set())
  const [paste, setPaste] = useState('')
  const [fileName, setFileName] = useState('')
  const [genShots, setGenShots] = useState(true)
  const [useClaude, setUseClaude] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)

  const load = (scenes: ParsedScene[], name: string) => {
    setParsed(scenes)
    setPicked(new Set(scenes.map((_, i) => i)))
    setFileName(name)
    if (!scenes.length) toast('No scenes found. Check the file is a screenplay with INT./EXT. headings.', 'error')
  }

  const onFile = async (f: File | undefined) => {
    if (!f) return
    setBusy('Reading…')
    try { load(parseScreenplay(await fileToLines(f)), f.name) } catch (e) { toast(`Could not read file: ${(e as Error).message}`, 'error') } finally { setBusy(null) }
  }

  const doImport = async () => {
    const chosen = parsed.filter((_, i) => picked.has(i))
    if (!chosen.length) return
    if (useClaude && providers?.claude) {
      importScenes(chosen, { generateShots: false })
      const st = useProject.getState()
      const newScenes = st.project!.scenes.slice(-chosen.length)
      for (let i = 0; i < chosen.length; i++) {
        setBusy(`Claude directing scene ${i + 1}/${chosen.length}…`)
        try {
          const res = await claudeShotList({ heading: chosen[i].heading, text: chosen[i].text, characters: chosen[i].characters }, director, st.project!.aspectRatio)
          if (res) addShotsFromDrafts(newScenes[i].id, res.shots.map((s) => ({ ...s, aspectRatio: null, colorTags: s.colorTags?.length ? s.colorTags : [...director.colorTags] })))
        } catch (e) { toast(`Scene ${chosen[i].sceneNo}: ${(e as Error).message}`, 'error') }
      }
      setBusy(null)
    } else {
      importScenes(chosen, { generateShots: genShots })
    }
    toast(`Imported ${chosen.length} scene${chosen.length > 1 ? 's' : ''}${genShots ? ` with shots in the ${director.name} lens` : ''}.`)
    setParsed([]); setPaste('')
    setLeftTab('scenes')
  }

  return (
    <div className="flex flex-col h-full text-xs">
      <div className="p-3 space-y-2 border-b border-line">
        <label className="btn w-full justify-center cursor-pointer">
          {busy ? <Spinner /> : '📄'} Upload screenplay (.pdf, .fountain, .txt)
          <input type="file" accept=".pdf,.fountain,.txt,application/pdf,text/plain" hidden onChange={(e) => { void onFile(e.target.files?.[0]); e.target.value = '' }} />
        </label>
        <textarea className="field min-h-[90px] font-mono text-[11px]" value={paste} onChange={(e) => setPaste(e.target.value)} placeholder={'…or paste scenes here\n\nINT. KITCHEN - NIGHT\n\nMEERA stands at the sink.\n\nRAVI\nAre you going to answer that?'} />
        <button className="btn w-full justify-center" disabled={!paste.trim()} onClick={() => load(parseScreenplay(textToLines(paste)), 'pasted text')}>Parse pasted text</button>
      </div>

      {parsed.length > 0 && (
        <>
          <div className="px-3 py-2 border-b border-line flex items-center justify-between">
            <span className="text-mute truncate">{parsed.length} scenes in {fileName}</span>
            <div className="flex gap-1">
              <button className="btn btn-ghost !py-0.5" onClick={() => setPicked(new Set(parsed.map((_, i) => i)))}>all</button>
              <button className="btn btn-ghost !py-0.5" onClick={() => setPicked(new Set())}>none</button>
            </div>
          </div>
          <div className="flex-1 overflow-auto">
            {parsed.map((s, i) => (
              <label key={i} className="flex gap-2 px-3 py-1.5 border-b border-line/60 cursor-pointer hover:bg-panel-2/50">
                <input type="checkbox" className="mt-0.5" checked={picked.has(i)} onChange={() => setPicked((p) => { const n = new Set(p); if (n.has(i)) n.delete(i); else n.add(i); return n })} />
                <div className="min-w-0">
                  <div className="truncate"><span className="text-mute mr-1">{s.sceneNo}</span>{s.heading}</div>
                  <div className="text-mute truncate">p.{s.pageStart}{s.pageEnd !== s.pageStart ? `–${s.pageEnd}` : ''} · {s.elements.filter((e) => e.type === 'dialogue').length} lines · {s.characters.slice(0, 3).join(', ')}</div>
                </div>
              </label>
            ))}
          </div>
          <div className="p-3 border-t border-line space-y-2">
            <label className="flex items-center gap-2"><input type="checkbox" checked={genShots} onChange={(e) => setGenShots(e.target.checked)} /> Lay out shots in the <b>{director.name}</b> lens</label>
            {providers?.claude && <label className={`flex items-center gap-2 ${genShots ? '' : 'opacity-50'}`}><input type="checkbox" disabled={!genShots} checked={useClaude} onChange={(e) => setUseClaude(e.target.checked)} /> Use Claude to direct (slower, better)</label>}
            <button className="btn btn-primary w-full justify-center" disabled={picked.size === 0 || !!busy} onClick={() => void doImport()}>
              {busy ? <><Spinner /> {busy}</> : `Import ${picked.size} scene${picked.size === 1 ? '' : 's'}`}
            </button>
          </div>
        </>
      )}
      {parsed.length === 0 && (
        <div className="p-4 text-mute leading-relaxed">
          The parser reads INT./EXT. headings, action, CHARACTER cues, dialogue and parentheticals. Nothing leaves your browser. Pick a director lens first so the shot list is laid out in that grammar.
        </div>
      )}
    </div>
  )
}
