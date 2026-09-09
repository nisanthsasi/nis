export function uid(prefix = ''): string {
  const core = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID().replace(/-/g, '').slice(0, 12)
    : Math.random().toString(36).slice(2, 14)
  return prefix ? `${prefix}_${core}` : core
}
