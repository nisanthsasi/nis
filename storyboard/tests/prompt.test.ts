import { describe, it, expect } from 'vitest'
import { buildPrompt, buildReferenceQuery } from '../src/lib/prompt'
import { blankShot } from '../src/lib/shotlist'
import { getDirector } from '../src/directors'
import { mapShotType, mapLightingKey, mapLensCharacter } from '../src/taxonomy'

describe('buildPrompt', () => {
  it('describes the shot without naming the director', () => {
    const d = getDirector('wong-kar-wai')
    const shot = { ...blankShot(d, '1'), subject: 'SU LI-ZHEN in a red cheongsam', action: 'She waits by the noodle stall.', lightingKey: 'neon' as const }
    const p = buildPrompt(shot, d, { heading: '', location: 'Hong Kong alley', intExt: 'EXT', timeLabel: 'NIGHT' }, '1.85:1')
    expect(p).toContain('SU LI-ZHEN')
    expect(p).toContain('neon')
    expect(p).toContain('Aspect ratio 1.85:1')
    expect(p).not.toContain('Wong')
    expect(p).toMatch(/no watermark/)
  })

  it('builds a short reference query', () => {
    const d = getDirector('villeneuve')
    const q = buildReferenceQuery({ ...blankShot(d, '1'), subject: 'A lone figure', timeOfDay: 'dusk' }, { heading: '', location: 'Desert', intExt: 'EXT', timeLabel: 'DUSK' })
    expect(q).toContain('lone figure')
    expect(q).toContain('desert')
    expect(q.length).toBeLessThan(160)
  })
})

describe('FrameThrower metadata mapping', () => {
  it('maps shot types', () => {
    expect(mapShotType('Extreme Wide Shot')).toBe('EWS')
    expect(mapShotType('Medium Close-Up')).toBe('MCU')
    expect(mapShotType('close-up')).toBe('CU')
    expect(mapShotType('over the shoulder')).toBe('OTS')
    expect(mapShotType(null)).toBeNull()
  })
  it('maps lighting and lens', () => {
    expect(mapLightingKey('Low Key')).toBe('low-key')
    expect(mapLightingKey('golden hour sun')).toBe('golden-hour')
    expect(mapLensCharacter('Anamorphic')).toBe('anamorphic')
  })
})
