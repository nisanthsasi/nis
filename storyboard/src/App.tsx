import { useEffect, useState } from 'react'
import { useProject } from './store/useProject'
import { generateApi } from './api/generate'
import { ProjectHome } from './components/ProjectHome'
import { TopBar } from './components/TopBar'
import { SettingsDrawer } from './components/SettingsDrawer'
import { ScenesPanel } from './components/Left/ScenesPanel'
import { ScriptPanel } from './components/Left/ScriptPanel'
import { DirectorPanel } from './components/Left/DirectorPanel'
import { BoardGrid } from './components/Board/BoardGrid'
import { ShotInspector } from './components/Right/ShotInspector'
import { ReferencesPanel } from './components/Right/ReferencesPanel'
import { GeneratePanel } from './components/Right/GeneratePanel'
import { Tabs, Toast } from './components/ui'

export default function App() {
  const project = useProject((s) => s.project)
  const ui = useProject((s) => s.ui)
  const setLeftTab = useProject((s) => s.setLeftTab)
  const setRightTab = useProject((s) => s.setRightTab)
  const setProviders = useProject((s) => s.setProviders)
  const removeShot = useProject((s) => s.removeShot)
  const [settingsOpen, setSettingsOpen] = useState(false)

  useEffect(() => {
    const poll = () => generateApi.providers().then(setProviders).catch(() => { /* server down; panels show guidance */ })
    void poll()
    const t = setInterval(poll, 30_000)
    return () => clearInterval(t)
  }, [setProviders])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      const st = useProject.getState()
      if ((e.key === 'Delete' || e.key === 'Backspace') && st.selectedShotId) {
        if (confirm('Delete the selected shot?')) removeShot(st.selectedShotId)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [removeShot])

  if (!project) return <><ProjectHome /><Toast toast={ui.toast} /></>

  return (
    <div className="h-full flex flex-col">
      <TopBar onHome={() => { void useProject.getState().refreshProjects(); useProject.setState({ project: null, selectedSceneId: null, selectedShotId: null }) }} onSettings={() => setSettingsOpen(true)} />
      <div className="flex-1 min-h-0 grid" style={{ gridTemplateColumns: '300px 1fr 360px' }}>
        <aside className="border-r border-line bg-panel flex flex-col min-h-0">
          <Tabs value={ui.leftTab} onChange={setLeftTab} tabs={[{ value: 'scenes', label: 'Scenes' }, { value: 'script', label: 'Script' }, { value: 'director', label: 'Director' }]} />
          <div className="flex-1 min-h-0 overflow-auto">
            {ui.leftTab === 'scenes' && <ScenesPanel />}
            {ui.leftTab === 'script' && <ScriptPanel />}
            {ui.leftTab === 'director' && <DirectorPanel />}
          </div>
        </aside>
        <main className="min-h-0 min-w-0 bg-ink"><BoardGrid /></main>
        <aside className="border-l border-line bg-panel flex flex-col min-h-0">
          <Tabs value={ui.rightTab} onChange={setRightTab} tabs={[{ value: 'shot', label: 'Shot' }, { value: 'refs', label: 'References' }, { value: 'generate', label: 'Generate' }]} />
          <div className="flex-1 min-h-0 overflow-auto">
            {ui.rightTab === 'shot' && <ShotInspector />}
            {ui.rightTab === 'refs' && <ReferencesPanel />}
            {ui.rightTab === 'generate' && <GeneratePanel />}
          </div>
        </aside>
      </div>
      {settingsOpen && <SettingsDrawer onClose={() => setSettingsOpen(false)} />}
      <Toast toast={ui.toast} />
    </div>
  )
}
