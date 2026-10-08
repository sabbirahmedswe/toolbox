import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { renderPdfThumbnail } from '../pdfThumbnail'

interface Props {
  file: File
  /** The CSS box to render the page to fit; defaults to the size of the canvas's parent (a card's preview box). */
  box?: { width: number; height: number }
  className?: string
  style?: CSSProperties
  /** Shown while loading (`failed` false) or if the file can't be rendered; defaults to the PDF badge. */
  fallback?: (failed: boolean) => ReactNode
}

const badge = () => <span className="file-badge">PDF</span>

/** First-page preview of a local PDF. */
export default function PdfThumb({ file, box, className = 'file-thumb', style, fallback = badge }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  // How the last render of this file ended. A new size keeps the current picture up while it renders.
  const [done, setDone] = useState<{ file: File; ok: boolean } | null>(null)
  const status = done?.file === file ? (done.ok ? 'ready' : 'failed') : 'loading'
  const width = box?.width
  const height = box?.height

  useEffect(() => {
    const controller = new AbortController()
    const canvas = canvasRef.current!
    const parent = canvas.parentElement!
    const size = { width: width ?? parent.clientWidth, height: height ?? parent.clientHeight }
    // Render off screen, then copy: the shown canvas keeps its picture meanwhile, and a cancelled render still
    // finishing in the background can't draw into the next one's canvas.
    const offscreen = document.createElement('canvas')
    renderPdfThumbnail(file, offscreen, size, controller.signal).then(
      () => {
        if (controller.signal.aborted) return
        canvas.width = offscreen.width
        canvas.height = offscreen.height
        canvas.getContext('2d')!.drawImage(offscreen, 0, 0)
        offscreen.width = offscreen.height = 0 // free the pixels now rather than at the next garbage collection
        setDone({ file, ok: true })
      },
      () => {
        // Unreadable PDFs show the fallback; aborted renders are simply dropped.
        if (!controller.signal.aborted) setDone({ file, ok: false })
      },
    )
    return () => controller.abort()
  }, [file, width, height])

  return (
    <>
      <canvas ref={canvasRef} className={className} style={style} hidden={status !== 'ready'} />
      {status !== 'ready' && fallback(status === 'failed')}
    </>
  )
}
