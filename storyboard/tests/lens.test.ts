import { describe, it, expect } from 'vitest'
import { mergeLens, resolveLens, dpFromDirector } from '../src/lens'
import { getDirector, DIRECTORS } from '../src/directors'
import { CINEMATOGRAPHERS, getCinematographer, dpFromText } from '../src/cinematographers'
import { generateShotList } from '../src/lib/shotlist'
import { parseScreenplay, textToLines } from '../src/lib/screenplay'
import { buildPrompt } from '../src/lib/prompt'
import { blankShot } from '../src/lib/shotlist'

const SCENE = parseScreenplay(textToLines(`INT. TEA SHOP - DAY

ANAND wipes a glass. SUDHA enters.

SUDHA
You said you'd call.

ANAND
I did call.

SUDHA
Twice. In three weeks. Every morning you open at five and every night you close at eleven and in between you never once think of me.

She leaves.
`))[0]

describe('director / cinematographer split', () => {
  it('every listed default DP exists', () => {
    for (const d of DIRECTORS) if (d.defaultDpId) expect(getCinematographer(d.defaultDpId), `${d.name} -> ${d.defaultDpId}`).toBeDefined()
  })

  it('resolves the usual DP for a director and derives one when none is listed', () => {
    const mani = resolveLens({ directorId: 'mani-ratnam', customDirector: '', dpId: 'same', customDp: '' })
    expect(mani.dpName).toBe('Santosh Sivan')
    expect(mani.name).toBe('Mani Ratnam × Santosh Sivan')
    const ozu = resolveLens({ directorId: 'ozu', customDirector: '', dpId: 'same', customDp: '' })
    expect(ozu.dp.id).toBe('same')
    expect(ozu.lensLadder).toEqual({ wide: 50, normal: 50, long: 50 })
  })

  it('the DP overrides lensing and light, the director keeps coverage and pacing', () => {
    const inarritu = getDirector('inarritu')
    const deakins = getCinematographer('deakins')!
    const lens = mergeLens(inarritu, deakins)
    expect(lens.coverageStyle).toBe('long-take')
    expect(lens.pacing).toBe(inarritu.pacing)
    expect(lens.lensCharacter).toBe('spherical')
    expect(lens.lensRange).toEqual([27, 75])
    expect(lens.lightingKey).toBe('natural')
    expect(lens.format).toBe(deakins.format)
    // Deakins is not a handheld DP: his temperament demotes handheld below the director's other moves
    expect(lens.movements[0]).not.toBe('handheld')
    expect(mergeLens(inarritu, getCinematographer('cronenweth')!).movements).not.toContain('handheld')
    const withLubezki = mergeLens(inarritu, getCinematographer('lubezki')!)
    expect(withLubezki.movements[0]).toBe('handheld')
  })

  it('same director, two DPs, different lenses on the same scene', () => {
    const spielberg = getDirector('spielberg')
    const a = generateShotList(SCENE, mergeLens(spielberg, getCinematographer('kaminski')!))
    const b = generateShotList(SCENE, mergeLens(spielberg, getCinematographer('lubezki')!))
    // Same coverage plan (same director), different glass
    expect(a.map((s) => s.shotSize)).toEqual(b.map((s) => s.shotSize))
    expect(a.map((s) => s.lensMm)).not.toEqual(b.map((s) => s.lensMm))
    expect(b.every((s) => (s.lensMm ?? 99) <= 35)).toBe(true)
    expect(a.some((s) => s.lightingQuality === 'back-lit')).toBe(true)
  })

  it('same DP, two directors, different coverage on the same scene', () => {
    const lubezki = getCinematographer('lubezki')!
    const cuaron = generateShotList(SCENE, mergeLens(getDirector('cuaron'), lubezki))
    const inarritu = generateShotList(SCENE, mergeLens(getDirector('inarritu'), lubezki))
    const kurosawa = generateShotList(SCENE, mergeLens(getDirector('kurosawa'), getCinematographer('asakazu-nakai')!))
    expect(cuaron.length).toBeLessThanOrEqual(inarritu.length + 1)
    expect(kurosawa.every((s) => (s.lensMm ?? 0) >= 50)).toBe(true)
    expect(kurosawa.length).toBeGreaterThan(cuaron.length)
  })

  it('prompts carry both vocabularies and never the names', () => {
    const lens = resolveLens({ directorId: 'wong-kar-wai', customDirector: '', dpId: 'doyle', customDp: '' })
    const p = buildPrompt(blankShot(lens, '1'), lens, null, '1.85:1')
    expect(p).toMatch(/step-printed/)
    expect(p).toMatch(/obstruction/)
    expect(p).not.toMatch(/Wong|Doyle/)
  })

  it('custom lensing text is parsed', () => {
    const dp = dpFromText('Alexa 65 large format, 24mm 40mm 75mm, anamorphic, low key practicals, teal-orange, handheld, shallow focus, 2.39 scope')
    expect(dp.lensLadder).toEqual({ wide: 24, normal: 40, long: 75 })
    expect(dp.lensCharacter).toBe('anamorphic')
    expect(dp.format).toMatch(/65/)
    expect(dp.lightingKey).toBe('low-key')
    expect(dp.camera).toBe('handheld')
    expect(dp.depthOfField).toBe('shallow')
    expect(dp.colorTags).toContain('teal-orange')
    expect(dp.aspectRatio).toBe('2.39:1')
  })

  it('every cinematographer profile is internally consistent', () => {
    for (const c of CINEMATOGRAPHERS) {
      expect(c.lensLadder.wide, c.name).toBeLessThanOrEqual(c.lensLadder.normal)
      expect(c.lensLadder.normal, c.name).toBeLessThanOrEqual(c.lensLadder.long)
      expect(c.styleVocabulary.length, c.name).toBeGreaterThanOrEqual(4)
    }
    const derived = dpFromDirector(getDirector('tarkovsky'))
    expect(derived.id).toBe('same')
  })
})
