import { useEffect, useState } from 'react'
import { useProject } from '../store/useProject'
import type { Project } from '../types'

export function ProjectHome() {
  const projects = useProject((s) => s.projects)
  const refresh = useProject((s) => s.refreshProjects)
  const newProject = useProject((s) => s.newProject)
  const openProject = useProject((s) => s.openProject)
  const deleteProject = useProject((s) => s.deleteProject)
  const importProject = useProject((s) => s.importProject)
  const toast = useProject((s) => s.toast)
  const [name, setName] = useState('')
  useEffect(() => { void refresh() }, [refresh])

  const onImport = async (f: File | undefined) => {
    if (!f) return
    try {
      const p = JSON.parse(await f.text()) as Project
      if (!p.scenes || !p.shots) throw new Error('not a storyboard project file')
      await importProject(p)
    } catch (e) { toast(`Import failed: ${(e as Error).message}`, 'error') }
  }

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-3xl mx-auto p-10">
        <h1 className="text-2xl font-semibold tracking-tight">Storyboard Maker</h1>
        <p className="text-mute mt-1">Reference stills, director lenses, AI frames and a printable board. Everything is saved in this browser.</p>
        <div className="mt-8 flex gap-2">
          <input className="field max-w-xs" value={name} onChange={(e) => setName(e.target.value)} placeholder="New board name" onKeyDown={(e) => e.key === 'Enter' && void newProject(name || undefined)} />
          <button className="btn btn-primary" onClick={() => void newProject(name || undefined)}>＋ New board</button>
          <label className="btn cursor-pointer">⇧ Import JSON<input type="file" accept="application/json,.json" hidden onChange={(e) => void onImport(e.target.files?.[0])} /></label>
        </div>
        <div className="mt-8 grid gap-2">
          {projects.length === 0 && <div className="text-mute">No boards yet.</div>}
          {projects.map((p) => (
            <div key={p.id} className="flex items-center gap-3 border border-line rounded bg-panel px-4 py-3 hover:border-mute/60">
              <button className="flex-1 text-left cursor-pointer" onClick={() => void openProject(p.id)}>
                <div className="font-medium">{p.name}</div>
                <div className="text-mute text-xs">{p.sceneCount} scenes · {p.shotCount} shots · {new Date(p.updatedAt).toLocaleString()}</div>
              </button>
              <button className="btn btn-ghost text-danger" onClick={() => { if (confirm(`Delete "${p.name}"?`)) void deleteProject(p.id) }}>✕</button>
            </div>
          ))}
        </div>
        <div className="mt-12 text-xs text-mute leading-relaxed space-y-1">
          <p><b className="text-text">Reference stills</b> come from FrameThrower's API (ShotDeck and Film Vibes offer no API and forbid scraping). Add a free token in <code>.env</code>.</p>
          <p><b className="text-text">AI frames</b> default to Pollinations, which is free and needs no key. Cloudflare, Gemini and OpenAI can be enabled in <code>.env</code>.</p>
          <p><b className="text-text">Screenplay PDFs</b> are parsed in your browser; nothing is uploaded anywhere.</p>
        </div>
      </div>
    </div>
  )
}
