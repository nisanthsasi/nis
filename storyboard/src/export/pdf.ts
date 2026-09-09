import { jsPDF } from 'jspdf'
import type { Frame, Project, Scene, Shot } from '../types'
import { aspectToRatio, CAMERA_ANGLES, LENS_CHARACTERS, LIGHTING_KEYS, MOVEMENTS, SHOT_SIZES } from '../taxonomy'
import { getImageUrl } from '../store/db'
import { proxied } from '../api/frames'
import { fitToAspect } from '../lib/image'
import { resolveDirector } from '../store/useProject'

export interface PdfOptions {
  pageSize?: 'a4' | 'letter'
  framesPerPage?: 2 | 4 | 6
  sceneIds?: string[]
  showCredits?: boolean
  onProgress?: (done: number, total: number) => void
}

/** Grid geometry: columns x rows for N frames per landscape page. */
export function gridFor(framesPerPage: number): { cols: number; rows: number } {
  if (framesPerPage <= 2) return { cols: 2, rows: 1 }
  if (framesPerPage <= 4) return { cols: 2, rows: 2 }
  return { cols: 3, rows: 2 }
}

/** Number of pages needed for a list of per-scene shot counts (scenes never share a page). */
export function pageCount(shotCounts: number[], framesPerPage: number): number {
  return shotCounts.reduce((n, c) => n + Math.max(1, Math.ceil(c / framesPerPage)), 0)
}

export function heroFrame(shot: Shot): Frame | null {
  return shot.frames.find((f) => f.id === shot.heroFrameId) ?? shot.frames[0] ?? null
}

async function frameDataUrl(frame: Frame | null, ratio: number): Promise<string | null> {
  if (!frame) return null
  try {
    let src: string | undefined
    if (frame.imageId) src = await getImageUrl(frame.imageId)
    else if (frame.url) src = proxied(frame.url)
    else if (frame.thumbUrl) src = proxied(frame.thumbUrl)
    if (!src) return null
    return await fitToAspect(src, ratio, 1000, 'contain')
  } catch {
    return null
  }
}

const label = <T extends string>(list: { value: T; label: string }[], v: T) => list.find((x) => x.value === v)?.label ?? v

export async function exportStoryboardPdf(project: Project, opts: PdfOptions = {}): Promise<Blob> {
  const pageSize = opts.pageSize ?? project.settings.pageSize
  const fpp = opts.framesPerPage ?? project.settings.framesPerPage
  const showCredits = opts.showCredits ?? project.settings.showCredits
  const scenes = project.scenes.filter((s) => !opts.sceneIds || opts.sceneIds.includes(s.id))
  const director = resolveDirector(project)
  const ratio = aspectToRatio(project.aspectRatio)

  const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: pageSize })
  const W = doc.internal.pageSize.getWidth()
  const H = doc.internal.pageSize.getHeight()
  const M = 10
  const headerH = 12
  const footerH = 7
  const { cols, rows } = gridFor(fpp)
  const gap = 5
  const cellW = (W - M * 2 - gap * (cols - 1)) / cols
  const cellH = (H - M * 2 - headerH - footerH - gap * (rows - 1)) / rows
  const imgH = Math.min(cellW / ratio, cellH * 0.62)
  const imgW = imgH * ratio

  const total = scenes.reduce((n, s) => n + s.shotIds.length, 0)
  let done = 0
  let first = true
  let pageNo = 0

  const header = (scene: Scene) => {
    pageNo++
    doc.setTextColor(20)
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(12)
    doc.text(project.name, M, M + 4)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9)
    doc.setTextColor(90)
    doc.text(`Sc ${scene.sceneNo}  ${scene.heading}`, M, M + 9)
    const right = `${director.name}  |  ${project.aspectRatio}  |  p.${pageNo}`
    doc.text(right, W - M, M + 4, { align: 'right' })
    doc.setDrawColor(200)
    doc.line(M, M + headerH - 1, W - M, M + headerH - 1)
    doc.setFontSize(7)
    doc.setTextColor(140)
    doc.text('Storyboard Maker', M, H - 4)
    if (showCredits) doc.text('Reference stills remain the property of their rights holders; internal pre-production use only.', W - M, H - 4, { align: 'right' })
  }

  const drawCell = async (shot: Shot, scene: Scene, col: number, row: number) => {
    const x = M + col * (cellW + gap)
    const y = M + headerH + row * (cellH + gap)
    // image box
    const ix = x + (cellW - imgW) / 2
    doc.setFillColor(15, 15, 15)
    doc.rect(ix, y, imgW, imgH, 'F')
    const fr = heroFrame(shot)
    const data = await frameDataUrl(fr, ratio)
    if (data) {
      try { doc.addImage(data, 'JPEG', ix, y, imgW, imgH) } catch { /* skip broken image */ }
    } else {
      doc.setTextColor(120)
      doc.setFontSize(8)
      doc.text('no frame', ix + imgW / 2, y + imgH / 2, { align: 'center' })
    }
    // shot number badge
    doc.setFillColor(232, 176, 75)
    doc.rect(ix, y, 9, 5, 'F')
    doc.setTextColor(10)
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(8)
    doc.text(`${scene.sceneNo}.${shot.shotNo}`, ix + 1, y + 3.6)

    // text block
    let ty = y + imgH + 4
    const maxW = cellW
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(8)
    doc.setTextColor(20)
    const strip = [
      label(SHOT_SIZES, shot.shotSize), label(CAMERA_ANGLES, shot.cameraAngle), label(MOVEMENTS, shot.movement),
      shot.lensMm ? `${shot.lensMm}mm ${label(LENS_CHARACTERS, shot.lensCharacter)}` : label(LENS_CHARACTERS, shot.lensCharacter),
      label(LIGHTING_KEYS, shot.lightingKey), shot.durationSec ? `${shot.durationSec}s` : '',
    ].filter(Boolean).join('  ·  ')
    const stripLines = doc.splitTextToSize(strip, maxW) as string[]
    doc.text(stripLines.slice(0, 2), x, ty)
    ty += 3.2 * Math.min(2, stripLines.length) + 1
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(7.5)
    doc.setTextColor(40)
    const body: string[] = []
    if (shot.subject) body.push(shot.subject)
    if (shot.action) body.push(shot.action)
    if (shot.dialogue) body.push(`“${shot.dialogue}”`)
    if (shot.notes) body.push(`Note: ${shot.notes}`)
    const remaining = y + cellH - ty - (showCredits && fr?.kind === 'reference' ? 3.5 : 0)
    const maxLines = Math.max(1, Math.floor(remaining / 3.1))
    const lines = (doc.splitTextToSize(body.join('  '), maxW) as string[]).slice(0, maxLines)
    doc.text(lines, x, ty)
    ty += lines.length * 3.1
    if (showCredits && fr?.kind === 'reference' && fr.credit) {
      doc.setFontSize(6.5)
      doc.setTextColor(120)
      const c = fr.credit
      const credit = ['Ref:', c.film, c.year ? `(${c.year})` : '', c.director ? `dir. ${c.director}` : '', c.dp ? `DP ${c.dp}` : ''].filter(Boolean).join(' ')
      doc.text(doc.splitTextToSize(credit, maxW)[0], x, y + cellH - 0.5)
    }
    done++
    opts.onProgress?.(done, total)
  }

  for (const scene of scenes) {
    const shots = scene.shotIds.map((id) => project.shots[id]).filter(Boolean)
    const pages = Math.max(1, Math.ceil(shots.length / fpp))
    for (let p = 0; p < pages; p++) {
      if (!first) doc.addPage()
      first = false
      header(scene)
      const slice = shots.slice(p * fpp, (p + 1) * fpp)
      for (let i = 0; i < slice.length; i++) {
        await drawCell(slice[i], scene, i % cols, Math.floor(i / cols))
      }
      if (slice.length === 0) {
        doc.setTextColor(120)
        doc.setFontSize(9)
        doc.text('No shots in this scene yet.', M, M + headerH + 8)
      }
    }
  }
  if (scenes.length === 0) {
    doc.text('Empty storyboard.', M, M + headerH + 8)
  }
  return doc.output('blob')
}

export function downloadBlob(blob: Blob, filename: string) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  document.body.appendChild(a)
  a.click()
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove() }, 1000)
}
