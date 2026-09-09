import { describe, it, expect } from 'vitest'
import { parseScreenplay, textToLines } from '../src/lib/screenplay'
import { generateShotList, timeLabelToTimeOfDay } from '../src/lib/shotlist'
import { getDirector } from '../src/directors'

const SCENE = `
INT. TEA SHOP - DAY

A cramped shop. ANAND wipes a glass. SUDHA enters with a wet umbrella.

SUDHA
You said you'd call.

ANAND
I did call.

SUDHA
Twice. In three weeks.

ANAND
(putting the glass down)
The shop doesn't run itself, Sudha. Every morning I open at five, every night I close at eleven, and in between I stand here and I think about calling you.

SUDHA
Then think louder.

She leaves. The umbrella stays.
`

describe('generateShotList', () => {
  const scene = parseScreenplay(textToLines(SCENE))[0]

  it('produces a numbered list with an opener and closer', () => {
    const shots = generateShotList(scene, getDirector('me'))
    expect(shots.length).toBeGreaterThanOrEqual(5)
    expect(shots.map((s) => s.shotNo)).toEqual(shots.map((_, i) => String(i + 1)))
    expect(['EWS', 'WS', 'MS', 'INSERT']).toContain(shots[0].shotSize)
    expect(shots.every((s) => s.timeOfDay === 'day')).toBe(true)
  })

  it('directs differently under different lenses', () => {
    const villeneuve = generateShotList(scene, getDirector('villeneuve'))
    const kashyap = generateShotList(scene, getDirector('kashyap'))
    const ozu = generateShotList(scene, getDirector('ozu'))
    // Long-take director covers the exchange in fewer, longer shots
    expect(villeneuve.length).toBeLessThan(kashyap.length)
    expect(villeneuve.some((s) => s.movement === 'push-in')).toBe(true)
    // Kinetic director is handheld
    expect(kashyap.filter((s) => s.movement === 'handheld').length).toBeGreaterThan(0)
    // Ozu never moves and lives on a 50mm
    expect(ozu.every((s) => s.movement === 'static')).toBe(true)
    expect(ozu.every((s) => s.lensMm === 50)).toBe(true)
    // Lens choices follow the director's range
    expect(villeneuve.every((s) => (s.lensMm ?? 0) >= 21 && (s.lensMm ?? 0) <= 50)).toBe(true)
  })

  it('inserts on a prop named in the action', () => {
    const shots = generateShotList(scene, getDirector('me'))
    const insert = shots.find((s) => s.shotSize === 'INSERT')
    expect(insert?.subject).toMatch(/umbrella|glass/)
  })

  it('caps the list at maxShots keeping the opener', () => {
    const shots = generateShotList(scene, getDirector('kashyap'), { maxShots: 4 })
    expect(shots).toHaveLength(4)
    expect(shots[0].shotNo).toBe('1')
  })

  it('maps time labels', () => {
    expect(timeLabelToTimeOfDay('NIGHT')).toBe('night')
    expect(timeLabelToTimeOfDay('MAGIC HOUR')).toBe('golden-hour')
    expect(timeLabelToTimeOfDay('CONTINUOUS')).toBe('unspecified')
  })
})
