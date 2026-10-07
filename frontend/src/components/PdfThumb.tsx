import { useEffect, useRef, useState } from 'react'
import { renderPdfThumbnail } from '../pdfThumbnail'

/** First-page preview of a local PDF; shows the PDF badge while loading or if the file can't be rendered. */
export default function PdfThumb({ file }: { file: File }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    const canvas = canvasRef.current!
    // Render at the size of the card's preview box, which is smaller on phones.
    const box = canvas.parentElement!
    renderPdfThumbnail(file, canvas, { width: box.clientWidth, height: box.clientHeight }, controller.signal).then(
      () => setReady(true),
      () => {}, // unreadable PDFs and aborted renders keep the badge
    )
    return () => controller.abort()
  }, [file])

  return (
    <>
      <canvas ref={canvasRef} className="file-thumb" hidden={!ready} />
      {!ready && <span className="file-badge">PDF</span>}
    </>
  )
}
