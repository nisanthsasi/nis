import 'dotenv/config'
import express from 'express'
import path from 'node:path'
import fs from 'node:fs'
import { fileURLToPath } from 'node:url'
import net from 'node:net'
import { frames, framesEnabled, frameError, seenImageHosts } from './frames.mjs'
import { generate, providerStatus, pollinationsWaitMs } from './generate.mjs'
import { claudeEnabled, claudeShotList } from './shotlist.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const app = express()
app.disable('x-powered-by')
app.use(express.json({ limit: '25mb' }))

const send = (res, p) => p.then((data) => res.json({ data })).catch((err) => {
  const { status, body } = frameError(err)
  res.status(status).json(body)
})

// ---- status ---------------------------------------------------------------
app.get('/api/providers', (_req, res) => {
  res.json({ ...providerStatus(), framethrower: framesEnabled, claude: claudeEnabled, pollinationsWaitMs: pollinationsWaitMs() })
})

// ---- FrameThrower ----------------------------------------------------------
const num = (v, d) => { const n = Number(v); return Number.isFinite(n) && n > 0 ? Math.min(n, 60) : d }

app.get('/api/frames/search', (req, res) => {
  const q = String(req.query.q || '').trim()
  if (!q) return res.status(400).json({ error: 'q is required' })
  const mode = req.query.mode === 'description' ? 'description' : 'hybrid'
  send(res, frames.search(q, { limit: num(req.query.limit, 24), mode }))
})
app.get('/api/frames/browse', (req, res) => {
  const allowed = ['shot_type', 'lens_character', 'setting', 'time_of_day', 'camera_angle', 'visual_style', 'director', 'genre', 'era']
  const filters = {}
  for (const k of allowed) if (req.query[k]) filters[k] = String(req.query[k])
  if (req.query.year_min) filters.year_min = Number(req.query.year_min)
  if (req.query.year_max) filters.year_max = Number(req.query.year_max)
  filters.limit = num(req.query.limit, 24)
  send(res, frames.browse(filters))
})
app.get('/api/frames/similar/:id', (req, res) => {
  const mode = ['semantic', 'visual', 'color'].includes(String(req.query.mode)) ? String(req.query.mode) : 'visual'
  send(res, frames.similar(req.params.id, { mode, limit: num(req.query.limit, 24) }))
})
app.get('/api/frames/suggest', (req, res) => send(res, frames.suggest(String(req.query.q || ''))))
app.get('/api/frames/random', (req, res) => send(res, frames.random(num(req.query.limit, 24))))
app.get('/api/frames/film/:slug', (req, res) => send(res, frames.filmFrames(req.params.slug, { page: num(req.query.page, 1), perPage: num(req.query.perPage, 40) })))
app.get('/api/frames/:id', (req, res) => send(res, frames.frame(req.params.id)))

// ---- image proxy (so reference thumbnails can be drawn into the PDF) --------
function hostAllowed(host) {
  if (net.isIP(host)) return false
  if (host === 'localhost' || host.endsWith('.local')) return false
  if (seenImageHosts.has(host)) return true
  for (const h of seenImageHosts) if (host.endsWith('.' + h)) return true
  const extra = (process.env.IMG_PROXY_ALLOW || '').split(',').map((s) => s.trim()).filter(Boolean)
  return extra.some((h) => host === h || host.endsWith('.' + h))
}
app.get('/api/img', async (req, res) => {
  let url
  try { url = new URL(String(req.query.url || '')) } catch { return res.status(400).json({ error: 'bad url' }) }
  if (url.protocol !== 'https:' || !hostAllowed(url.hostname)) return res.status(403).json({ error: 'host not allowed' })
  try {
    const up = await fetch(url, { headers: { Accept: 'image/*' }, redirect: 'follow' })
    if (!up.ok) return res.status(up.status).end()
    const ct = up.headers.get('content-type') || 'image/jpeg'
    if (!ct.startsWith('image/')) return res.status(415).json({ error: 'not an image' })
    res.setHeader('Content-Type', ct)
    res.setHeader('Cache-Control', 'public, max-age=86400')
    res.setHeader('Access-Control-Allow-Origin', '*')
    res.send(Buffer.from(await up.arrayBuffer()))
  } catch (err) {
    res.status(502).json({ error: err.message })
  }
})

// ---- generation ------------------------------------------------------------
app.post('/api/generate', async (req, res) => {
  const { provider, prompt, aspect, seed, referenceImages, quality, model } = req.body || {}
  try {
    const out = await generate({ provider, prompt, aspect, seed, referenceImages, quality, model })
    res.json({ data: out })
  } catch (err) {
    res.status(err.status || 500).json({ error: err.message })
  }
})

// ---- Claude shot list (optional) --------------------------------------------
app.post('/api/shotlist', async (req, res) => {
  if (!claudeEnabled) return res.status(404).json({ error: 'Claude not configured' })
  try {
    const out = await claudeShotList(req.body || {})
    res.json({ data: out })
  } catch (err) {
    res.status(err.status || 500).json({ error: err.message })
  }
})

// ---- static in production ---------------------------------------------------
const dist = path.join(here, '..', 'dist')
if (process.env.NODE_ENV === 'production' && fs.existsSync(dist)) {
  app.use(express.static(dist))
  app.get(/^(?!\/api\/).*/, (_req, res) => res.sendFile(path.join(dist, 'index.html')))
}

const port = Number(process.env.PORT || 8787)
if (process.env.NODE_ENV !== 'test') {
  app.listen(port, () => {
    const st = providerStatus()
    console.log(`storyboard api on http://localhost:${port}`)
    console.log(`  framethrower: ${framesEnabled ? 'on' : 'off (FRAMETHROWER_TOKEN)'}  claude: ${claudeEnabled ? 'on' : 'off'}  image providers: ${Object.entries(st).filter(([, v]) => v).map(([k]) => k).join(', ')}`)
  })
}

export { app }
