// FrameThrower wrapper. Returns metadata + image URLs only (never bytes), per their intended use.
import FrameThrower from 'framethrower-ai'

const token = process.env.FRAMETHROWER_TOKEN
export const framesEnabled = Boolean(token)
const ft = token ? new FrameThrower(token) : null

/** Hostnames seen in FrameThrower responses, allowed through the image proxy. */
export const seenImageHosts = new Set(['framethrower.ai', 'www.framethrower.ai', 'cdn.framethrower.ai'])

function remember(frames) {
  for (const f of Array.isArray(frames) ? frames : [frames]) {
    for (const u of [f?.imageUrl, f?.thumbUrl, f?.film?.posterUrl]) {
      if (!u) continue
      try { seenImageHosts.add(new URL(u).hostname) } catch { /* ignore */ }
    }
  }
  return frames
}

function need() {
  if (!ft) { const e = new Error('FrameThrower is not configured. Add FRAMETHROWER_TOKEN to .env'); e.status = 503; throw e }
  return ft
}

export const frames = {
  search: (q, opts) => need().search(q, opts).then(remember),
  browse: (filters) => need().browse(filters).then(remember),
  similar: (id, opts) => need().similar(id, opts).then(remember),
  frame: (id) => need().frame(id).then(remember),
  random: (limit) => need().random(limit).then(remember),
  suggest: (q) => need().suggest(q),
  films: (opts) => need().films(opts),
  filmFrames: (slug, opts) => need().filmFrames(slug, opts).then(remember),
}

/** Normalise SDK/HTTP errors (402 insufficient credits, 401 bad token) into {status, body}. */
export function frameError(err) {
  const status = err?.status ?? err?.response?.status ?? (/402|credit/i.test(String(err?.message)) ? 402 : 502)
  let body = { error: err?.message || 'FrameThrower request failed' }
  if (err?.body && typeof err.body === 'object') body = { ...body, ...err.body }
  if (status === 402 && !body.buy_credits) body.buy_credits = 'https://framethrower.ai/settings?tab=billing'
  return { status, body }
}
