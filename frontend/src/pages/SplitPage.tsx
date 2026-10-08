import { useEffect, useId, useState } from 'react'
import { downloadBlob, formatBytes, postForFile, type FileResult } from '../api/client'
import BtnIcon from '../components/BtnIcon'
import FileDropzone from '../components/FileDropzone'
import PdfPagePreview from '../components/PdfPagePreview'
import { addWithinLimits, MAX_RANGES_LENGTH, MAX_SPLIT_PARTS } from '../fileItems'
import { parseRanges, plural } from '../pageRanges'
import { countPdfPages } from '../pdfThumbnail'

const ACCEPT = { 'application/pdf': ['.pdf'] }

type Mode = 'ranges' | 'every'

const MODES: { value: Mode; title: string; description: string }[] = [
  { value: 'ranges', title: 'Custom ranges', description: 'Pick the pages for each PDF' },
  { value: 'every', title: 'Fixed ranges', description: 'A new PDF every few pages' },
]

/** Page count of a file, or null when pdf.js couldn't read it (the backend still can, or reports why not). */
interface PageCount {
  file: File
  count: number | null
}

/** What the settings would produce: the number of PDFs (null if unknown), or why they can't be used. */
type Plan = { parts: number | null } | { error: string }

export default function SplitPage() {
  const [file, setFile] = useState<File | null>(null)
  const [pages, setPages] = useState<PageCount | null>(null)
  const [mode, setMode] = useState<Mode>('ranges')
  const [ranges, setRanges] = useState('')
  const [merge, setMerge] = useState(false)
  const [every, setEvery] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<FileResult | null>(null)
  const inputId = useId()
  const hintId = useId()

  // undefined while counting; ignores a count left over from a previously selected file.
  const pageCount = pages?.file === file ? pages.count : undefined

  useEffect(() => {
    if (!file) return
    const controller = new AbortController()
    countPdfPages(file, controller.signal).then(
      (count) => setPages({ file, count }),
      () => {
        if (!controller.signal.aborted) setPages({ file, count: null })
      },
    )
    return () => controller.abort()
  }, [file])

  const plan = planSplit(mode, ranges, merge, every, pageCount ?? null)

  function selectFile(files: File[]) {
    const next = addWithinLimits([], files.slice(0, 1))
    setFile(next.items[0]?.file ?? null)
    setError(next.error)
  }

  async function split() {
    if (!file) return
    setBusy(true)
    setError(null)
    const form = new FormData()
    form.append('file', file)
    form.append('mode', mode)
    if (mode === 'ranges') {
      form.append('ranges', ranges)
      form.append('merge', String(merge))
    } else {
      form.append('every', every)
    }
    try {
      const res = await postForFile('/api/split', form, 'split.zip')
      setResult(res)
      downloadBlob(res.blob, res.filename)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  function reset() {
    setFile(null)
    setMode('ranges')
    setRanges('')
    setMerge(false)
    setEvery('')
    setResult(null)
    setError(null)
  }

  if (result) {
    const zipped = result.filename.toLowerCase().endsWith('.zip')
    return (
      <section className="tool-page">
        <h1>{zipped ? 'Your PDF has been split!' : 'Your new PDF is ready!'}</h1>
        <p className="subtitle">The download should start automatically.</p>
        <div className="actions">
          <button className="btn btn-large" onClick={() => downloadBlob(result.blob, result.filename)}>
            {zipped ? 'Download ZIP' : 'Download PDF'}
            <BtnIcon kind="download" />
          </button>
          <button className="btn btn-large btn-secondary" onClick={reset}>
            Split another file
          </button>
        </div>
      </section>
    )
  }

  const invalid = 'error' in plan
  // Don't flag an empty box as a mistake before anything is typed.
  const typed = (mode === 'ranges' ? ranges : every).trim() !== ''
  const showError = invalid && (typed || pageCount === 0)

  if (!file) {
    return (
      <section className="tool-page">
        <h1>Split a PDF</h1>
        <p className="subtitle">Separate a PDF into several files by page range, or pull out just the pages you need.</p>
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
        <div className="split-file">
          <div className="split-file-header">
            <div className="selected-file-info">
              <div className="file-name" title={file.name}>
                {file.name}
              </div>
              <div className="file-size">
                {formatBytes(file.size)}
                {pageCount === undefined
                  ? ' · Counting pages…'
                  : pageCount !== null && ` · ${plural(pageCount, 'page')}`}
              </div>
            </div>
            {!busy && (
              <button className="split-file-remove" onClick={reset} aria-label="Remove file" title="Remove file">
                ×
              </button>
            )}
          </div>
          <PdfPagePreview file={file} />
        </div>
      </div>

      <aside className="workspace-sidebar">
        <div className="workspace-sidebar-body">
          <h1>Split</h1>

          <fieldset className="choices" disabled={busy}>
            <legend>Split mode</legend>
            {MODES.map((m) => (
              <label key={m.value} className={`choice${mode === m.value ? ' choice-selected' : ''}`}>
                <input
                  type="radio"
                  name="mode"
                  value={m.value}
                  checked={mode === m.value}
                  onChange={() => setMode(m.value)}
                />
                <span className="choice-title">{m.title}</span>
                <span className="muted">{m.description}</span>
              </label>
            ))}
          </fieldset>

          <fieldset className="split-settings" disabled={busy}>
            {mode === 'ranges' ? (
              <>
                <label className="field-label" htmlFor={inputId}>
                  Page ranges
                </label>
                <input
                  id={inputId}
                  className="text-input"
                  value={ranges}
                  onChange={(e) => setRanges(e.target.value)}
                  placeholder="e.g. 1-3, 5, 8-10"
                  maxLength={MAX_RANGES_LENGTH}
                  autoComplete="off"
                  spellCheck={false}
                  aria-invalid={showError}
                  aria-describedby={hintId}
                />
                <p id={hintId} className={`field-hint${showError ? ' field-hint-error' : ''}`}>
                  {showError && 'error' in plan
                    ? plan.error
                    : merge
                      ? 'Separate ranges with commas. Their pages go into one PDF, in this order.'
                      : 'Separate ranges with commas. Each range becomes its own PDF.'}
                </p>
                <label className="checkbox">
                  <input type="checkbox" checked={merge} onChange={(e) => setMerge(e.target.checked)} />
                  Put all ranges in one PDF
                </label>
              </>
            ) : (
              <>
                <label className="field-label" htmlFor={inputId}>
                  Pages per PDF
                </label>
                <input
                  id={inputId}
                  className="text-input text-input-narrow"
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={pageCount ?? undefined}
                  step={1}
                  value={every}
                  placeholder="e.g. 5"
                  onChange={(e) => setEvery(e.target.value)}
                  aria-invalid={showError}
                  aria-describedby={hintId}
                />
                <p id={hintId} className={`field-hint${showError ? ' field-hint-error' : ''}`}>
                  {showError && 'error' in plan ? plan.error : 'The last PDF gets whatever pages are left.'}
                </p>
              </>
            )}
          </fieldset>

          {'parts' in plan && plan.parts !== null && (
            <p className="split-summary">
              You'll get {plan.parts === 1 ? 'one PDF' : `${plan.parts} PDFs in a ZIP file`}.
            </p>
          )}

          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
        </div>

        <div className="workspace-sidebar-footer">
          <button className="btn btn-large" onClick={split} disabled={busy || invalid}>
            {busy ? 'Splitting…' : 'Split PDF'}
            {!busy && <BtnIcon kind="next" />}
          </button>
        </div>
      </aside>
    </section>
  )
}

/** Check the settings the way the backend will. `pageCount` is null when it isn't known (yet). */
function planSplit(mode: Mode, ranges: string, merge: boolean, every: string, pageCount: number | null): Plan {
  if (pageCount === 0) return { error: 'This PDF has no pages to split.' }
  let parts: number | null
  if (mode === 'ranges') {
    const parsed = parseRanges(ranges, pageCount)
    if ('error' in parsed) return parsed
    parts = merge ? 1 : parsed.ranges.length
  } else {
    const n = Number(every)
    if (!/^[0-9]+$/.test(every.trim()) || n < 1) return { error: 'Enter a whole number of pages, 1 or more.' }
    parts = pageCount === null ? null : Math.ceil(pageCount / n)
  }
  if (parts !== null && parts > MAX_SPLIT_PARTS) {
    const hint = mode === 'ranges' ? 'Use fewer ranges.' : 'Use more pages per file.'
    return { error: `This would create ${parts} PDFs, more than the limit of ${MAX_SPLIT_PARTS}. ${hint}` }
  }
  return { parts }
}
