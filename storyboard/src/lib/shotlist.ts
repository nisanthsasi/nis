import type {
  CameraAngle, DirectorProfile, LightingKey, LightingQuality, Movement, ParsedScene,
  ScriptElement, ShotDraft, ShotSize, TimeOfDay,
} from '../types'

export type SceneLike = Pick<ParsedScene, 'heading' | 'intExt' | 'location' | 'timeLabel' | 'elements' | 'characters'>

interface DialogueLine { character: string; text: string; parenthetical?: string }
type Beat =
  | { kind: 'action'; text: string; props: string[]; page: number }
  | { kind: 'dialogue'; lines: DialogueLine[]; page: number }

const PROP_WORDS = [
  'phone', 'mobile', 'letter', 'photo', 'photograph', 'knife', 'gun', 'pistol', 'key', 'keys', 'ring', 'watch',
  'clock', 'cigarette', 'glass', 'cup', 'bottle', 'door', 'window', 'mirror', 'book', 'diary', 'note', 'money',
  'cash', 'envelope', 'bag', 'suitcase', 'hand', 'hands', 'eyes', 'feet', 'blood', 'wound', 'lamp', 'candle',
  'flame', 'rain', 'ticket', 'card', 'map', 'radio', 'tv', 'television', 'screen', 'laptop', 'wallet', 'necklace',
  'bangle', 'saree', 'mundu', 'umbrella', 'lantern', 'bell', 'flower', 'tea', 'coffee', 'plate', 'food',
]

export function timeLabelToTimeOfDay(label: string): TimeOfDay {
  const t = label.toLowerCase()
  if (/pre-dawn|dawn|sunrise/.test(t)) return 'dawn'
  if (/morning/.test(t)) return 'morning'
  if (/magic|golden/.test(t)) return 'golden-hour'
  if (/dusk|sunset|evening|twilight/.test(t)) return 'dusk'
  if (/night|midnight/.test(t)) return 'night'
  if (/afternoon|noon/.test(t)) return 'afternoon'
  if (/day/.test(t)) return 'day'
  return 'unspecified'
}

export function deriveLighting(intExt: string, tod: TimeOfDay, d: DirectorProfile): { key: LightingKey; quality: LightingQuality } {
  if (tod === 'golden-hour' || tod === 'dusk' || tod === 'dawn') return { key: intExt === 'INT' ? d.lightingKey : 'golden-hour', quality: 'back-lit' }
  if (tod === 'night') {
    if (d.lightingKey === 'neon') return { key: 'neon', quality: 'soft' }
    return { key: intExt === 'EXT' ? 'low-key' : 'practical', quality: d.lightingQuality === 'hard' ? 'hard' : 'motivated' }
  }
  if (intExt === 'EXT') return { key: d.lightingKey === 'harsh-sun' || d.lightingKey === 'overcast' || d.lightingKey === 'golden-hour' ? d.lightingKey : 'natural', quality: d.lightingQuality }
  return { key: d.lightingKey === 'harsh-sun' || d.lightingKey === 'golden-hour' ? 'natural' : d.lightingKey, quality: d.lightingQuality }
}

function extractBeats(els: ScriptElement[]): Beat[] {
  const beats: Beat[] = []
  for (const e of els) {
    if (e.type === 'action') {
      const lower = e.text.toLowerCase()
      const props = PROP_WORDS.filter((w) => new RegExp(`\\b${w}\\b`).test(lower)).slice(0, 3)
      beats.push({ kind: 'action', text: e.text, props, page: e.page })
    } else if (e.type === 'dialogue' || e.type === 'parenthetical') {
      const last = beats[beats.length - 1]
      const line: DialogueLine = e.type === 'dialogue'
        ? { character: e.character ?? '', text: e.text }
        : { character: e.character ?? '', text: '', parenthetical: e.text }
      if (last && last.kind === 'dialogue') {
        const prev = last.lines[last.lines.length - 1]
        if (line.parenthetical && prev && prev.character === line.character && !prev.text) prev.parenthetical = line.parenthetical
        else if (line.parenthetical && prev && prev.character === line.character) prev.parenthetical = (prev.parenthetical ? prev.parenthetical + ' ' : '') + line.parenthetical
        else last.lines.push(line)
      } else {
        beats.push({ kind: 'dialogue', lines: [line], page: e.page })
      }
    }
  }
  return beats
}

function lensFor(size: ShotSize, d: DirectorProfile): number {
  const [w, l] = d.lensRange
  const mid = Math.round((w + l) / 2)
  switch (size) {
    case 'EWS': case 'WS': case 'POV': return w
    case 'FS': case 'MWS': case 'TWO': return Math.round((w + mid) / 2)
    case 'MS': case 'OTS': return mid
    case 'MCU': return Math.round((mid + l) / 2)
    default: return l
  }
}

function durationFor(size: ShotSize, d: DirectorProfile, mult = 1): number {
  const base = d.averageShotSec
  const f = size === 'EWS' || size === 'WS' ? 1.4 : size === 'CU' || size === 'ECU' || size === 'INSERT' ? 0.8 : 1
  return Math.max(1, Math.round(base * f * mult))
}

function pick<T>(arr: T[], i: number, fallback: T): T { return arr.length ? arr[i % arr.length] : fallback }

function truncate(s: string, n = 180): string { return s.length > n ? s.slice(0, n - 1).trimEnd() + '…' : s }

interface Ctx {
  d: DirectorProfile
  tod: TimeOfDay
  light: { key: LightingKey; quality: LightingQuality }
  scene: SceneLike
  n: number
}

interface Draft extends ShotDraft { priority: number }

function make(ctx: Ctx, partial: Partial<ShotDraft> & { shotSize: ShotSize; priority?: number }): Draft {
  const { d } = ctx
  const size = partial.shotSize
  ctx.n++
  return {
    shotNo: String(ctx.n),
    shotSize: size,
    cameraAngle: partial.cameraAngle ?? pick(d.angles, 0, 'eye-level'),
    movement: partial.movement ?? pick(d.movements, 0, 'static'),
    lensMm: partial.lensMm ?? lensFor(size, d),
    lensCharacter: d.lensCharacter,
    lightingKey: partial.lightingKey ?? ctx.light.key,
    lightingQuality: partial.lightingQuality ?? ctx.light.quality,
    timeOfDay: ctx.tod,
    colorTags: [...d.colorTags],
    aspectRatio: null,
    durationSec: partial.durationSec ?? durationFor(size, d),
    subject: partial.subject ?? '',
    action: partial.action ?? '',
    dialogue: partial.dialogue ?? '',
    notes: partial.notes ?? '',
    rationale: partial.rationale,
    priority: partial.priority ?? 2,
  }
}

function opener(ctx: Ctx, firstAction?: string): Draft {
  const { d, scene } = ctx
  const where = [scene.intExt, scene.location].filter(Boolean).join(' ')
  const base = { subject: where || scene.heading, action: firstAction ? truncate(firstAction) : `Establish ${scene.location || 'the space'}.`, priority: 0 }
  switch (d.coverageStyle) {
    case 'tableau': return make(ctx, { ...base, shotSize: 'WS', movement: 'static', cameraAngle: pick(d.angles, 0, 'eye-level'), rationale: 'Tableau opener: symmetrical wide, hold.' })
    case 'long-take': return make(ctx, { ...base, shotSize: 'WS', movement: pick(d.movements, 0, 'push-in'), durationSec: durationFor('WS', d, 1.5), rationale: 'Long-take opener: drift into the space.' })
    case 'kinetic': return make(ctx, { ...base, shotSize: 'MS', movement: 'handheld', cameraAngle: pick(d.angles, 1, 'low'), rationale: 'Kinetic opener: already moving when we arrive.' })
    case 'observational': return make(ctx, { ...base, shotSize: 'WS', movement: 'static', rationale: 'Observational opener: wide, let the space breathe.' })
    case 'fragmented': return make(ctx, { ...base, shotSize: 'INSERT', movement: 'static', subject: 'A detail of the space', rationale: 'Fragmented opener: arrive on a detail before the geography.' })
    default: return make(ctx, { ...base, shotSize: scene.intExt === 'EXT' ? 'EWS' : 'WS', movement: pick(d.movements.filter((m) => m !== 'handheld'), 0, 'static'), rationale: 'Classical establishing shot.' })
  }
}

function actionShots(ctx: Ctx, beat: Extract<Beat, { kind: 'action' }>, idx: number): Draft[] {
  const { d } = ctx
  const out: Draft[] = []
  const chars = ctx.scene.characters.filter((c) => beat.text.toUpperCase().includes(c))
  const subject = chars.slice(0, 2).join(' and ') || 'Action'
  if (beat.props.length) {
    out.push(make(ctx, { shotSize: 'INSERT', movement: 'static', subject: beat.props.join(', '), action: truncate(beat.text), priority: 3, rationale: `Insert on ${beat.props[0]} named in the action.` }))
  }
  if (d.coverageStyle === 'long-take') {
    out.push(make(ctx, { shotSize: 'MS', movement: pick(d.movements, 1, 'tracking'), subject, action: truncate(beat.text), durationSec: durationFor('MS', d, 1.5), priority: 2, rationale: 'One moving shot carries the whole action beat.' }))
  } else if (d.coverageStyle === 'kinetic') {
    out.push(make(ctx, { shotSize: idx % 2 ? 'CU' : 'MS', movement: 'handheld', cameraAngle: pick(d.angles, idx, 'eye-level'), subject, action: truncate(beat.text), priority: 2, rationale: 'Handheld, inside the action.' }))
  } else if (!beat.props.length || beat.text.length > 120) {
    out.push(make(ctx, { shotSize: idx % 2 ? 'MS' : 'FS', movement: pick(d.movements, idx, 'static'), subject, action: truncate(beat.text), priority: 2, rationale: 'Action beat in a body-height frame.' }))
  }
  return out
}

function dialogueShots(ctx: Ctx, beat: Extract<Beat, { kind: 'dialogue' }>, sceneProgress: number): Draft[] {
  const { d } = ctx
  const speakers = [...new Set(beat.lines.map((l) => l.character).filter(Boolean))]
  const counts = new Map<string, number>()
  for (const l of beat.lines) counts.set(l.character, (counts.get(l.character) ?? 0) + l.text.length)
  const longest = beat.lines.reduce((a, b) => (b.text.length > a.text.length ? b : a), beat.lines[0])
  const listener = speakers.length > 1 ? [...counts.entries()].sort((a, b) => a[1] - b[1])[0][0] : speakers[0]
  const firstLine = beat.lines.find((l) => l.text)
  const dlg = firstLine ? `${firstLine.character}: ${truncate(firstLine.text, 120)}` : ''
  const peakDlg = longest ? `${longest.character}: ${truncate(longest.text, 120)}` : ''
  const exchanges = beat.lines.filter((l) => l.text).length
  const late = sceneProgress > 0.5
  const out: Draft[] = []
  const two = speakers.length === 2
  const pair = speakers.slice(0, 2).join(' / ')

  switch (d.coverageStyle) {
    case 'long-take': {
      out.push(make(ctx, { shotSize: two ? 'TWO' : speakers.length > 2 ? 'WS' : 'MS', movement: 'push-in', subject: speakers.join(', '), dialogue: dlg, durationSec: Math.max(d.averageShotSec, exchanges * 3), priority: 1, rationale: 'Whole exchange in one slowly tightening shot.' }))
      if (exchanges >= 6) out.push(make(ctx, { shotSize: 'CU', movement: 'static', subject: longest.character, dialogue: peakDlg, priority: 1, rationale: 'Land on the face at the emotional peak.' }))
      break
    }
    case 'fragmented': {
      for (const s of speakers.slice(0, 3)) out.push(make(ctx, { shotSize: 'CU', movement: pick(d.movements, 0, 'handheld'), subject: s, dialogue: dlg, priority: 1, rationale: 'Close, partial, obstructed.' }))
      out.push(make(ctx, { shotSize: 'INSERT', movement: 'static', subject: 'Hands / object between them', priority: 3, rationale: 'Detail carries the subtext.' }))
      if (late) out.push(make(ctx, { shotSize: 'ECU', movement: 'static', subject: `${longest.character} eyes`, dialogue: peakDlg, priority: 1, rationale: 'Peak on the eyes.' }))
      break
    }
    case 'observational': {
      out.push(make(ctx, { shotSize: two ? 'TWO' : 'WS', movement: 'static', subject: speakers.join(', '), dialogue: dlg, durationSec: Math.max(d.averageShotSec, exchanges * 2), priority: 1, rationale: 'Hold the wide; let behaviour play.' }))
      if (exchanges >= 3) out.push(make(ctx, { shotSize: 'MCU', movement: pick(d.movements, 0, 'handheld'), subject: listener, dialogue: peakDlg, priority: 2, rationale: 'One reaction from the listener.' }))
      break
    }
    case 'tableau': {
      if (speakers.length > 1) out.push(make(ctx, { shotSize: 'WS', movement: 'static', subject: speakers.join(', '), dialogue: dlg, priority: 1, rationale: 'Frontal master.' }))
      for (const s of speakers.slice(0, 3)) out.push(make(ctx, { shotSize: late ? 'MCU' : 'MS', movement: 'static', cameraAngle: pick(d.angles, 0, 'eye-level'), subject: `${s}, frontal`, dialogue: s === longest.character ? peakDlg : '', priority: 1, rationale: 'Matched frontal single.' }))
      break
    }
    case 'kinetic': {
      for (const s of speakers.slice(0, 3)) out.push(make(ctx, { shotSize: late ? 'CU' : 'MCU', movement: 'handheld', cameraAngle: pick(d.angles, 1, 'eye-level'), subject: s, dialogue: s === longest.character ? peakDlg : dlg, priority: 1, rationale: 'Handheld single, breathing with the actor.' }))
      if (two && exchanges >= 4) out.push(make(ctx, { shotSize: 'OTS', movement: 'whip-pan', subject: pair, priority: 3, rationale: 'Snap between them at the peak.' }))
      break
    }
    default: {
      out.push(make(ctx, { shotSize: two ? 'TWO' : speakers.length > 2 ? 'WS' : 'MS', movement: pick(d.movements.filter((m) => m !== 'handheld'), 0, 'static'), subject: speakers.join(', '), dialogue: dlg, priority: 1, rationale: 'Master for the exchange.' }))
      if (two) {
        out.push(make(ctx, { shotSize: 'OTS', subject: `${speakers[0]} over ${speakers[1]}`, dialogue: dlg, priority: 1, rationale: 'Coverage A.' }))
        out.push(make(ctx, { shotSize: 'OTS', subject: `${speakers[1]} over ${speakers[0]}`, priority: 1, rationale: 'Coverage B.' }))
        if (exchanges >= 4 || late) {
          out.push(make(ctx, { shotSize: 'CU', subject: longest.character, dialogue: peakDlg, movement: 'push-in', priority: 1, rationale: 'Tighten on the speaker at the peak.' }))
          out.push(make(ctx, { shotSize: 'CU', subject: listener, priority: 2, rationale: 'Reaction.' }))
        }
      } else {
        for (const s of speakers.slice(0, 3)) out.push(make(ctx, { shotSize: 'MCU', subject: s, dialogue: s === longest.character ? peakDlg : '', priority: 1, rationale: 'Single.' }))
      }
    }
  }
  return out
}

function closer(ctx: Ctx, lastSpeaker?: string): Draft {
  const { d, scene } = ctx
  switch (d.coverageStyle) {
    case 'tableau': return make(ctx, { shotSize: 'WS', movement: 'static', subject: `Empty ${scene.location || 'room'} after they leave`, priority: 2, rationale: 'Pillow shot out.' })
    case 'long-take': return make(ctx, { shotSize: 'CU', movement: 'static', subject: lastSpeaker || scene.characters[0] || 'Face', priority: 2, durationSec: durationFor('CU', d, 1.5), rationale: 'Hold the last face past comfort.' })
    case 'kinetic': return make(ctx, { shotSize: 'WS', movement: 'pull-back', subject: scene.location || 'The space', priority: 2, rationale: 'Release: pull out of the chaos.' })
    default: return make(ctx, { shotSize: 'CU', movement: 'static', subject: lastSpeaker || scene.characters[0] || 'Reaction', priority: 2, rationale: 'Button on a reaction.' })
  }
}

export interface ShotListOptions { maxShots?: number }

/** Offline rule engine: a parsed scene plus a director profile becomes a shot list. */
export function generateShotList(scene: SceneLike, d: DirectorProfile, opts: ShotListOptions = {}): ShotDraft[] {
  const maxShots = opts.maxShots ?? 14
  const tod = timeLabelToTimeOfDay(scene.timeLabel)
  const ctx: Ctx = { d, tod, light: deriveLighting(scene.intExt, tod, d), scene, n: 0 }
  const beats = extractBeats(scene.elements)
  const drafts: Draft[] = []

  const firstAction = beats[0]?.kind === 'action' ? beats[0].text : undefined
  drafts.push(opener(ctx, firstAction))

  let lastSpeaker: string | undefined
  beats.forEach((b, i) => {
    const progress = beats.length > 1 ? i / (beats.length - 1) : 1
    if (b.kind === 'action') {
      if (i === 0 && firstAction && !b.props.length) return // opener already carries it
      drafts.push(...actionShots(ctx, b, i))
    } else {
      drafts.push(...dialogueShots(ctx, b, progress))
      lastSpeaker = b.lines[b.lines.length - 1]?.character
    }
  })
  if (beats.length > 0) drafts.push(closer(ctx, lastSpeaker))

  // Trim to maxShots by dropping lowest priority first, preserving order.
  let list = drafts
  if (list.length > maxShots) {
    const order = list.map((s, i) => ({ s, i }))
    const keep = new Set<number>()
    for (const pr of [0, 1, 2, 3, 4]) {
      for (const { s, i } of order) {
        if (s.priority === pr && keep.size < maxShots) keep.add(i)
      }
    }
    list = order.filter(({ i }) => keep.has(i)).map(({ s }) => s)
  }
  return list.map((s, i) => {
    const { priority: _p, ...rest } = s
    void _p
    return { ...rest, shotNo: String(i + 1) }
  })
}

/** Default draft for a blank shot, seeded by the director profile. */
export function blankShot(d: DirectorProfile, shotNo: string): ShotDraft {
  const size: ShotSize = d.shotSizes[0] ?? 'MS'
  const angle: CameraAngle = d.angles[0] ?? 'eye-level'
  const move: Movement = d.movements[0] ?? 'static'
  return {
    shotNo, shotSize: size, cameraAngle: angle, movement: move, lensMm: lensFor(size, d), lensCharacter: d.lensCharacter,
    lightingKey: d.lightingKey, lightingQuality: d.lightingQuality, timeOfDay: 'unspecified', colorTags: [...d.colorTags],
    aspectRatio: null, durationSec: d.averageShotSec, subject: '', action: '', dialogue: '', notes: '',
  }
}
