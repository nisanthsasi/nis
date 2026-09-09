import type {
  AspectRatio, CameraAngle, LensCharacter, LightingKey, LightingQuality,
  Movement, ShotSize, TimeOfDay, ProviderId,
} from './types'

export const SHOT_SIZES: { value: ShotSize; label: string; prompt: string }[] = [
  { value: 'EWS', label: 'Extreme wide', prompt: 'extreme wide shot, figure small in a vast environment' },
  { value: 'WS', label: 'Wide', prompt: 'wide shot, full environment visible' },
  { value: 'FS', label: 'Full shot', prompt: 'full shot, head to toe' },
  { value: 'MWS', label: 'Medium wide', prompt: 'medium wide shot, knees up' },
  { value: 'MS', label: 'Medium', prompt: 'medium shot, waist up' },
  { value: 'MCU', label: 'Medium close-up', prompt: 'medium close-up, chest up' },
  { value: 'CU', label: 'Close-up', prompt: 'close-up on the face' },
  { value: 'ECU', label: 'Extreme close-up', prompt: 'extreme close-up, eyes or a detail filling the frame' },
  { value: 'INSERT', label: 'Insert', prompt: 'insert shot of an object, shallow focus' },
  { value: 'OTS', label: 'Over the shoulder', prompt: 'over-the-shoulder shot, foreground shoulder soft' },
  { value: 'TWO', label: 'Two shot', prompt: 'two shot, both characters in frame' },
  { value: 'POV', label: 'POV', prompt: 'point-of-view shot from the character\'s eyes' },
]

export const CAMERA_ANGLES: { value: CameraAngle; label: string }[] = [
  { value: 'eye-level', label: 'Eye level' },
  { value: 'low', label: 'Low angle' },
  { value: 'high', label: 'High angle' },
  { value: 'dutch', label: 'Dutch tilt' },
  { value: 'overhead', label: 'Overhead / top-down' },
  { value: 'worms-eye', label: "Worm's eye" },
  { value: 'shoulder-level', label: 'Shoulder level' },
  { value: 'hip-level', label: 'Hip level' },
  { value: 'ground-level', label: 'Ground level' },
]

export const MOVEMENTS: { value: Movement; label: string }[] = [
  { value: 'static', label: 'Static / locked off' },
  { value: 'pan', label: 'Pan' },
  { value: 'tilt', label: 'Tilt' },
  { value: 'push-in', label: 'Push in (dolly)' },
  { value: 'pull-back', label: 'Pull back (dolly)' },
  { value: 'tracking', label: 'Tracking / lateral' },
  { value: 'arc', label: 'Arc / orbit' },
  { value: 'crane', label: 'Crane / jib' },
  { value: 'handheld', label: 'Handheld' },
  { value: 'steadicam', label: 'Steadicam / gimbal' },
  { value: 'zoom', label: 'Zoom' },
  { value: 'whip-pan', label: 'Whip pan' },
  { value: 'drone', label: 'Drone / aerial' },
  { value: 'rack-focus', label: 'Rack focus' },
]

export const LENS_CHARACTERS: { value: LensCharacter; label: string; prompt: string }[] = [
  { value: 'spherical', label: 'Spherical', prompt: 'clean spherical lens' },
  { value: 'anamorphic', label: 'Anamorphic', prompt: 'anamorphic lens, oval bokeh, horizontal flares' },
  { value: 'vintage', label: 'Vintage glass', prompt: 'vintage lens, soft edges, gentle halation' },
  { value: 'wide', label: 'Wide angle', prompt: 'wide-angle lens, deep focus' },
  { value: 'telephoto', label: 'Telephoto', prompt: 'long telephoto lens, compressed perspective' },
  { value: 'macro', label: 'Macro', prompt: 'macro lens, razor-thin focus' },
  { value: 'tilt-shift', label: 'Tilt-shift', prompt: 'tilt-shift lens, selective plane of focus' },
  { value: 'fisheye', label: 'Fisheye', prompt: 'fisheye lens distortion' },
]

export const LIGHTING_KEYS: { value: LightingKey; label: string; prompt: string }[] = [
  { value: 'natural', label: 'Natural / available', prompt: 'natural available light' },
  { value: 'high-key', label: 'High key', prompt: 'high-key lighting, bright and even' },
  { value: 'low-key', label: 'Low key', prompt: 'low-key lighting, deep shadows' },
  { value: 'practical', label: 'Practicals', prompt: 'lit by practical lamps in frame' },
  { value: 'silhouette', label: 'Silhouette', prompt: 'silhouette against a bright background' },
  { value: 'chiaroscuro', label: 'Chiaroscuro', prompt: 'chiaroscuro, single hard source, dramatic falloff' },
  { value: 'neon', label: 'Neon', prompt: 'neon signage light, saturated color spill' },
  { value: 'golden-hour', label: 'Golden hour', prompt: 'warm golden-hour sunlight, long shadows' },
  { value: 'blue-hour', label: 'Blue hour', prompt: 'cool blue-hour ambient light' },
  { value: 'overcast', label: 'Overcast', prompt: 'flat overcast daylight' },
  { value: 'harsh-sun', label: 'Harsh sun', prompt: 'harsh midday sun, hard shadows' },
  { value: 'mixed', label: 'Mixed sources', prompt: 'mixed color temperature sources' },
]

export const LIGHTING_QUALITIES: { value: LightingQuality; label: string }[] = [
  { value: 'soft', label: 'Soft' },
  { value: 'hard', label: 'Hard' },
  { value: 'diffused', label: 'Diffused' },
  { value: 'motivated', label: 'Motivated' },
  { value: 'top-lit', label: 'Top lit' },
  { value: 'back-lit', label: 'Back lit' },
  { value: 'side-lit', label: 'Side lit' },
  { value: 'under-lit', label: 'Under lit' },
]

export const TIMES_OF_DAY: { value: TimeOfDay; label: string }[] = [
  { value: 'unspecified', label: 'Unspecified' },
  { value: 'dawn', label: 'Dawn' },
  { value: 'morning', label: 'Morning' },
  { value: 'day', label: 'Day' },
  { value: 'afternoon', label: 'Afternoon' },
  { value: 'golden-hour', label: 'Golden hour' },
  { value: 'dusk', label: 'Dusk' },
  { value: 'night', label: 'Night' },
]

export const ASPECT_RATIOS: { value: AspectRatio; label: string; ratio: number }[] = [
  { value: '16:9', label: '16:9 (1.78)', ratio: 16 / 9 },
  { value: '1.85:1', label: '1.85:1 Flat', ratio: 1.85 },
  { value: '2:1', label: '2:1 Univisium', ratio: 2 },
  { value: '2.39:1', label: '2.39:1 Scope', ratio: 2.39 },
  { value: '4:3', label: '4:3 Academy-ish', ratio: 4 / 3 },
  { value: '1:1', label: '1:1 Square', ratio: 1 },
  { value: '9:16', label: '9:16 Vertical', ratio: 9 / 16 },
]

export const COLOR_TAGS = [
  'warm', 'cool', 'desaturated', 'saturated', 'monochrome', 'teal-orange', 'pastel',
  'earth tones', 'amber', 'cyan', 'magenta', 'green', 'red accent', 'blue', 'sepia',
  'high contrast', 'low contrast', 'muted', 'neon', 'golden', 'bleach bypass',
]

export const PROVIDERS: { value: ProviderId; label: string; cost: string; note: string }[] = [
  { value: 'pollinations', label: 'Pollinations (free)', cost: 'Free, no key', note: 'FLUX model. One image per 15 s on the anonymous tier; small watermark unless you register a free account.' },
  { value: 'cloudflare', label: 'Cloudflare FLUX schnell (free tier)', cost: 'Free daily allowance', note: 'Needs a free Cloudflare account ID + API token in .env.' },
  { value: 'gemini', label: 'Gemini Nano Banana', cost: 'Free quota may apply', note: 'gemini-2.5-flash-image. Free-tier image quota varies by account. Supports reference images.' },
  { value: 'openai', label: 'OpenAI gpt-image-2', cost: '~$0.03 to $0.08 / image', note: 'Best prompt adherence, any aspect ratio, reference images via edits.' },
]

export function aspectToRatio(a: AspectRatio): number {
  return ASPECT_RATIOS.find((x) => x.value === a)?.ratio ?? 16 / 9
}

/** Map a FrameThrower metadata.shotType string onto our ShotSize */
export function mapShotType(s: string | null | undefined): ShotSize | null {
  if (!s) return null
  const t = s.toLowerCase()
  if (t.includes('extreme wide') || t.includes('establishing')) return 'EWS'
  if (t.includes('extreme close')) return 'ECU'
  if (t.includes('over') && t.includes('shoulder')) return 'OTS'
  if (t.includes('two')) return 'TWO'
  if (t.includes('insert') || t.includes('detail')) return 'INSERT'
  if (t.includes('pov') || t.includes('point of view')) return 'POV'
  if (t.includes('medium close')) return 'MCU'
  if (t.includes('close')) return 'CU'
  if (t.includes('medium wide') || t.includes('cowboy')) return 'MWS'
  if (t.includes('medium')) return 'MS'
  if (t.includes('full')) return 'FS'
  if (t.includes('wide') || t.includes('long')) return 'WS'
  return null
}

export function mapCameraAngle(s: string | null | undefined): CameraAngle | null {
  if (!s) return null
  const t = s.toLowerCase()
  if (t.includes('overhead') || t.includes('top') || t.includes('bird')) return 'overhead'
  if (t.includes('worm')) return 'worms-eye'
  if (t.includes('dutch') || t.includes('canted')) return 'dutch'
  if (t.includes('low')) return 'low'
  if (t.includes('high')) return 'high'
  if (t.includes('ground')) return 'ground-level'
  if (t.includes('hip')) return 'hip-level'
  if (t.includes('shoulder')) return 'shoulder-level'
  if (t.includes('eye')) return 'eye-level'
  return null
}

export function mapLensCharacter(s: string | null | undefined): LensCharacter | null {
  if (!s) return null
  const t = s.toLowerCase()
  if (t.includes('anamorphic')) return 'anamorphic'
  if (t.includes('vintage')) return 'vintage'
  if (t.includes('tele')) return 'telephoto'
  if (t.includes('macro')) return 'macro'
  if (t.includes('fish')) return 'fisheye'
  if (t.includes('tilt')) return 'tilt-shift'
  if (t.includes('wide')) return 'wide'
  if (t.includes('spherical') || t.includes('clean')) return 'spherical'
  return null
}

export function mapLightingKey(s: string | null | undefined): LightingKey | null {
  if (!s) return null
  const t = s.toLowerCase()
  if (t.includes('high')) return 'high-key'
  if (t.includes('low')) return 'low-key'
  if (t.includes('silhou')) return 'silhouette'
  if (t.includes('chiaro')) return 'chiaroscuro'
  if (t.includes('neon')) return 'neon'
  if (t.includes('golden')) return 'golden-hour'
  if (t.includes('blue hour')) return 'blue-hour'
  if (t.includes('overcast')) return 'overcast'
  if (t.includes('harsh') || t.includes('midday')) return 'harsh-sun'
  if (t.includes('practical')) return 'practical'
  if (t.includes('natural') || t.includes('available')) return 'natural'
  if (t.includes('mixed')) return 'mixed'
  return null
}

export function mapTimeOfDay(s: string | null | undefined): TimeOfDay | null {
  if (!s) return null
  const t = s.toLowerCase()
  if (t.includes('dawn') || t.includes('sunrise')) return 'dawn'
  if (t.includes('morning')) return 'morning'
  if (t.includes('golden') || t.includes('magic')) return 'golden-hour'
  if (t.includes('dusk') || t.includes('sunset') || t.includes('twilight') || t.includes('evening')) return 'dusk'
  if (t.includes('night')) return 'night'
  if (t.includes('afternoon')) return 'afternoon'
  if (t.includes('day')) return 'day'
  return null
}
