import { useState } from 'react'
import { downloadBlob, formatBytes, postForFile, type FileResult } from '../api/client'
import BtnIcon from '../components/BtnIcon'
import FileCard from '../components/FileCard'
import FileDropzone from '../components/FileDropzone'
import PdfThumb from '../components/PdfThumb'
import PdfZoom from '../components/PdfZoom'
import ToolSidebar from '../components/ToolSidebar'
import { addWithinLimits } from '../fileItems'

const ACCEPT = { 'application/pdf': ['.pdf'] }

type Level = 'low' | 'medium' | 'high'

const LEVELS: { value: Level; title: string; description: string }[] = [
  { value: 'high', title: 'Extreme compression', description: 'Smallest file, lower quality' },
  { value: 'medium', title: 'Recommended', description: 'Good quality, good compression' },
  { value: 'low', title: 'Less compression', description: 'High quality, larger file' },
]

interface Outcome {
  result: FileResult
  originalSize: number
  compressedSize: number
}

export default function CompressPage() {
  const [file, setFile] = useState<File | null>(null)
  const [level, setLevel] = useState<Level>('medium')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [outcome, setOutcome] = useState<Outcome | null>(null)
  const [zoomed, setZoomed] = useState(false)

  function selectFile(files: File[]) {
    const next = addWithinLimits([], files.slice(0, 1))
    setFile(next.items[0]?.file ?? null)
    setError(next.error)
  }

  async function compress() {
    if (!file) return
    setBusy(true)
    setError(null)
    const form = new FormData()
    form.append('file', file)
    form.append('level', level)
    try {
      const result = await postForFile('/api/compress', form, 'compressed.pdf')
      const originalSize = Number(result.headers.get('X-Original-Size') ?? file.size)
      const compressedSize = Number(result.headers.get('X-Compressed-Size') ?? result.blob.size)
      setOutcome({ result, originalSize, compressedSize })
      downloadBlob(result.blob, result.filename)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  function reset() {
    setFile(null)
    setZoomed(false)
    setOutcome(null)
    setError(null)
  }

  if (outcome) {
    const { result, originalSize, compressedSize } = outcome
    const reduced = compressedSize < originalSize
    const percent = savingsPercent(originalSize, compressedSize)
    return (
      <section className="tool-page">
        {reduced ? (
          <>
            <h1>Your PDF is now {percent}% smaller!</h1>
            <p className="subtitle">The download should start automatically.</p>
          </>
        ) : (
          <>
            <h1>Your PDF is already well optimized</h1>
            <p className="subtitle">We couldn't make it any smaller, so you'll get the original file back.</p>
          </>
        )}
        <div className="savings">
          <div>
            <span className="muted">Before</span>
            <strong>{formatBytes(originalSize)}</strong>
          </div>
          <span className="savings-arrow">→</span>
          <div>
            <span className="muted">After</span>
            <strong>{formatBytes(compressedSize)}</strong>
          </div>
        </div>
        <div className="actions">
          <button className="btn btn-large" onClick={() => downloadBlob(result.blob, result.filename)}>
            Download compressed PDF
            <BtnIcon kind="download" />
          </button>
          <button className="btn btn-large btn-secondary" onClick={reset}>
            Compress another file
          </button>
        </div>
      </section>
    )
  }

  if (!file) {
    return (
      <section className="tool-page">
        <h1>Compress a PDF</h1>
        <p className="subtitle">Shrink your PDF and choose how much quality to trade for a smaller file.</p>
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
        title="Compression level"
        action={
          <button className="btn btn-large" onClick={compress} disabled={busy}>
            {busy ? 'Compressing…' : 'Compress PDF'}
            {!busy && <BtnIcon kind="next" />}
          </button>
        }
      >
        <fieldset className="choices choices-stacked" disabled={busy}>
          <legend className="sr-only">Compression level</legend>
          {LEVELS.map((l) => (
            <label key={l.value} className={`choice${level === l.value ? ' choice-selected' : ''}`}>
              <input
                type="radio"
                name="level"
                value={l.value}
                checked={level === l.value}
                onChange={() => {
                  setLevel(l.value)
                  // A server error from the last attempt may not apply at the new level.
                  setError(null)
                }}
              />
              <span className="choice-title">{l.title}</span>
              <span className="muted">{l.description}</span>
            </label>
          ))}
        </fieldset>

        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
      </ToolSidebar>
    </section>
  )
}

/** Percent saved; at least 1 so a tiny but real saving isn't shown as 0%. */
function savingsPercent(original: number, size: number): number {
  return Math.max(1, Math.round((1 - size / original) * 100))
}
