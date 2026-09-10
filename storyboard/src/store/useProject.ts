import { create } from 'zustand'
import type { AspectRatio, Frame, Lens, Project, ProjectSettings, ParsedScene, Scene, Shot, ShotDraft, ShotVariant } from '../types'
import { uid } from '../lib/id'
import { resolveLens } from '../lens'
import { blankShot, generateShotList } from '../lib/shotlist'
import * as dbApi from './db'

export type RightTab = 'shot' | 'refs' | 'generate'
export type LeftTab = 'scenes' | 'script' | 'director'

interface UIState {
  rightTab: RightTab
  leftTab: LeftTab
  toast: { kind: 'info' | 'error'; text: string } | null
}

export interface ProviderStatus {
  pollinations: boolean
  cloudflare: boolean
  gemini: boolean
  openai: boolean
  framethrower: boolean
  claude: boolean
}

interface State {
  project: Project | null
  projects: dbApi.ProjectMeta[]
  selectedSceneId: string | null
  selectedShotId: string | null
  ui: UIState
  providers: ProviderStatus | null
  // project lifecycle
  refreshProjects: () => Promise<void>
  newProject: (name?: string) => Promise<void>
  openProject: (id: string) => Promise<void>
  deleteProject: (id: string) => Promise<void>
  importProject: (p: Project) => Promise<void>
  // project fields
  setProject: (patch: Partial<Project>) => void
  setSettings: (patch: Partial<ProjectSettings>) => void
  setDirector: (id: string, customText?: string) => void
  setDp: (id: string, customText?: string) => void
  setAspect: (a: AspectRatio) => void
  // scenes
  addScene: (partial?: Partial<Scene>) => string
  updateScene: (id: string, patch: Partial<Scene>) => void
  removeScene: (id: string) => void
  moveScene: (from: number, to: number) => void
  importScenes: (parsed: ParsedScene[], opts?: { generateShots: boolean }) => void
  // shots
  addShot: (sceneId: string, draft?: Partial<ShotDraft>, index?: number) => string
  addShotsFromDrafts: (sceneId: string, drafts: ShotDraft[], replace?: boolean) => void
  /** Replace a scene's shots with new drafts, saving the current list as a variant first. */
  redirectScene: (sceneId: string, drafts: ShotDraft[]) => void
  // variants
  saveVariant: (sceneId: string, label?: string) => void
  restoreVariant: (sceneId: string, variantId: string) => void
  deleteVariant: (sceneId: string, variantId: string) => void
  renameVariant: (sceneId: string, variantId: string, label: string) => void
  copyVariantShot: (sceneId: string, variantId: string, shotId: string) => void
  updateShot: (id: string, patch: Partial<Shot>) => void
  removeShot: (id: string) => void
  duplicateShot: (id: string) => void
  moveShot: (sceneId: string, from: number, to: number) => void
  // frames
  addFrame: (shotId: string, frame: Omit<Frame, 'id' | 'createdAt'>, makeHero?: boolean) => string
  removeFrame: (shotId: string, frameId: string) => void
  setHero: (shotId: string, frameId: string) => void
  // selection / ui
  selectScene: (id: string | null) => void
  selectShot: (id: string | null) => void
  setRightTab: (t: RightTab) => void
  setLeftTab: (t: LeftTab) => void
  toast: (text: string, kind?: 'info' | 'error') => void
  setProviders: (p: ProviderStatus) => void
}

function makeProject(name: string): Project {
  const now = Date.now()
  return {
    id: uid('prj'), name, directorId: 'me', customDirector: '', dpId: 'same', customDp: '', aspectRatio: '2.39:1',
    scenes: [], shots: {},
    settings: { pageSize: 'a4', framesPerPage: 4, provider: 'pollinations', showCredits: true },
    createdAt: now, updatedAt: now,
  }
}

function makeScene(partial: Partial<Scene> = {}, index = 0): Scene {
  return {
    id: uid('scn'), sceneNo: String(index + 1), heading: `SCENE ${index + 1}`, intExt: '', location: '', timeLabel: '',
    synopsis: '', scriptText: '', characters: [], shotIds: [], variants: [], ...partial,
  }
}

export function resolveDirector(p: Project | null): Lens {
  return resolveLens(p)
}

/** Fill fields added after a project was first saved. */
function migrate(p: Project): Project {
  return {
    ...p,
    dpId: p.dpId ?? 'same',
    customDp: p.customDp ?? '',
    scenes: p.scenes.map((s) => ({ ...s, variants: s.variants ?? [] })),
  }
}

/** Is this image still referenced by any shot or variant other than the given shot? */
function imageReferenced(p: Project, imageId: string, exceptShotId?: string): boolean {
  for (const s of Object.values(p.shots)) if (s.id !== exceptShotId && s.frames.some((f) => f.imageId === imageId)) return true
  for (const sc of p.scenes) for (const v of sc.variants ?? []) for (const s of v.shots) if (s.frames.some((f) => f.imageId === imageId)) return true
  return false
}

let saveTimer: ReturnType<typeof setTimeout> | null = null

export const useProject = create<State>((set, get) => {
  const mutate = (fn: (p: Project) => Project | void) => {
    const p = get().project
    if (!p) return
    const next = fn(p) ?? p
    set({ project: { ...next, updatedAt: Date.now() } })
  }

  return {
    project: null,
    projects: [],
    selectedSceneId: null,
    selectedShotId: null,
    ui: { rightTab: 'shot', leftTab: 'scenes', toast: null },
    providers: null,

    refreshProjects: async () => set({ projects: await dbApi.listProjects() }),
    newProject: async (name = 'Untitled board') => {
      const p = makeProject(name)
      const scene = makeScene({}, 0)
      p.scenes.push(scene)
      await dbApi.saveProject(p)
      set({ project: p, selectedSceneId: scene.id, selectedShotId: null })
      await get().refreshProjects()
    },
    openProject: async (id) => {
      const raw = await dbApi.loadProject(id)
      if (!raw) return
      const p = migrate(raw)
      set({ project: p, selectedSceneId: p.scenes[0]?.id ?? null, selectedShotId: null })
    },
    deleteProject: async (id) => {
      await dbApi.deleteProject(id)
      if (get().project?.id === id) set({ project: null, selectedSceneId: null, selectedShotId: null })
      await get().refreshProjects()
    },
    importProject: async (p) => {
      const fresh = migrate({ ...p, id: uid('prj'), updatedAt: Date.now() })
      await dbApi.saveProject(fresh)
      set({ project: fresh, selectedSceneId: fresh.scenes[0]?.id ?? null, selectedShotId: null })
      await get().refreshProjects()
    },

    setProject: (patch) => mutate((p) => ({ ...p, ...patch })),
    setSettings: (patch) => mutate((p) => ({ ...p, settings: { ...p.settings, ...patch } })),
    setDirector: (id, customText) => mutate((p) => {
      const next = { ...p, directorId: id, customDirector: customText ?? p.customDirector }
      const lens = resolveLens(next)
      return { ...next, aspectRatio: id === 'me' ? p.aspectRatio : lens.aspectRatio }
    }),
    setDp: (id, customText) => mutate((p) => {
      const next = { ...p, dpId: id, customDp: customText ?? p.customDp }
      const lens = resolveLens(next)
      return { ...next, aspectRatio: p.directorId === 'me' && id === 'same' ? p.aspectRatio : lens.aspectRatio }
    }),
    setAspect: (a) => mutate((p) => ({ ...p, aspectRatio: a })),

    addScene: (partial) => {
      const id = uid('scn')
      mutate((p) => ({ ...p, scenes: [...p.scenes, makeScene({ ...partial, id }, p.scenes.length)] }))
      set({ selectedSceneId: id, selectedShotId: null })
      return id
    },
    updateScene: (id, patch) => mutate((p) => ({ ...p, scenes: p.scenes.map((s) => (s.id === id ? { ...s, ...patch } : s)) })),
    removeScene: (id) => mutate((p) => {
      const scene = p.scenes.find((s) => s.id === id)
      if (!scene) return p
      const shots = { ...p.shots }
      for (const sid of scene.shotIds) delete shots[sid]
      const scenes = p.scenes.filter((s) => s.id !== id)
      if (get().selectedSceneId === id) set({ selectedSceneId: scenes[0]?.id ?? null, selectedShotId: null })
      return { ...p, scenes, shots }
    }),
    moveScene: (from, to) => mutate((p) => {
      const scenes = [...p.scenes]
      const [m] = scenes.splice(from, 1)
      scenes.splice(to, 0, m)
      return { ...p, scenes }
    }),
    importScenes: (parsed, opts = { generateShots: true }) => {
      const p = get().project
      if (!p) return
      const d = resolveDirector(p)
      const scenes = [...p.scenes]
      const shots = { ...p.shots }
      // drop the default empty scene if it is untouched
      if (scenes.length === 1 && scenes[0].shotIds.length === 0 && !scenes[0].scriptText && scenes[0].heading.startsWith('SCENE')) scenes.length = 0
      let firstId: string | null = null
      for (const ps of parsed) {
        const scene = makeScene({
          sceneNo: ps.sceneNo, heading: ps.heading, intExt: ps.intExt, location: ps.location, timeLabel: ps.timeLabel,
          scriptText: ps.text, characters: ps.characters,
          synopsis: ps.elements.find((e) => e.type === 'action')?.text.slice(0, 200) ?? '',
        }, scenes.length)
        if (!firstId) firstId = scene.id
        if (opts.generateShots) {
          scene.activeLens = { directorId: p.directorId, dpId: p.dpId, label: d.name }
          const drafts = generateShotList(ps, d)
          for (const dr of drafts) {
            const shot: Shot = { ...dr, id: uid('sht'), sceneId: scene.id, frames: [], heroFrameId: null }
            delete (shot as Partial<ShotDraft>).rationale
            if (dr.rationale) shot.notes = dr.rationale
            shots[shot.id] = shot
            scene.shotIds.push(shot.id)
          }
        }
        scenes.push(scene)
      }
      set({ project: { ...p, scenes, shots, updatedAt: Date.now() }, selectedSceneId: firstId ?? get().selectedSceneId, selectedShotId: null })
    },

    addShot: (sceneId, draft, index) => {
      const id = uid('sht')
      mutate((p) => {
        const scene = p.scenes.find((s) => s.id === sceneId)
        if (!scene) return p
        const d = resolveDirector(p)
        const base = blankShot(d, String(scene.shotIds.length + 1))
        const shot: Shot = { ...base, ...draft, id, sceneId, frames: [], heroFrameId: null }
        const shotIds = [...scene.shotIds]
        shotIds.splice(index ?? shotIds.length, 0, id)
        return renumber({ ...p, shots: { ...p.shots, [id]: shot }, scenes: p.scenes.map((s) => (s.id === sceneId ? { ...s, shotIds } : s)) }, sceneId)
      })
      set({ selectedShotId: id, selectedSceneId: sceneId })
      return id
    },
    addShotsFromDrafts: (sceneId, drafts, replace = false) => mutate((p) => {
      const scene = p.scenes.find((s) => s.id === sceneId)
      if (!scene) return p
      const shots = { ...p.shots }
      let shotIds = [...scene.shotIds]
      if (replace) { for (const sid of shotIds) delete shots[sid]; shotIds = [] }
      for (const dr of drafts) {
        const { rationale, ...rest } = dr
        const shot: Shot = { ...rest, id: uid('sht'), sceneId, frames: [], heroFrameId: null, notes: rest.notes || rationale || '' }
        shots[shot.id] = shot
        shotIds.push(shot.id)
      }
      const activeLens = replace ? { directorId: p.directorId, dpId: p.dpId, label: resolveLens(p).name } : scene.activeLens
      return renumber({ ...p, shots, scenes: p.scenes.map((s) => (s.id === sceneId ? { ...s, shotIds, activeLens } : s)) }, sceneId)
    }),
    redirectScene: (sceneId, drafts) => {
      const st = get()
      const scene = st.project?.scenes.find((s) => s.id === sceneId)
      if (!scene) return
      if (scene.shotIds.length) st.saveVariant(sceneId)
      st.addShotsFromDrafts(sceneId, drafts, true)
    },

    saveVariant: (sceneId, label) => mutate((p) => {
      const scene = p.scenes.find((s) => s.id === sceneId)
      if (!scene || !scene.shotIds.length) return p
      const made = scene.activeLens ?? { directorId: p.directorId, dpId: p.dpId, label: resolveLens(p).name }
      const v: ShotVariant = {
        id: uid('var'), label: label || made.label, directorId: made.directorId, dpId: made.dpId,
        shots: scene.shotIds.map((id) => p.shots[id]).filter(Boolean).map((s) => ({ ...s, frames: [...s.frames] })),
        createdAt: Date.now(),
      }
      return { ...p, scenes: p.scenes.map((s) => (s.id === sceneId ? { ...s, variants: [...(s.variants ?? []), v] } : s)) }
    }),
    restoreVariant: (sceneId, variantId) => mutate((p) => {
      const scene = p.scenes.find((s) => s.id === sceneId)
      const v = scene?.variants.find((x) => x.id === variantId)
      if (!scene || !v) return p
      // Park the current list as a variant, then make the chosen one active.
      const made = scene.activeLens ?? { directorId: p.directorId, dpId: p.dpId, label: resolveLens(p).name }
      const parked: ShotVariant | null = scene.shotIds.length ? {
        id: uid('var'), label: made.label, directorId: made.directorId, dpId: made.dpId,
        shots: scene.shotIds.map((id) => p.shots[id]).filter(Boolean), createdAt: Date.now(),
      } : null
      const shots = { ...p.shots }
      for (const id of scene.shotIds) delete shots[id]
      const restored = v.shots.map((s) => ({ ...s, id: uid('sht'), sceneId }))
      for (const s of restored) shots[s.id] = s
      const variants = scene.variants.filter((x) => x.id !== variantId).concat(parked ? [parked] : [])
      const activeLens = { directorId: v.directorId, dpId: v.dpId, label: v.label }
      const next = { ...p, shots, directorId: v.directorId, dpId: v.dpId, scenes: p.scenes.map((s) => (s.id === sceneId ? { ...s, shotIds: restored.map((r) => r.id), variants, activeLens } : s)) }
      set({ selectedShotId: null })
      return renumber(next, sceneId)
    }),
    deleteVariant: (sceneId, variantId) => mutate((p) => {
      const scene = p.scenes.find((s) => s.id === sceneId)
      const v = scene?.variants.find((x) => x.id === variantId)
      if (!scene || !v) return p
      const next = { ...p, scenes: p.scenes.map((s) => (s.id === sceneId ? { ...s, variants: s.variants.filter((x) => x.id !== variantId) } : s)) }
      for (const s of v.shots) for (const f of s.frames) if (f.imageId && !imageReferenced(next, f.imageId)) void dbApi.deleteImage(f.imageId)
      return next
    }),
    renameVariant: (sceneId, variantId, label) => mutate((p) => ({ ...p, scenes: p.scenes.map((s) => (s.id === sceneId ? { ...s, variants: s.variants.map((v) => (v.id === variantId ? { ...v, label } : v)) } : s)) })),
    copyVariantShot: (sceneId, variantId, shotId) => mutate((p) => {
      const scene = p.scenes.find((s) => s.id === sceneId)
      const src = scene?.variants.find((x) => x.id === variantId)?.shots.find((s) => s.id === shotId)
      if (!scene || !src) return p
      const copy: Shot = { ...src, id: uid('sht'), sceneId, frames: [...src.frames] }
      return renumber({ ...p, shots: { ...p.shots, [copy.id]: copy }, scenes: p.scenes.map((s) => (s.id === sceneId ? { ...s, shotIds: [...s.shotIds, copy.id] } : s)) }, sceneId)
    }),

    updateShot: (id, patch) => mutate((p) => (p.shots[id] ? { ...p, shots: { ...p.shots, [id]: { ...p.shots[id], ...patch } } } : p)),
    removeShot: (id) => mutate((p) => {
      const shot = p.shots[id]
      if (!shot) return p
      for (const f of shot.frames) if (f.imageId && !imageReferenced(p, f.imageId, id)) void dbApi.deleteImage(f.imageId)
      const shots = { ...p.shots }
      delete shots[id]
      if (get().selectedShotId === id) set({ selectedShotId: null })
      return renumber({ ...p, shots, scenes: p.scenes.map((s) => (s.id === shot.sceneId ? { ...s, shotIds: s.shotIds.filter((x) => x !== id) } : s)) }, shot.sceneId)
    }),
    duplicateShot: (id) => {
      const nid = uid('sht')
      mutate((p) => {
        const shot = p.shots[id]
        if (!shot) return p
        const copy: Shot = { ...shot, id: nid, frames: shot.frames.filter((f) => f.kind === 'reference'), heroFrameId: null }
        copy.heroFrameId = copy.frames[0]?.id ?? null
        const scene = p.scenes.find((s) => s.id === shot.sceneId)!
        const idx = scene.shotIds.indexOf(id)
        const shotIds = [...scene.shotIds]
        shotIds.splice(idx + 1, 0, nid)
        return renumber({ ...p, shots: { ...p.shots, [nid]: copy }, scenes: p.scenes.map((s) => (s.id === scene.id ? { ...s, shotIds } : s)) }, scene.id)
      })
      set({ selectedShotId: nid })
    },
    moveShot: (sceneId, from, to) => mutate((p) => {
      const scene = p.scenes.find((s) => s.id === sceneId)
      if (!scene || from === to) return p
      const shotIds = [...scene.shotIds]
      const [m] = shotIds.splice(from, 1)
      shotIds.splice(to, 0, m)
      return renumber({ ...p, scenes: p.scenes.map((s) => (s.id === sceneId ? { ...s, shotIds } : s)) }, sceneId)
    }),

    addFrame: (shotId, frame, makeHero = true) => {
      const id = uid('frm')
      mutate((p) => {
        const shot = p.shots[shotId]
        if (!shot) return p
        const f: Frame = { ...frame, id, createdAt: Date.now() }
        const frames = [...shot.frames, f]
        return { ...p, shots: { ...p.shots, [shotId]: { ...shot, frames, heroFrameId: makeHero || !shot.heroFrameId ? id : shot.heroFrameId } } }
      })
      return id
    },
    removeFrame: (shotId, frameId) => mutate((p) => {
      const shot = p.shots[shotId]
      if (!shot) return p
      const f = shot.frames.find((x) => x.id === frameId)
      if (f?.imageId && !imageReferenced(p, f.imageId, shotId)) void dbApi.deleteImage(f.imageId)
      const frames = shot.frames.filter((x) => x.id !== frameId)
      return { ...p, shots: { ...p.shots, [shotId]: { ...shot, frames, heroFrameId: shot.heroFrameId === frameId ? frames[0]?.id ?? null : shot.heroFrameId } } }
    }),
    setHero: (shotId, frameId) => mutate((p) => (p.shots[shotId] ? { ...p, shots: { ...p.shots, [shotId]: { ...p.shots[shotId], heroFrameId: frameId } } } : p)),

    selectScene: (id) => set({ selectedSceneId: id, selectedShotId: null }),
    selectShot: (id) => set({ selectedShotId: id }),
    setRightTab: (t) => set((s) => ({ ui: { ...s.ui, rightTab: t } })),
    setLeftTab: (t) => set((s) => ({ ui: { ...s.ui, leftTab: t } })),
    toast: (text, kind = 'info') => {
      set((s) => ({ ui: { ...s.ui, toast: { kind, text } } }))
      setTimeout(() => set((s) => (s.ui.toast?.text === text ? { ui: { ...s.ui, toast: null } } : s)), 3500)
    },
    setProviders: (providers) => set({ providers }),
  }
})

function renumber(p: Project, sceneId: string): Project {
  const scene = p.scenes.find((s) => s.id === sceneId)
  if (!scene) return p
  const shots = { ...p.shots }
  scene.shotIds.forEach((id, i) => { if (shots[id]) shots[id] = { ...shots[id], shotNo: String(i + 1) } })
  return { ...p, shots }
}

// Debounced autosave
useProject.subscribe((s, prev) => {
  if (s.project && s.project !== prev.project) {
    if (saveTimer) clearTimeout(saveTimer)
    const snapshot = s.project
    saveTimer = setTimeout(() => { void dbApi.saveProject(snapshot).then(() => useProject.getState().refreshProjects()) }, 400)
  }
})

/** Selectors */
export const useCurrentScene = () => useProject((s) => s.project?.scenes.find((x) => x.id === s.selectedSceneId) ?? null)
export const useCurrentShot = () => useProject((s) => (s.selectedShotId && s.project ? s.project.shots[s.selectedShotId] ?? null : null))
/** The working lens: director grammar merged with the cinematographer's lensing. */
export const useDirector = () => useProject((s) => resolveLens(s.project))
export const useLens = useDirector
