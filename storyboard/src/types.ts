// Core data model for the storyboard maker.
// No enums (erasableSyntaxOnly): string unions + const option lists in taxonomy.ts.

export type ShotSize =
  | 'EWS' | 'WS' | 'FS' | 'MWS' | 'MS' | 'MCU' | 'CU' | 'ECU'
  | 'INSERT' | 'OTS' | 'TWO' | 'POV'

export type CameraAngle =
  | 'eye-level' | 'low' | 'high' | 'dutch' | 'overhead' | 'worms-eye'
  | 'shoulder-level' | 'hip-level' | 'ground-level'

export type Movement =
  | 'static' | 'pan' | 'tilt' | 'push-in' | 'pull-back' | 'tracking' | 'arc'
  | 'crane' | 'handheld' | 'steadicam' | 'zoom' | 'whip-pan' | 'drone' | 'rack-focus'

export type LensCharacter =
  | 'spherical' | 'anamorphic' | 'vintage' | 'wide' | 'telephoto' | 'macro' | 'tilt-shift' | 'fisheye'

export type LightingKey =
  | 'high-key' | 'low-key' | 'natural' | 'practical' | 'silhouette' | 'chiaroscuro'
  | 'neon' | 'golden-hour' | 'blue-hour' | 'overcast' | 'harsh-sun' | 'mixed'

export type LightingQuality =
  | 'hard' | 'soft' | 'diffused' | 'motivated' | 'top-lit' | 'back-lit' | 'side-lit' | 'under-lit'

export type TimeOfDay =
  | 'dawn' | 'morning' | 'day' | 'afternoon' | 'golden-hour' | 'dusk' | 'night' | 'unspecified'

export type AspectRatio = '16:9' | '2.39:1' | '1.85:1' | '2:1' | '4:3' | '1:1' | '9:16'

export type FrameKind = 'reference' | 'generated' | 'upload'

export type ProviderId = 'pollinations' | 'cloudflare' | 'gemini' | 'openai'

export interface FrameCredit {
  film?: string | null
  year?: number | null
  director?: string | null
  dp?: string | null
  deepLink?: string | null
}

export interface Frame {
  id: string
  kind: FrameKind
  /** IndexedDB image id for uploads and generated frames */
  imageId?: string
  /** Remote URL for reference frames (never stored locally) */
  url?: string
  thumbUrl?: string
  credit?: FrameCredit
  /** Prompt used for generated frames */
  prompt?: string
  provider?: ProviderId
  seed?: number
  /** FrameThrower frame id, for "more like this" */
  sourceId?: string
  createdAt: number
}

export interface Shot {
  id: string
  sceneId: string
  shotNo: string
  shotSize: ShotSize
  cameraAngle: CameraAngle
  movement: Movement
  lensMm: number | null
  lensCharacter: LensCharacter
  lightingKey: LightingKey
  lightingQuality: LightingQuality
  timeOfDay: TimeOfDay
  colorTags: string[]
  /** null = inherit project aspect */
  aspectRatio: AspectRatio | null
  durationSec: number | null
  /** Subject / blocking, e.g. "MEERA at the window, back to camera" */
  subject: string
  action: string
  dialogue: string
  notes: string
  frames: Frame[]
  heroFrameId: string | null
}

export interface Scene {
  id: string
  sceneNo: string
  heading: string
  intExt: 'INT' | 'EXT' | 'INT/EXT' | ''
  location: string
  timeLabel: string
  synopsis: string
  /** Raw script text for this scene, if imported */
  scriptText: string
  characters: string[]
  shotIds: string[]
}

export interface ProjectSettings {
  pageSize: 'a4' | 'letter'
  framesPerPage: 2 | 4 | 6
  provider: ProviderId
  showCredits: boolean
}

export interface Project {
  id: string
  name: string
  directorId: string
  /** Free-text grammar when directorId === 'custom' */
  customDirector: string
  aspectRatio: AspectRatio
  scenes: Scene[]
  shots: Record<string, Shot>
  settings: ProjectSettings
  createdAt: number
  updatedAt: number
}

export type CoverageStyle =
  | 'classical' | 'long-take' | 'fragmented' | 'observational' | 'tableau' | 'kinetic'

export type Pacing = 'slow' | 'measured' | 'brisk' | 'frenetic'

export interface DirectorProfile {
  id: string
  name: string
  region: string
  era: string
  summary: string
  aspectRatio: AspectRatio
  coverageStyle: CoverageStyle
  /** Preferred shot sizes, most characteristic first */
  shotSizes: ShotSize[]
  angles: CameraAngle[]
  movements: Movement[]
  lensCharacter: LensCharacter
  /** [wide, long] focal length range in mm the director lives in */
  lensRange: [number, number]
  lightingKey: LightingKey
  lightingQuality: LightingQuality
  palette: string[]
  colorTags: string[]
  blocking: string
  pacing: Pacing
  averageShotSec: number
  /** Visual descriptors injected into image prompts (never the director's name) */
  styleVocabulary: string[]
  signatureMoves: string[]
  /** Name to pass to FrameThrower browse({ director }) */
  frameThrowerDirector?: string
}

/** A screenplay element produced by the parser */
export interface ScriptElement {
  type: 'action' | 'dialogue' | 'parenthetical' | 'transition' | 'heading'
  text: string
  character?: string
  page: number
}

export interface ParsedScene {
  sceneNo: string
  heading: string
  intExt: 'INT' | 'EXT' | 'INT/EXT' | ''
  location: string
  timeLabel: string
  pageStart: number
  pageEnd: number
  elements: ScriptElement[]
  characters: string[]
  text: string
}

/** Shot draft produced by the shot-list engines before it is given ids */
export type ShotDraft = Omit<Shot, 'id' | 'sceneId' | 'frames' | 'heroFrameId'> & {
  rationale?: string
}
