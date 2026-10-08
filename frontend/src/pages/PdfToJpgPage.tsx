import { useState } from 'react'
import { downloadBlob, postForFile, type FileResult } from '../api/client'
import BtnIcon from '../components/BtnIcon'
import FileDropzone from '../components/FileDropzone'
import PdfThumb from '../components/PdfThumb'
import PdfZoom from '../components/PdfZoom'
import FileCard from '../components/FileCard'
import ToolSidebar from '../components/ToolSidebar'
import { addWithinLimits, MAX_PDF_TO_JPG_PAGES } from '../fileItems'
import { usePdfPageCount } from '../usePdfPageCount'

const ACCEPT = { 'application/pdf': ['.pdf'] }

type Quality = 'normal' | 'high'

const QUALITIES: { value: Quality; title: string; description: string }[] = [
  { value: 'normal', title: 'Normal quality', description: '150 dpi, good for screens and sharing' },
  { value: 'high', title: 'High quality', description: '300 dpi, sharper for printing, larger files' },
]

export default function PdfToJpgPage() {
  const [file, setFile] = useState<File | null>(null)
  const [quality, setQuality] = useState<Quality>('normal')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<FileResult | null>(null)
  const [zoomed, setZoomed] = useState(false)

  // undefined while counting, null if pdf.js can't read the file.
  const pageCount = usePdfPageCount(file)

  // Checked the way the backend will, so the button can't send a file that's bound to be rejected.
  const pageError =
    pageCount === 0
      ? 'This PDF has no pages to convert.'
      : pageCount != null && pageCount > MAX_PDF_TO_JPG_PAGES
        ? `This PDF has ${pageCount} pages, more than the limit of ${MAX_PDF_TO_JPG_PAGES}. Split it into smaller PDFs first.`
        : null

  function selectFile(files: File[]) {
    const next = addWithinLimits([], files.slice(0, 1))
    setFile(next.items[0]?.file ?? null)
    setError(next.error)
  }

  async function convert() {
    if (!file) return
    setBusy(true)
    setError(null)
    const form = new FormData()
    form.append('file', file)
    form.append('quality', quality)
    try {
      // One page gives a JPG, more a ZIP: name it by type when the response doesn't give a name.
      const res = await postForFile('/api/pdf-to-jpg', form, '')
      const filename = res.filename || (isZip(res) ? 'images.zip' : 'image.jpg')
      setResult({ ...res, filename })
      downloadBlob(res.blob, filename)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  function reset() {
    setFile(null)
    setZoomed(false)
    setQuality('normal')
    setResult(null)
    setError(null)
  }

  if (result) {
    const zipped = isZip(result)
    return (
      <section className="tool-page">
        <h1>{zipped ? 'Your JPG images are ready!' : 'Your JPG image is ready!'}</h1>
        <p className="subtitle">The download should start automatically.</p>
        <div className="actions">
          <button className="btn btn-large" onClick={() => downloadBlob(result.blob, result.filename)}>
            {zipped ? 'Download ZIP' : 'Download JPG'}
            <BtnIcon kind="download" />
          </button>
          <button className="btn btn-large btn-secondary" onClick={reset}>
            Convert another file
          </button>
        </div>
      </section>
    )
  }

  if (!file) {
    return (
      <section className="tool-page">
        <h1>Convert PDF to JPG</h1>
        <p className="subtitle">Turn each page of a PDF into a JPG image.</p>
        <FileDropzone
          accept={ACCEPT}
          multiple={false}
          onFiles={selectFile}
          onReject={setError}
          label="Select PDF file"
          hint="or drop a PDF here"
        />
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
      </section>
    )
  }

  return (
    <section className="workspace">
      <div className="workspace-main">
        <FileCard
          file={file}
          preview={<PdfThumb file={file} />}
          onZoom={busy ? undefined : () => setZoomed(true)}
          onRemove={busy ? undefined : reset}
        />
        {zoomed && <PdfZoom file={file} onClose={() => setZoomed(false)} />}
      </div>

      <ToolSidebar
        title="Image quality"
        action={
          <button className="btn btn-large" onClick={convert} disabled={busy || pageError !== null}>
            {busy ? 'Converting…' : 'Convert to JPG'}
            {!busy && <BtnIcon kind="next" />}
          </button>
        }
      >
        <fieldset className="choices choices-stacked" disabled={busy}>
          <legend className="sr-only">Image quality</legend>
          {QUALITIES.map((q) => (
            <label key={q.value} className={`choice${quality === q.value ? ' choice-selected' : ''}`}>
              <input
                type="radio"
                name="quality"
                value={q.value}
                checked={quality === q.value}
                onChange={() => {
                  setQuality(q.value)
                  // A server error, e.g. that high quality is too large, may not apply at the new quality.
                  setError(null)
                }}
              />
              <span className="choice-title">{q.title}</span>
              <span className="muted">{q.description}</span>
            </label>
          ))}
        </fieldset>

        {pageCount != null && pageError === null && (
          <p className="split-summary">
            You'll get {pageCount === 1 ? 'one JPG image' : `${pageCount} JPG images in a ZIP file`}.
          </p>
        )}

        {(pageError ?? error) && (
          <div className="error" role="alert">
            {pageError ?? error}
          </div>
        )}
      </ToolSidebar>
    </section>
  )
}

function isZip(result: FileResult): boolean {
  return result.blob.type === 'application/zip'
}
