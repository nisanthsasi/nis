import { useState } from 'react'
import { useDirector, useProject } from '../store/useProject'
import { ASPECT_RATIOS } from '../taxonomy'
import { downloadBlob, exportStoryboardPdf } from '../export/pdf'
import { Spinner } from './ui'
import type { AspectRatio } from '../types'

export function TopBar({ onHome, onSettings }: { onHome: () => void; onSettings: () => void }) {
  const project = useProject((s) => s.project)!
  const director = useDirector()
  const setProject = useProject((s) => s.setProject)
  const setAspect = useProject((s) => s.setAspect)
  const setLeftTab = useProject((s) => s.setLeftTab)
  const toast = useProject((s) => s.toast)
  const [busy, setBusy] = useState<string | null>(null)

  const exportPdf = async () => {
    setBusy('0%')
    try {
      const blob = await exportStoryboardPdf(project, { onProgress: (d, t) => setBusy(`${Math.round((d / Math.max(1, t)) * 100)}%`) })
      downloadBlob(blob, `${project.name.replace(/[^\w-]+/g, '_')}_storyboard.pdf`)
    } catch (e) { toast(`PDF failed: ${(e as Error).message}`, 'error') } finally { setBusy(null) }
  }
  const exportJson = () => {
    const blob = new Blob([JSON.stringify(project, null, 2)], { type: 'application/json' })
    downloadBlob(blob, `${project.name.replace(/[^\w-]+/g, '_')}.storyboard.json`)
    toast('Project JSON exported (images stay in this browser; re-generate or re-upload after importing elsewhere).')
  }

  return (
    <header className="h-12 border-b border-line bg-panel flex items-center gap-2 px-3 shrink-0">
      <button className="btn btn-ghost !px-2" onClick={onHome} title="All boards">🎞</button>
      <input className="bg-transparent outline-none font-semibold text-sm min-w-0 w-56" value={project.name} onChange={(e) => setProject({ name: e.target.value })} />
      <button className="btn !py-1" onClick={() => setLeftTab('director')} title="Change director lens">🎬 {director.name}</button>
      <select className="field !w-auto !py-1" value={project.aspectRatio} onChange={(e) => setAspect(e.target.value as AspectRatio)} title="Project aspect ratio">
        {ASPECT_RATIOS.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
      </select>
      <div className="flex-1" />
      <button className="btn !py-1" onClick={exportJson}>⇩ JSON</button>
      <button className="btn btn-primary !py-1" onClick={() => void exportPdf()} disabled={!!busy}>{busy ? <><Spinner /> {busy}</> : '⇩ Export PDF'}</button>
      <button className="btn btn-ghost !px-2" onClick={onSettings} title="Settings">⚙</button>
    </header>
  )
}
