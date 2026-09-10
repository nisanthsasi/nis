import type { CinematographerProfile, DirectorProfile, Lens, Movement, Project } from './types'
import { directorFromText, getDirector } from './directors'
import { dpFromText, getCinematographer } from './cinematographers'

/** Build a DP layer out of a director profile, for directors without a listed DP. */
export function dpFromDirector(d: DirectorProfile): CinematographerProfile {
  const [wide, long] = d.lensRange
  return {
    id: 'same', name: `${d.name}'s usual lensing`, region: d.region, era: d.era,
    summary: 'Lensing derived from the director profile.',
    format: d.lensCharacter === 'anamorphic' ? '35mm anamorphic' : d.lensCharacter === 'vintage' ? '35mm, vintage glass' : '35mm spherical',
    aspectRatio: d.aspectRatio, lensCharacter: d.lensCharacter,
    lensLadder: d.lensLadder ?? { wide, normal: Math.round((wide + long) / 2), long },
    lightingKey: d.lightingKey, lightingQuality: d.lightingQuality, palette: d.palette, colorTags: d.colorTags,
    camera: d.movements.includes('handheld') ? 'handheld' : d.movements.every((m) => m === 'static') ? 'locked' : 'fluid',
    depthOfField: d.lensCharacter === 'wide' ? 'deep' : d.lensCharacter === 'anamorphic' || d.lensCharacter === 'telephoto' ? 'shallow' : 'mixed',
    styleVocabulary: [], signature: [], knownFor: [],
  }
}

const uniq = <T,>(xs: T[]) => [...new Set(xs)]

/** Merge a director's grammar with a cinematographer's lensing. */
export function mergeLens(director: DirectorProfile, dp: CinematographerProfile): Lens {
  let movements: Movement[] = director.movements
  if (dp.camera === 'handheld') movements = uniq<Movement>(['handheld', ...director.movements])
  else if (dp.camera === 'locked') movements = director.movements.filter((m) => m !== 'handheld' && m !== 'steadicam')
  else if (dp.camera === 'fluid') movements = [...director.movements.filter((m) => m !== 'handheld'), ...director.movements.filter((m) => m === 'handheld')]
  if (!movements.length) movements = ['static']
  const own = dp.id === 'same'
  return {
    ...director,
    id: own ? director.id : `${director.id}+${dp.id}`,
    name: own ? director.name : `${director.name} × ${dp.name}`,
    directorName: director.name,
    dpName: dp.name,
    dp,
    movements,
    lensCharacter: dp.lensCharacter,
    lensLadder: dp.lensLadder,
    lensRange: [dp.lensLadder.wide, dp.lensLadder.long],
    format: dp.format,
    aspectRatio: dp.aspectRatio,
    lightingKey: dp.lightingKey,
    lightingQuality: dp.lightingQuality,
    palette: dp.palette,
    colorTags: uniq([...dp.colorTags, ...director.colorTags]).slice(0, 6),
    styleVocabulary: uniq([...director.styleVocabulary.slice(0, 6), ...dp.styleVocabulary.slice(0, 6)]),
  }
}

const cache = new Map<string, Lens>()

export function resolveDirectorProfile(p: Pick<Project, 'directorId' | 'customDirector'>): DirectorProfile {
  return p.directorId === 'custom' ? directorFromText(p.customDirector) : getDirector(p.directorId)
}

export function resolveDpProfile(p: Pick<Project, 'dpId' | 'customDp'>, director: DirectorProfile): CinematographerProfile {
  const dpId = p.dpId || 'same'
  if (dpId === 'custom') return dpFromText(p.customDp || '')
  if (dpId === 'same') {
    const usual = director.defaultDpId ? getCinematographer(director.defaultDpId) : undefined
    return usual ?? dpFromDirector(director)
  }
  return getCinematographer(dpId) ?? dpFromDirector(director)
}

/** The project's working lens. Memoised so selectors return stable references. */
export function resolveLens(p: Pick<Project, 'directorId' | 'customDirector' | 'dpId' | 'customDp'> | null): Lens {
  const proj = p ?? { directorId: 'me', customDirector: '', dpId: 'same', customDp: '' }
  const director = resolveDirectorProfile(proj)
  const dp = resolveDpProfile(proj, director)
  const key = `${director.id}|${director.summary}|${dp.id}|${dp.summary}`
  const hit = cache.get(key)
  if (hit) return hit
  const lens = mergeLens(director, dp)
  cache.set(key, lens)
  return lens
}
