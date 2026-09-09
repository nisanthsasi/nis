// Image generation providers behind one interface:
//   generate({ provider, prompt, aspect, seed, referenceImages }) -> { pngBase64, mime, provider, cost }
// referenceImages: array of data URLs (base64) used for character/style consistency where supported.

const ASPECTS = {
  '16:9': { w: 1536, h: 864, gemini: '16:9', cf: [1024, 576] },
  '1.85:1': { w: 1536, h: 832, gemini: '16:9', cf: [1024, 560] },
  '2:1': { w: 1536, h: 768, gemini: '2:1', cf: [1024, 512] },
  '2.39:1': { w: 1536, h: 640, gemini: '21:9', cf: [1024, 432] },
  '4:3': { w: 1024, h: 768, gemini: '4:3', cf: [1024, 768] },
  '1:1': { w: 1024, h: 1024, gemini: '1:1', cf: [1024, 1024] },
  '9:16': { w: 864, h: 1536, gemini: '9:16', cf: [576, 1024] },
}

export function providerStatus() {
  return {
    pollinations: true,
    cloudflare: Boolean(process.env.CLOUDFLARE_ACCOUNT_ID && process.env.CLOUDFLARE_API_TOKEN),
    gemini: Boolean(process.env.GEMINI_API_KEY),
    openai: Boolean(process.env.OPENAI_API_KEY),
  }
}

function dims(aspect) { return ASPECTS[aspect] ?? ASPECTS['16:9'] }

function parseDataUrl(u) {
  const m = /^data:([^;,]+)?(;base64)?,(.*)$/s.exec(u || '')
  if (!m) return null
  return { mime: m[1] || 'image/png', base64: m[3] }
}

async function readError(res) {
  const text = await res.text().catch(() => '')
  try { const j = JSON.parse(text); return j?.error?.message || j?.error || j?.message || text } catch { return text || res.statusText }
}

// ---- Pollinations (free, no key) -------------------------------------------------
let lastPollinations = 0
const POLL_GAP_MS = 15_500
export function pollinationsWaitMs() { return Math.max(0, lastPollinations + POLL_GAP_MS - Date.now()) }

async function pollinations({ prompt, aspect, seed }) {
  const wait = pollinationsWaitMs()
  if (wait > 0) await new Promise((r) => setTimeout(r, wait))
  lastPollinations = Date.now()
  const { w, h } = dims(aspect)
  const params = new URLSearchParams({ width: String(w), height: String(h), model: 'flux', nologo: 'true', enhance: 'false', safe: 'false' })
  if (seed != null) params.set('seed', String(seed))
  if (process.env.POLLINATIONS_TOKEN) params.set('token', process.env.POLLINATIONS_TOKEN)
  const url = `https://image.pollinations.ai/prompt/${encodeURIComponent(prompt)}?${params}`
  const res = await fetch(url, { headers: { Accept: 'image/*', Referer: 'storyboard-maker' } })
  if (!res.ok) throw Object.assign(new Error(`Pollinations: ${await readError(res)}`), { status: res.status === 429 ? 429 : 502 })
  const buf = Buffer.from(await res.arrayBuffer())
  const mime = res.headers.get('content-type')?.split(';')[0] || 'image/jpeg'
  return { pngBase64: buf.toString('base64'), mime, provider: 'pollinations', cost: 'free' }
}

// ---- Cloudflare Workers AI: FLUX.1 schnell --------------------------------------
async function cloudflare({ prompt, aspect, seed }) {
  const acct = process.env.CLOUDFLARE_ACCOUNT_ID
  const tok = process.env.CLOUDFLARE_API_TOKEN
  const [width, height] = dims(aspect).cf
  const res = await fetch(`https://api.cloudflare.com/client/v4/accounts/${acct}/ai/run/@cf/black-forest-labs/flux-1-schnell`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${tok}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, steps: 6, width, height, ...(seed != null ? { seed } : {}) }),
  })
  if (!res.ok) throw Object.assign(new Error(`Cloudflare: ${await readError(res)}`), { status: 502 })
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) {
    const j = await res.json()
    const b64 = j?.result?.image
    if (!b64) throw Object.assign(new Error('Cloudflare returned no image'), { status: 502 })
    return { pngBase64: b64, mime: 'image/jpeg', provider: 'cloudflare', cost: 'free tier' }
  }
  const buf = Buffer.from(await res.arrayBuffer())
  return { pngBase64: buf.toString('base64'), mime: ct.split(';')[0] || 'image/png', provider: 'cloudflare', cost: 'free tier' }
}

// ---- Gemini (Nano Banana) ---------------------------------------------------------
async function gemini({ prompt, aspect, referenceImages = [], model }) {
  const key = process.env.GEMINI_API_KEY
  const mdl = model || process.env.GEMINI_IMAGE_MODEL || 'gemini-2.5-flash-image'
  const parts = []
  for (const ref of referenceImages.slice(0, 3)) {
    const d = parseDataUrl(ref)
    if (d) parts.push({ inlineData: { mimeType: d.mime, data: d.base64 } })
  }
  parts.push({ text: (referenceImages.length ? 'Use the attached images as reference for the characters and visual style. ' : '') + prompt })
  const body = {
    contents: [{ role: 'user', parts }],
    generationConfig: { responseModalities: ['IMAGE'], imageConfig: { aspectRatio: dims(aspect).gemini } },
  }
  const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${mdl}:generateContent`, {
    method: 'POST', headers: { 'x-goog-api-key': key, 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  if (!res.ok) throw Object.assign(new Error(`Gemini: ${await readError(res)}`), { status: res.status === 429 ? 429 : 502 })
  const j = await res.json()
  const img = j?.candidates?.[0]?.content?.parts?.find((p) => p.inlineData)?.inlineData
  if (!img) {
    const reason = j?.candidates?.[0]?.finishReason || j?.promptFeedback?.blockReason || 'no image in response'
    throw Object.assign(new Error(`Gemini returned no image (${reason})`), { status: 502 })
  }
  return { pngBase64: img.data, mime: img.mimeType || 'image/png', provider: 'gemini', cost: mdl }
}

// ---- OpenAI gpt-image-2 -----------------------------------------------------------
async function openai({ prompt, aspect, referenceImages = [], quality }) {
  const key = process.env.OPENAI_API_KEY
  const model = process.env.OPENAI_IMAGE_MODEL || 'gpt-image-2'
  const { w, h } = dims(aspect)
  const size = `${w}x${h}`
  let res
  if (referenceImages.length) {
    const fd = new FormData()
    fd.set('model', model)
    fd.set('prompt', prompt)
    fd.set('size', size)
    fd.set('quality', quality || 'medium')
    referenceImages.slice(0, 4).forEach((ref, i) => {
      const d = parseDataUrl(ref)
      if (d) fd.append('image[]', new Blob([Buffer.from(d.base64, 'base64')], { type: d.mime }), `ref${i}.png`)
    })
    res = await fetch('https://api.openai.com/v1/images/edits', { method: 'POST', headers: { Authorization: `Bearer ${key}` }, body: fd })
  } else {
    res = await fetch('https://api.openai.com/v1/images/generations', {
      method: 'POST', headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ model, prompt, size, quality: quality || 'medium', n: 1 }),
    })
  }
  if (!res.ok) throw Object.assign(new Error(`OpenAI: ${await readError(res)}`), { status: res.status === 429 ? 429 : 502 })
  const j = await res.json()
  const b64 = j?.data?.[0]?.b64_json
  if (!b64) throw Object.assign(new Error('OpenAI returned no image'), { status: 502 })
  return { pngBase64: b64, mime: 'image/png', provider: 'openai', cost: `${model} ${quality || 'medium'}` }
}

const PROVIDERS = { pollinations, cloudflare, gemini, openai }

export async function generate(opts) {
  const provider = opts.provider || 'pollinations'
  const fn = PROVIDERS[provider]
  if (!fn) throw Object.assign(new Error(`Unknown provider ${provider}`), { status: 400 })
  if (!providerStatus()[provider]) throw Object.assign(new Error(`${provider} is not configured on the server (.env)`), { status: 503 })
  if (!opts.prompt || typeof opts.prompt !== 'string') throw Object.assign(new Error('prompt is required'), { status: 400 })
  return fn(opts)
}
