import { useState } from 'react'
import { downloadBlob, postForFile, type FileResult } from '../api/client'
import FileDropzone from '../components/FileDropzone'
import SortableFileList from '../components/SortableFileList'
import { addWithinLimits, type FileItem } from '../fileItems'

const ACCEPT = { 'application/pdf': ['.pdf'] }

export default function MergePage() {
  const [items, setItems] = useState<FileItem[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<FileResult | null>(null)

  function addFiles(files: File[]) {
    const next = addWithinLimits(items, files)
    setItems(next.items)
    setError(next.error)
  }

  async function merge() {
    setBusy(true)
    setError(null)
    const form = new FormData()
    items.forEach((i) => form.append('files', i.file))
    try {
      const res = await postForFile('/api/merge', form, 'merged.pdf')
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
        <h1>Your PDFs have been merged!</h1>
        <p className="subtitle">The download should start automatically.</p>
        <div className="actions">
          <button className="btn" onClick={() => downloadBlob(result.blob, result.filename)}>
            Download merged PDF
          </button>
          <button className="btn btn-secondary" onClick={reset}>
            Merge more files
          </button>
        </div>
      </section>
    )
  }

  return (
    <section className="tool-page">
      <h1>Merge PDF files</h1>
      <p className="subtitle">Combine PDFs in the order you want. Drag files to reorder them.</p>

      {items.length === 0 ? (
        <FileDropzone accept={ACCEPT} onFiles={addFiles} onReject={setError} label="Select PDF files" hint="or drop PDFs here" />
      ) : (
        <>
          <SortableFileList items={items} onChange={setItems} disabled={busy} />
          {!busy && <FileDropzone accept={ACCEPT} onFiles={addFiles} onReject={setError} label="Add more files" compact />}
          <div className="actions">
            <button className="btn" onClick={merge} disabled={busy || items.length < 2}>
              {busy ? 'Merging…' : 'Merge PDF'}
            </button>
          </div>
          {items.length < 2 && <p className="muted">Add at least 2 PDFs to merge.</p>}
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
