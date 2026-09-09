import type { AspectRatio, DirectorProfile, Scene, Shot, ShotDraft } from '../types'
import { CAMERA_ANGLES, LENS_CHARACTERS, LIGHTING_KEYS, LIGHTING_QUALITIES, SHOT_SIZES, TIMES_OF_DAY } from '../taxonomy'

type SceneCtx = Pick<Scene, 'heading' | 'location' | 'intExt' | 'timeLabel'> | null | undefined

/** Turn a shot's taxonomy plus the director's vocabulary into an image prompt. */
export function buildPrompt(shot: Shot | ShotDraft, director: DirectorProfile, scene?: SceneCtx, aspect?: AspectRatio): string {
  const size = SHOT_SIZES.find((s) => s.value === shot.shotSize)
  const angle = CAMERA_ANGLES.find((a) => a.value === shot.cameraAngle)
  const lens = LENS_CHARACTERS.find((l) => l.value === shot.lensCharacter)
  const light = LIGHTING_KEYS.find((l) => l.value === shot.lightingKey)
  const quality = LIGHTING_QUALITIES.find((q) => q.value === shot.lightingQuality)
  const tod = TIMES_OF_DAY.find((t) => t.value === shot.timeOfDay)

  const parts: string[] = ['Cinematic film still.']
  const subj = shot.subject?.trim()
  parts.push(`${cap(size?.prompt ?? 'medium shot')}${subj ? ` of ${subj}` : ''}.`)
  if (shot.action?.trim()) parts.push(ensureDot(shot.action.trim()))
  const where = [scene?.intExt === 'INT' ? 'interior' : scene?.intExt === 'EXT' ? 'exterior' : '', scene?.location].filter(Boolean).join(', ')
  if (where) parts.push(`Setting: ${where}.`)
  if (tod && tod.value !== 'unspecified') parts.push(`Time: ${tod.label.toLowerCase()}.`)
  const cam: string[] = []
  if (angle && angle.value !== 'eye-level') cam.push(`${angle.label.toLowerCase()} camera`)
  if (shot.movement === 'handheld') cam.push('slight handheld energy')
  if (lens) cam.push(lens.prompt + (shot.lensMm ? ` around ${shot.lensMm}mm` : ''))
  if (cam.length) parts.push(cap(cam.join(', ')) + '.')
  const lt: string[] = []
  if (light) lt.push(light.prompt)
  if (quality) lt.push(`${quality.label.toLowerCase()} light`)
  if (lt.length) parts.push(cap(lt.join(', ')) + '.')
  if (shot.colorTags?.length) parts.push(`Palette: ${shot.colorTags.join(', ')}.`)
  if (director.styleVocabulary.length) parts.push(`Style: ${director.styleVocabulary.join(', ')}.`)
  parts.push(`Aspect ratio ${aspect ?? shot.aspectRatio ?? director.aspectRatio}.`)
  parts.push('Photorealistic, subtle film grain, natural skin, no text, no captions, no watermark, no logo.')
  return parts.join(' ')
}

/** A short FrameThrower query derived from the shot, for reference search. */
export function buildReferenceQuery(shot: Shot | ShotDraft, scene?: SceneCtx): string {
  const size = SHOT_SIZES.find((s) => s.value === shot.shotSize)?.label.toLowerCase() ?? ''
  const light = LIGHTING_KEYS.find((l) => l.value === shot.lightingKey)?.label.toLowerCase() ?? ''
  const tod = shot.timeOfDay !== 'unspecified' ? shot.timeOfDay.replace('-', ' ') : ''
  const where = scene?.location ? scene.location.toLowerCase() : ''
  const subj = (shot.subject || shot.action || '').split(/[.,]/)[0].slice(0, 60)
  return [size, subj, where, tod, light].filter(Boolean).join(', ')
}

function cap(s: string): string { return s.charAt(0).toUpperCase() + s.slice(1) }
function ensureDot(s: string): string { return /[.!?…]$/.test(s) ? s : s + '.' }
