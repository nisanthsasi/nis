import type { ReactNode, SelectHTMLAttributes } from 'react'

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
      {hint && <span className="block text-[11px] text-mute mt-1">{hint}</span>}
    </label>
  )
}

export function Select<T extends string>({ value, options, onChange, ...rest }: {
  value: T
  options: { value: T; label: string }[]
  onChange: (v: T) => void
} & Omit<SelectHTMLAttributes<HTMLSelectElement>, 'value' | 'onChange'>) {
  return (
    <select className="field" value={value} onChange={(e) => onChange(e.target.value as T)} {...rest}>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  )
}

export function Spinner({ className = '' }: { className?: string }) {
  return <span className={`inline-block w-3.5 h-3.5 border-2 border-mute/40 border-t-accent rounded-full animate-spin ${className}`} />
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="p-6 text-center text-mute">
      <div className="text-sm text-text mb-1">{title}</div>
      <div className="text-xs leading-relaxed">{children}</div>
    </div>
  )
}

export function Tabs<T extends string>({ value, tabs, onChange }: { value: T; tabs: { value: T; label: string }[]; onChange: (v: T) => void }) {
  return (
    <div className="flex border-b border-line shrink-0">
      {tabs.map((t) => (
        <button key={t.value} onClick={() => onChange(t.value)}
          className={`px-3 py-2 text-xs uppercase tracking-wide border-b-2 -mb-px cursor-pointer ${value === t.value ? 'border-accent text-text' : 'border-transparent text-mute hover:text-text'}`}>
          {t.label}
        </button>
      ))}
    </div>
  )
}

export function Toast({ toast }: { toast: { kind: 'info' | 'error'; text: string } | null }) {
  if (!toast) return null
  return (
    <div className={`fixed bottom-4 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded shadow-lg text-sm border ${toast.kind === 'error' ? 'bg-[#3a1d1d] border-danger/60 text-[#ffd0d0]' : 'bg-panel-2 border-line text-text'}`}>
      {toast.text}
    </div>
  )
}
