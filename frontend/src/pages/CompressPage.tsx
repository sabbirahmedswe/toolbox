import { useEffect, useState } from 'react'
import { downloadBlob, formatBytes, postForFile, postForJson, type FileResult } from '../api/client'
import BtnIcon from '../components/BtnIcon'
import FileDropzone from '../components/FileDropzone'
import { addWithinLimits } from '../fileItems'

const ACCEPT = { 'application/pdf': ['.pdf'] }

type Level = 'low' | 'medium' | 'high'

const LEVELS: { value: Level; title: string; description: string }[] = [
  { value: 'high', title: 'Extreme compression', description: 'Smallest file, lower quality' },
  { value: 'medium', title: 'Recommended', description: 'Good quality, good compression' },
  { value: 'low', title: 'Less compression', description: 'High quality, larger file' },
]

/** Size each level would produce, or null when the estimate failed. */
interface Estimate {
  file: File
  sizes: Record<Level, number> | null
}

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
  const [estimate, setEstimate] = useState<Estimate | null>(null)

  // Ignore an estimate left over from a previously selected file.
  const current = estimate?.file === file ? estimate : null
  // Not while compressing: the estimate would compete with it for the server's CPU. Cancelling stops
  // the server at its next level; if compressing fails, the estimate starts again.
  const wantEstimate = file !== null && !current && !busy && !outcome

  useEffect(() => {
    if (!file || !wantEstimate) return
    const controller = new AbortController()
    const form = new FormData()
    form.append('file', file)
    postForJson<{ sizes: Record<Level, number> }>('/api/compress/estimate', form, controller.signal)
      .then((res) => setEstimate({ file, sizes: res.sizes }))
      .catch(() => {
        // An estimate is a nice-to-have: on failure just leave it out; Compress reports real errors.
        if (!controller.signal.aborted) setEstimate({ file, sizes: null })
      })
    return () => controller.abort()
  }, [file, wantEstimate])

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

  return (
    <section className="tool-page">
      <h1>Compress a PDF</h1>
      <p className="subtitle">Shrink your PDF and choose how much quality to trade for a smaller file.</p>

      {!file ? (
        <FileDropzone
          accept={ACCEPT}
          multiple={false}
          onFiles={selectFile}
          onReject={setError}
          label="Select PDF file"
          hint="or drop a PDF here"
        />
      ) : (
        <>
          <div className="selected-file">
            <div className="file-badge">PDF</div>
            <div className="selected-file-info">
              <div className="file-name" title={file.name}>
                {file.name}
              </div>
              <div className="file-size">{formatBytes(file.size)}</div>
            </div>
            {!busy && (
              <button className="btn btn-secondary btn-small" onClick={reset}>
                Change
              </button>
            )}
          </div>

          <fieldset className="levels" disabled={busy}>
            <legend>Compression level</legend>
            {LEVELS.map((l) => (
              <label key={l.value} className={`level${level === l.value ? ' level-selected' : ''}`}>
                <input
                  type="radio"
                  name="level"
                  value={l.value}
                  checked={level === l.value}
                  onChange={() => setLevel(l.value)}
                />
                <span className="level-title">{l.title}</span>
                <span className="muted">{l.description}</span>
                <LevelEstimate original={file.size} size={current?.sizes?.[l.value]} loading={!current} />
              </label>
            ))}
          </fieldset>

          <div className="actions">
            <button className="btn btn-large" onClick={compress} disabled={busy}>
              {busy ? 'Compressing…' : 'Compress PDF'}
              {!busy && <BtnIcon kind="next" />}
            </button>
          </div>
        </>
      )}

      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
    </section>
  )
}

function LevelEstimate({ original, size, loading }: { original: number; size?: number; loading: boolean }) {
  if (loading) return <span className="level-estimate level-estimate-muted">Estimating…</span>
  if (size === undefined) return <span className="level-estimate level-estimate-muted">Estimate unavailable</span>
  if (size >= original) return <span className="level-estimate">No smaller</span>
  return (
    <span className="level-estimate">
      ≈ {formatBytes(size)} <span className="level-estimate-percent">−{savingsPercent(original, size)}%</span>
    </span>
  )
}

/** Percent saved; at least 1 so a tiny but real saving isn't shown as 0%. */
function savingsPercent(original: number, size: number): number {
  return Math.max(1, Math.round((1 - size / original) * 100))
}
