import type { Frame } from '../types'
import { useFrameSrc } from '../hooks/useFrameSrc'

export function FrameImage({ frame, ratio, className = '', fit = 'cover', preferThumb = true }: {
  frame: Frame | null | undefined
  ratio: number
  className?: string
  fit?: 'cover' | 'contain'
  preferThumb?: boolean
}) {
  const src = useFrameSrc(frame, preferThumb)
  return (
    <div className={`relative bg-black overflow-hidden ${className}`} style={{ aspectRatio: String(ratio) }}>
      {src ? (
        <img src={src} alt="" className={`absolute inset-0 w-full h-full ${fit === 'cover' ? 'object-cover' : 'object-contain'}`} draggable={false} />
      ) : (
        <div className="absolute inset-0 grid place-items-center text-mute text-[11px]">
          {frame ? '…' : 'no frame'}
        </div>
      )}
    </div>
  )
}
