import { useState, type ReactNode } from 'react'
import type { Accept } from 'react-dropzone'
import { downloadBlob, postForFile, type FileResult } from '../api/client'
import { addWithinLimits, type FileItem } from '../fileItems'
import FileDropzone from './FileDropzone'
import SortableFileList from './SortableFileList'

interface Props {
  endpoint: string
  fallbackName: string
  accept: Accept
  minFiles: number
  title: string
  subtitle: string
  selectLabel: string
  hint: string
  addMoreLabel: string
  minFilesHint?: string
  /** Shown above the file list once there are at least two files to reorder. */
  reorderHint?: string
  actionLabel: string
  busyLabel: string
  doneTitle: string
  downloadLabel: string
  againLabel: string
  renderPreview?: (item: FileItem) => ReactNode
}

/** Shared page for tools that upload an ordered list of files and download one PDF back. */
export default function MultiFileTool(props: Props) {
  const [items, setItems] = useState<FileItem[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<FileResult | null>(null)

  function addFiles(files: File[]) {
    const next = addWithinLimits(items, files)
    setItems(next.items)
    setError(next.error)
  }

  async function submit() {
    setBusy(true)
    setError(null)
    const form = new FormData()
    items.forEach((i) => form.append('files', i.file))
    try {
      const res = await postForFile(props.endpoint, form, props.fallbackName)
      setResult(res)
      downloadBlob(res.blob, res.filename)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  function reset() {
    setItems([])
    setResult(null)
    setError(null)
  }

  if (result) {
    return (
      <section className="tool-page">
        <h1>{props.doneTitle}</h1>
        <p className="subtitle">The download should start automatically.</p>
        <div className="actions">
          <button className="btn" onClick={() => downloadBlob(result.blob, result.filename)}>
            {props.downloadLabel}
          </button>
          <button className="btn btn-secondary" onClick={reset}>
            {props.againLabel}
          </button>
        </div>
      </section>
    )
  }

  const tooFew = items.length < props.minFiles

  return (
    <section className="tool-page">
      <h1>{props.title}</h1>
      <p className="subtitle">{props.subtitle}</p>

      {items.length === 0 ? (
        <FileDropzone accept={props.accept} onFiles={addFiles} onReject={setError} label={props.selectLabel} hint={props.hint} />
      ) : (
        <>
          {props.reorderHint && items.length > 1 && !busy && (
            <p className="reorder-hint">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M7 4v16M3 8l4-4 4 4M17 20V4M13 16l4 4 4-4" />
              </svg>
              {props.reorderHint}
            </p>
          )}
          <SortableFileList items={items} onChange={setItems} disabled={busy} renderPreview={props.renderPreview} />
          {!busy && (
            <FileDropzone accept={props.accept} onFiles={addFiles} onReject={setError} label={props.addMoreLabel} compact />
          )}
          <div className="actions">
            <button className="btn btn-large" onClick={submit} disabled={busy || tooFew}>
              {busy ? props.busyLabel : props.actionLabel}
              {!busy && (
                <span className="btn-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24">
                    <path d="M5 12h14M13 6l6 6-6 6" />
                  </svg>
                </span>
              )}
            </button>
          </div>
          {tooFew && props.minFilesHint && <p className="muted">{props.minFilesHint}</p>}
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
