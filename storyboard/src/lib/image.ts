/** Browser image helpers: resize uploads, convert between blob/dataURL/base64. */

export async function resizeImage(file: Blob, maxEdge = 1600, type = 'image/jpeg', quality = 0.9): Promise<Blob> {
  const bmp = await createImageBitmap(file)
  const scale = Math.min(1, maxEdge / Math.max(bmp.width, bmp.height))
  if (scale === 1 && file.type === type) { bmp.close(); return file }
  const w = Math.round(bmp.width * scale)
  const h = Math.round(bmp.height * scale)
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')!
  ctx.drawImage(bmp, 0, 0, w, h)
  bmp.close()
  return new Promise((resolve) => canvas.toBlob((b) => resolve(b ?? file), type, quality))
}

export function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => resolve(String(r.result))
    r.onerror = reject
    r.readAsDataURL(blob)
  })
}

export function base64ToBlob(b64: string, mime = 'image/png'): Blob {
  const bin = atob(b64)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return new Blob([bytes], { type: mime })
}

export async function blobToBase64(blob: Blob): Promise<string> {
  const url = await blobToDataUrl(blob)
  return url.slice(url.indexOf(',') + 1)
}

export function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('Image failed to load'))
    img.src = src
  })
}

/** Draw an image letterboxed/cropped into a canvas of the given aspect; returns a JPEG data URL. */
export async function fitToAspect(src: string, ratio: number, width = 1200, mode: 'cover' | 'contain' = 'cover'): Promise<string> {
  const img = await loadImage(src)
  const w = width
  const h = Math.round(width / ratio)
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')!
  ctx.fillStyle = '#000'
  ctx.fillRect(0, 0, w, h)
  const ir = img.width / img.height
  let dw = w, dh = h, dx = 0, dy = 0
  const cover = mode === 'cover'
  if ((ir > ratio) === cover) { dh = h; dw = Math.round(h * ir); dx = Math.round((w - dw) / 2) }
  else { dw = w; dh = Math.round(w / ir); dy = Math.round((h - dh) / 2) }
  ctx.drawImage(img, dx, dy, dw, dh)
  return canvas.toDataURL('image/jpeg', 0.9)
}
