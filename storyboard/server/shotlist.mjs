// Optional: Claude writes the shot breakdown when ANTHROPIC_API_KEY is set.
// Structured output via output_config.format so the result is always a valid shot list.
import { z } from 'zod'

export const claudeEnabled = Boolean(process.env.ANTHROPIC_API_KEY)

const ShotSchema = z.object({
  shotNo: z.string(),
  shotSize: z.enum(['EWS', 'WS', 'FS', 'MWS', 'MS', 'MCU', 'CU', 'ECU', 'INSERT', 'OTS', 'TWO', 'POV']),
  cameraAngle: z.enum(['eye-level', 'low', 'high', 'dutch', 'overhead', 'worms-eye', 'shoulder-level', 'hip-level', 'ground-level']),
  movement: z.enum(['static', 'pan', 'tilt', 'push-in', 'pull-back', 'tracking', 'arc', 'crane', 'handheld', 'steadicam', 'zoom', 'whip-pan', 'drone', 'rack-focus']),
  lensMm: z.number().int().min(8).max(400),
  lensCharacter: z.enum(['spherical', 'anamorphic', 'vintage', 'wide', 'telephoto', 'macro', 'tilt-shift', 'fisheye']),
  lightingKey: z.enum(['high-key', 'low-key', 'natural', 'practical', 'silhouette', 'chiaroscuro', 'neon', 'golden-hour', 'blue-hour', 'overcast', 'harsh-sun', 'mixed']),
  lightingQuality: z.enum(['hard', 'soft', 'diffused', 'motivated', 'top-lit', 'back-lit', 'side-lit', 'under-lit']),
  timeOfDay: z.enum(['dawn', 'morning', 'day', 'afternoon', 'golden-hour', 'dusk', 'night', 'unspecified']),
  colorTags: z.array(z.string()).max(6),
  durationSec: z.number().int().min(1).max(180),
  subject: z.string(),
  action: z.string(),
  dialogue: z.string(),
  notes: z.string(),
  rationale: z.string(),
})

export const ShotListSchema = z.object({
  sceneSummary: z.string(),
  shots: z.array(ShotSchema).min(1).max(20),
})

const SYSTEM = `You are a working film director and storyboard supervisor breaking a screenplay scene into a shot list.
You will be given the scene text and a "director lens": a description of the visual grammar to direct in (coverage habits, lenses, light, movement, palette, pacing). Direct the scene in that grammar without imitating any specific film.
Rules:
- Every shot must earn its place: coverage follows the emotional logic of the scene, not a template.
- Respect the lens: shot sizes, movement, lighting and pacing must be consistent with it.
- subject = who/what is in frame and how they are placed. action = what happens in the shot. dialogue = the line(s) it covers, prefixed by character name, or empty.
- notes = a crisp instruction to the DP / storyboard artist. rationale = one sentence on why this shot exists.
- lensMm should sit inside the lens range of the director lens. durationSec is an estimate.
- Keep to between 4 and 16 shots for a typical scene. Number shots from 1.`

let clientPromise = null
async function getClient() {
  if (!clientPromise) {
    clientPromise = import('@anthropic-ai/sdk').then((m) => new m.default())
  }
  return clientPromise
}

export async function claudeShotList({ scene, director, aspectRatio }) {
  if (!claudeEnabled) { const e = new Error('Claude is not configured'); e.status = 404; throw e }
  const [client, { zodOutputFormat }] = await Promise.all([getClient(), import('@anthropic-ai/sdk/helpers/zod')])

  const lens = [
    `Name: ${director.name}`,
    `Summary: ${director.summary}`,
    `Coverage style: ${director.coverageStyle}; pacing: ${director.pacing}; average shot ~${director.averageShotSec}s`,
    `Preferred sizes: ${director.shotSizes.join(', ')}; angles: ${director.angles.join(', ')}; movements: ${director.movements.join(', ')}`,
    `Lens: ${director.lensCharacter}, ${director.lensRange[0]}-${director.lensRange[1]}mm; aspect ${aspectRatio || director.aspectRatio}`,
    `Light: ${director.lightingKey}, ${director.lightingQuality}; palette tags: ${director.colorTags.join(', ')}`,
    `Blocking: ${director.blocking}`,
    `Signature moves: ${director.signatureMoves.join('; ')}`,
  ].join('\n')

  const user = `DIRECTOR LENS\n${lens}\n\nSCENE\n${scene.heading}\n${scene.text}\n\nCharacters: ${(scene.characters || []).join(', ') || 'unknown'}`

  const response = await client.beta.messages.create({
    model: 'claude-opus-5',
    max_tokens: 16000,
    thinking: { type: 'adaptive' },
    betas: ['server-side-fallback-2026-07-01'],
    fallbacks: 'default',
    system: SYSTEM,
    messages: [{ role: 'user', content: user }],
    output_config: { format: zodOutputFormat(ShotListSchema) },
  })

  if (response.stop_reason === 'refusal') {
    const e = new Error(`Claude declined: ${response.stop_details?.explanation || response.stop_details?.category || 'refusal'}`)
    e.status = 422
    throw e
  }
  const text = response.content.filter((b) => b.type === 'text').map((b) => b.text).join('')
  let parsed
  try { parsed = ShotListSchema.parse(JSON.parse(text)) } catch (err) {
    const e = new Error(`Claude returned an unexpected shape: ${err.message}`)
    e.status = 502
    throw e
  }
  return { ...parsed, model: response.model }
}
