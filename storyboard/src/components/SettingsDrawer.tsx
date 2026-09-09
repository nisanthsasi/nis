import { useProject } from '../store/useProject'
import { PROVIDERS } from '../taxonomy'
import { Field, Select } from './ui'
import type { ProviderId } from '../types'

export function SettingsDrawer({ onClose }: { onClose: () => void }) {
  const project = useProject((s) => s.project)!
  const providers = useProject((s) => s.providers)
  const setSettings = useProject((s) => s.setSettings)
  const st = project.settings
  return (
    <div className="fixed inset-0 z-40 flex justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/50" />
      <div className="relative w-80 h-full bg-panel border-l border-line p-4 space-y-4 text-xs overflow-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between"><div className="text-sm font-semibold">Settings</div><button className="btn btn-ghost" onClick={onClose}>✕</button></div>
        <Field label="PDF page size"><Select value={st.pageSize} options={[{ value: 'a4', label: 'A4 landscape' }, { value: 'letter', label: 'Letter landscape' }]} onChange={(v) => setSettings({ pageSize: v })} /></Field>
        <Field label="Frames per page"><Select<'2' | '4' | '6'> value={String(st.framesPerPage) as '2' | '4' | '6'} options={[{ value: '2', label: '2 (large)' }, { value: '4', label: '4' }, { value: '6', label: '6 (contact sheet)' }]} onChange={(v) => setSettings({ framesPerPage: Number(v) as 2 | 4 | 6 })} /></Field>
        <label className="flex items-center gap-2"><input type="checkbox" checked={st.showCredits} onChange={(e) => setSettings({ showCredits: e.target.checked })} /> Print credit line under reference stills</label>
        <Field label="Default image provider"><Select<ProviderId> value={st.provider} options={PROVIDERS.map((p) => ({ value: p.value, label: p.label }))} onChange={(v) => setSettings({ provider: v })} /></Field>
        <div>
          <span className="label">Server status</span>
          {providers ? (
            <ul className="space-y-1">
              {(['pollinations', 'cloudflare', 'gemini', 'openai', 'framethrower', 'claude'] as const).map((k) => (
                <li key={k} className="flex justify-between"><span>{k}</span><span className={providers[k] ? 'text-[#8fd18f]' : 'text-mute'}>{providers[k] ? 'configured' : 'off'}</span></li>
              ))}
            </ul>
          ) : <div className="text-danger">API server not reachable. Run <code>npm run dev</code> (starts both web and api).</div>}
          <p className="text-mute mt-2 leading-relaxed">Keys live in <code>storyboard/.env</code> on the server, never in the browser. See README for where to get each one; Pollinations needs none.</p>
        </div>
      </div>
    </div>
  )
}
