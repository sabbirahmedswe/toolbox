import { useState, type ReactNode } from 'react'
import type { Accept } from 'react-dropzone'
import { downloadBlob, postForFile, type FileResult } from '../api/client'
import { addWithinLimits, type FileItem } from '../fileItems'
import BtnIcon from './BtnIcon'
import FileDropzone from './FileDropzone'
import SortableFileList from './SortableFileList'
import ToolSidebar from './ToolSidebar'

interface Props {
  endpoint: string
  fallbackName: string
  accept: Accept
  minFiles: number
  title: string
  subtitle: string
  /** Heading of the settings panel, e.g. "Merge". */
  sidebarTitle: string
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
  /** Adds a zoom button to each card; see SortableFileList. */
  renderZoom?: (item: FileItem, onClose: () => void) => ReactNode
  /** Shows a button that sorts the files by name. */
  sortByName?: boolean
}

// Natural order, so "file 2" comes before "file 10", ignoring case and accents.
const byName = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })

function sortedByName(items: FileItem[], descending: boolean): FileItem[] {
  const sorted = [...items].sort((a, b) => byName.compare(a.file.name, b.file.name))
  return descending ? sorted.reverse() : sorted
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
          <button className="btn btn-large" onClick={() => downloadBlob(result.blob, result.filename)}>
            {props.downloadLabel}
            <BtnIcon kind="download" />
          </button>
          <button className="btn btn-large btn-secondary" onClick={reset}>
            {props.againLabel}
          </button>
        </div>
      </section>
    )
  }

  const tooFew = items.length < props.minFiles
  // Like a column header: sort A–Z, and once in that order, Z–A.
  const ascending = sortedByName(items, false)
  const nextDescending = items.every((item, i) => item === ascending[i])
  const sortLabel = nextDescending ? 'Sort by name, Z to A' : 'Sort by name, A to Z'
  // Too few files to submit: say why the button is disabled. Otherwise, with files to reorder, say how.
  const notice = tooFew ? props.minFilesHint : items.length > 1 ? props.reorderHint : undefined

  if (items.length === 0) {
    return (
      <section className="tool-page">
        <h1>{props.title}</h1>
        <p className="subtitle">{props.subtitle}</p>
        <FileDropzone accept={props.accept} onFiles={addFiles} onReject={setError} label={props.selectLabel} hint={props.hint} />
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
      <div className="workspace-main workspace-main-files">
        {!busy && (
          <div className="file-toolbar">
            <FileDropzone
              accept={props.accept}
              onFiles={addFiles}
              onReject={setError}
              label={props.addMoreLabel}
              floating
              badge={items.length}
            />
            {props.sortByName && items.length > 1 && (
              <button className="fab" onClick={() => setItems(sortedByName(items, nextDescending))} aria-label={sortLabel}>
                <span className="fab-tooltip" aria-hidden="true">
                  Order by name
                </span>
                {/* The order a click gives: a downward arrow beside A over Z, or Z over A. */}
                <svg className="sort-arrow" viewBox="6 3 12 18" aria-hidden="true">
                  <path d="M12 4v16M8 16l4 4 4-4" />
                </svg>
                <span className="sort-letters" aria-hidden="true">
                  <span>{nextDescending ? 'Z' : 'A'}</span>
                  <span>{nextDescending ? 'A' : 'Z'}</span>
                </span>
              </button>
            )}
          </div>
        )}
        <div className="workspace-files">
          <SortableFileList
            items={items}
            onChange={setItems}
            disabled={busy}
            renderPreview={props.renderPreview}
            renderZoom={props.renderZoom}
          />
        </div>
      </div>

      <ToolSidebar
        title={props.sidebarTitle}
        action={
          <button className="btn btn-large" onClick={submit} disabled={busy || tooFew}>
            {busy ? props.busyLabel : props.actionLabel}
            {!busy && <BtnIcon kind="next" />}
          </button>
        }
      >
        {notice && !busy && (
          <p className="reorder-hint">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="12" cy="12" r="9" />
              <path d="M12 11v5M12 8h.01" />
            </svg>
            {notice}
          </p>
        )}
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
      </ToolSidebar>
    </section>
  )
}
