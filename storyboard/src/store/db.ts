import Dexie, { type EntityTable } from 'dexie'
import type { Project } from '../types'

export interface StoredImage {
  id: string
  blob: Blob
  mime: string
  width?: number
  height?: number
  createdAt: number
}

export interface ProjectMeta {
  id: string
  name: string
  updatedAt: number
  sceneCount: number
  shotCount: number
}

class StoryboardDB extends Dexie {
  projects!: EntityTable<Project, 'id'>
  images!: EntityTable<StoredImage, 'id'>
  constructor() {
    super('storyboard-maker')
    this.version(1).stores({
      projects: 'id, updatedAt, name',
      images: 'id, createdAt',
    })
  }
}

export const db = new StoryboardDB()

const urlCache = new Map<string, string>()

export async function putImage(id: string, blob: Blob): Promise<string> {
  await db.images.put({ id, blob, mime: blob.type || 'image/png', createdAt: Date.now() })
  return id
}

export async function getImageBlob(id: string): Promise<Blob | undefined> {
  const rec = await db.images.get(id)
  return rec?.blob
}

/** Object URL for a stored image, cached for the session. */
export async function getImageUrl(id: string): Promise<string | undefined> {
  const hit = urlCache.get(id)
  if (hit) return hit
  const blob = await getImageBlob(id)
  if (!blob) return undefined
  const url = URL.createObjectURL(blob)
  urlCache.set(id, url)
  return url
}

export async function deleteImage(id: string): Promise<void> {
  const u = urlCache.get(id)
  if (u) { URL.revokeObjectURL(u); urlCache.delete(id) }
  await db.images.delete(id)
}

export async function listProjects(): Promise<ProjectMeta[]> {
  const all = await db.projects.orderBy('updatedAt').reverse().toArray()
  return all.map((p) => ({ id: p.id, name: p.name, updatedAt: p.updatedAt, sceneCount: p.scenes.length, shotCount: Object.keys(p.shots).length }))
}

export async function saveProject(p: Project): Promise<void> {
  await db.projects.put(p)
}

export async function loadProject(id: string): Promise<Project | undefined> {
  return db.projects.get(id)
}

export async function deleteProject(id: string): Promise<void> {
  const p = await db.projects.get(id)
  if (p) {
    const ids = Object.values(p.shots).flatMap((s) => s.frames.map((f) => f.imageId).filter((x): x is string => !!x))
    await Promise.all(ids.map(deleteImage))
  }
  await db.projects.delete(id)
}
