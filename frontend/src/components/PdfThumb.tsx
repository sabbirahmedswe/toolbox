import { useEffect, useRef, useState } from 'react'
import { renderPdfThumbnail } from '../pdfThumbnail'

// The .file-preview box on a full-size file card (210px wide minus padding and border).
const BOX = { width: 184, height: 190 }

/** First-page preview of a local PDF; shows the PDF badge while loading or if the file can't be rendered. */
export default function PdfThumb({ file }: { file: File }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    renderPdfThumbnail(file, canvasRef.current!, BOX, controller.signal).then(
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
