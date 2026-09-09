import type { ParsedScene, ScriptElement } from '../types'

/** A line of text with the page it came from and, for PDFs, its left x position. */
export interface TextLine {
  text: string
  page: number
  x?: number
}

const HEADING_RE = /^(?:(\d+[A-Z]?)[.\s]+)?(INT\.?\/EXT\.?|EXT\.?\/INT\.?|I\/E\.?|INT\.?|EXT\.?|EST\.?)\s*[.\-–—:]?\s*(.+?)(?:\s+(\d+[A-Z]?))?\s*$/i
const TRANSITION_RE = /^(FADE (IN|OUT|TO BLACK|TO WHITE)|CUT TO|DISSOLVE TO|SMASH CUT|MATCH CUT|JUMP CUT|INTERCUT|BACK TO|TIME CUT|THE END|END OF (ACT|EPISODE|FILM))\b|[A-Z ]+TO:$/
const SKIP_RE = /^(\(?CONTINUED\)?:?|\(MORE\)|\d+\.?|Page \d+.*|CONTINUED:?\s*\(\d+\))$/i
const CUE_EXT_RE = /\s*\((V\.?O\.?|O\.?S\.?|O\.?C\.?|CONT'?D|CONTINUED|ON PHONE|INTO PHONE|FILTERED|PRE-LAP|SUBTITLED|IN [A-Z]+)\)\s*$/i

const TIME_WORDS = ['DAY', 'NIGHT', 'DAWN', 'DUSK', 'MORNING', 'EVENING', 'AFTERNOON', 'LATER', 'CONTINUOUS', 'SAME TIME', 'MOMENTS LATER', 'SUNSET', 'SUNRISE', 'MAGIC HOUR', 'GOLDEN HOUR', 'PRE-DAWN', 'MIDNIGHT', 'NOON']

export function textToLines(text: string): TextLine[] {
  const pages = text.split(/\f/)
  const out: TextLine[] = []
  pages.forEach((pg, i) => {
    for (const raw of pg.split(/\r?\n/)) out.push({ text: raw.replace(/\s+$/, ''), page: i + 1 })
  })
  return out
}

function isUpper(s: string): boolean {
  const letters = s.replace(/[^A-Za-z]/g, '')
  return letters.length > 0 && letters === letters.toUpperCase()
}

function cleanCue(s: string): string {
  return s.replace(/^@/, '').replace(CUE_EXT_RE, '').replace(/\^$/, '').trim()
}

function looksLikeCue(line: string, next: string | undefined): boolean {
  const t = line.trim()
  if (!t) return false
  if (t.startsWith('@')) return true
  if (!isUpper(t)) return false
  if (t.length > 40) return false
  if (/[.!?…]$/.test(t) && !/\)$/.test(t)) return false
  if (HEADING_RE.test(t) || TRANSITION_RE.test(t) || SKIP_RE.test(t)) return false
  const words = cleanCue(t).split(/\s+/).filter(Boolean)
  if (words.length === 0 || words.length > 5) return false
  if (!next || !next.trim()) return false
  return true
}

function parseHeading(t: string): { intExt: ParsedScene['intExt']; location: string; timeLabel: string; num: string } | null {
  const m = HEADING_RE.exec(t.trim().replace(/^\./, ''))
  if (!m) return null
  const prefix = m[2].toUpperCase().replace(/\./g, '')
  const intExt: ParsedScene['intExt'] = prefix.includes('/') || prefix === 'I/E' ? 'INT/EXT' : prefix.startsWith('INT') ? 'INT' : prefix.startsWith('EXT') ? 'EXT' : ''
  let body = m[3].trim()
  const num = m[1] || m[4] || ''
  let timeLabel = ''
  const parts = body.split(/\s+[-–—]\s+/)
  if (parts.length > 1) {
    const last = parts[parts.length - 1].trim()
    const lastUp = last.toUpperCase()
    if (TIME_WORDS.some((w) => lastUp.includes(w)) || last.length < 20) {
      timeLabel = last
      body = parts.slice(0, -1).join(' - ')
    }
  } else {
    const up = body.toUpperCase()
    const hit = TIME_WORDS.find((w) => up.endsWith(' ' + w))
    if (hit) { timeLabel = body.slice(-hit.length); body = body.slice(0, -hit.length).trim().replace(/[-–—,]$/, '').trim() }
  }
  return { intExt, location: body.trim(), timeLabel: timeLabel.trim(), num }
}

/**
 * Parse screenplay lines into scenes. Works on plain text, Fountain and text
 * reconstructed from PDFs (where blank lines mark paragraph gaps).
 */
export function parseScreenplay(lines: TextLine[]): ParsedScene[] {
  const scenes: ParsedScene[] = []
  let cur: ParsedScene | null = null
  let seq = 0
  let i = 0

  const flushAction = (buf: string[], page: number) => {
    if (!cur || buf.length === 0) return
    const text = buf.join(' ').replace(/\s+/g, ' ').trim()
    if (text) cur.elements.push({ type: 'action', text, page })
    buf.length = 0
  }

  const actionBuf: string[] = []
  let actionPage = 1

  while (i < lines.length) {
    const { text: raw, page } = lines[i]
    const t = raw.trim()
    const next = lines[i + 1]?.text

    if (!t) { flushAction(actionBuf, actionPage); i++; continue }
    if (SKIP_RE.test(t)) { i++; continue }

    const forcedHeading = t.startsWith('.') && !t.startsWith('..') && isUpper(t.slice(1, 4))
    const h = parseHeading(forcedHeading ? t.slice(1) : t)
    if (h && (forcedHeading || /^(\d+[A-Z]?[.\s]+)?(INT|EXT|I\/E|EST)/i.test(t))) {
      flushAction(actionBuf, actionPage)
      seq++
      cur = {
        sceneNo: h.num || String(seq),
        heading: (forcedHeading ? t.slice(1) : t).replace(/^\d+[A-Z]?[.\s]+/, '').replace(/\s+\d+[A-Z]?$/, '').trim(),
        intExt: h.intExt, location: h.location, timeLabel: h.timeLabel,
        pageStart: page, pageEnd: page, elements: [], characters: [], text: '',
      }
      cur.elements.push({ type: 'heading', text: cur.heading, page })
      scenes.push(cur)
      i++
      continue
    }

    if (!cur) { i++; continue } // title page / preamble

    cur.pageEnd = page

    if (TRANSITION_RE.test(t) && isUpper(t)) {
      flushAction(actionBuf, actionPage)
      cur.elements.push({ type: 'transition', text: t, page })
      i++
      continue
    }

    if (looksLikeCue(t, next)) {
      flushAction(actionBuf, actionPage)
      const character = cleanCue(t)
      if (character && !cur.characters.includes(character)) cur.characters.push(character)
      i++
      const dlg: string[] = []
      while (i < lines.length) {
        const l = lines[i].text.trim()
        if (!l) break
        if (looksLikeCue(l, lines[i + 1]?.text) || parseHeading(l) && /^(INT|EXT|I\/E)/i.test(l)) break
        if (TRANSITION_RE.test(l) && isUpper(l)) break
        if (/^\(.*\)$/.test(l)) {
          if (dlg.length) { cur.elements.push({ type: 'dialogue', text: dlg.join(' '), character, page }); dlg.length = 0 }
          cur.elements.push({ type: 'parenthetical', text: l, character, page })
        } else if (/^\(/.test(l) && !/\)$/.test(l)) {
          // multi-line parenthetical
          let p = l
          i++
          while (i < lines.length && !/\)$/.test(lines[i].text.trim()) && lines[i].text.trim()) { p += ' ' + lines[i].text.trim(); i++ }
          if (i < lines.length) p += ' ' + lines[i].text.trim()
          if (dlg.length) { cur.elements.push({ type: 'dialogue', text: dlg.join(' '), character, page }); dlg.length = 0 }
          cur.elements.push({ type: 'parenthetical', text: p, character, page })
        } else {
          dlg.push(l)
        }
        i++
      }
      if (dlg.length) cur.elements.push({ type: 'dialogue', text: dlg.join(' ').replace(/\s+/g, ' '), character, page })
      continue
    }

    if (actionBuf.length === 0) actionPage = page
    actionBuf.push(t.replace(/^!/, ''))
    i++
  }
  flushAction(actionBuf, actionPage)

  if (scenes.length === 0) {
    const text = lines.map((l) => l.text).join('\n').trim()
    if (text) {
      const s: ParsedScene = {
        sceneNo: '1', heading: 'UNTITLED SCENE', intExt: '', location: '', timeLabel: '',
        pageStart: 1, pageEnd: lines[lines.length - 1]?.page ?? 1,
        elements: [{ type: 'action', text: text.replace(/\s+/g, ' '), page: 1 }], characters: [], text,
      }
      scenes.push(s)
    }
  }

  for (const s of scenes) s.text = elementsToText(s.elements)
  return scenes
}

/** Serialise elements back into screenplay-formatted text that parseScreenplay can read again. */
export function elementsToText(els: ScriptElement[]): string {
  const out: string[] = []
  let prevDialogueChar: string | undefined
  for (const e of els) {
    switch (e.type) {
      case 'heading':
      case 'action':
      case 'transition':
        if (out.length && out[out.length - 1] !== '') out.push('')
        out.push(e.text, '')
        prevDialogueChar = undefined
        break
      case 'parenthetical':
      case 'dialogue': {
        if (prevDialogueChar !== e.character) {
          if (out.length && out[out.length - 1] !== '') out.push('')
          out.push(e.character ?? '')
          prevDialogueChar = e.character
        }
        out.push(e.text)
        break
      }
    }
  }
  return out.join('\n').replace(/\n{3,}/g, '\n\n').trim()
}

/** Extract lines from a PDF in the browser using pdf.js. */
export async function pdfToLines(data: ArrayBuffer): Promise<TextLine[]> {
  // Legacy build: includes polyfills so older browsers (and older Chromium) can parse PDFs.
  const pdfjs = await import('pdfjs-dist/legacy/build/pdf.mjs')
  pdfjs.GlobalWorkerOptions.workerSrc = new URL('pdfjs-dist/legacy/build/pdf.worker.min.mjs', import.meta.url).toString()
  const doc = await pdfjs.getDocument({ data }).promise
  const out: TextLine[] = []
  for (let p = 1; p <= doc.numPages; p++) {
    const page = await doc.getPage(p)
    const content = await page.getTextContent()
    type Item = { str: string; transform: number[]; height?: number; width?: number }
    const items = (content.items as unknown as Item[]).filter((it) => typeof it.str === 'string')
    const rows = new Map<number, { x: number; parts: { x: number; s: string }[]; h: number }>()
    for (const it of items) {
      const x = it.transform[4]
      const y = Math.round(it.transform[5] / 2) * 2
      const h = it.height || Math.abs(it.transform[3]) || 10
      let row = rows.get(y)
      if (!row) { row = { x, parts: [], h }; rows.set(y, row) }
      row.parts.push({ x, s: it.str })
      row.x = Math.min(row.x, x)
    }
    const ys = [...rows.keys()].sort((a, b) => b - a)
    let prevY: number | null = null
    let prevH = 10
    for (const y of ys) {
      const row = rows.get(y)!
      if (prevY !== null && prevY - y > prevH * 1.6) out.push({ text: '', page: p })
      row.parts.sort((a, b) => a.x - b.x)
      let text = ''
      let lastEnd = -Infinity
      for (const part of row.parts) {
        if (text && part.x - lastEnd > 2) text += ' '
        text += part.s
        lastEnd = part.x + part.s.length * (row.h * 0.5)
      }
      const line = text.replace(/\s+/g, ' ').trim()
      if (line) out.push({ text: line, page: p, x: row.x })
      prevY = y
      prevH = row.h
    }
    out.push({ text: '', page: p })
  }
  return out
}

/** Read any supported file (pdf, fountain, txt) into lines. Browser only. */
export async function fileToLines(file: File): Promise<TextLine[]> {
  if (file.type === 'application/pdf' || /\.pdf$/i.test(file.name)) {
    return pdfToLines(await file.arrayBuffer())
  }
  return textToLines(await file.text())
}
