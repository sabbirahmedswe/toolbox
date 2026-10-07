import { useState } from 'react'
import { downloadBlob, postForFile, type FileResult } from '../api/client'
import FileDropzone from '../components/FileDropzone'
import ImageThumb from '../components/ImageThumb'
import SortableFileList from '../components/SortableFileList'
import { addWithinLimits, type FileItem } from '../fileItems'

const ACCEPT = { 'image/jpeg': ['.jpg', '.jpeg'], 'image/png': ['.png'] }

export default function ImagesToPdfPage() {
  const [items, setItems] = useState<FileItem[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<FileResult | null>(null)

  function addFiles(files: File[]) {
    const next = addWithinLimits(items, files)
    setItems(next.items)
    setError(next.error)
  }

  async function convert() {
    setBusy(true)
    setError(null)
    const form = new FormData()
    items.forEach((i) => form.append('files', i.file))
    try {
      const res = await postForFile('/api/images-to-pdf', form, 'images.pdf')
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
        <h1>Your images have been converted to PDF!</h1>
        <p className="subtitle">The download should start automatically.</p>
        <div className="actions">
          <button className="btn" onClick={() => downloadBlob(result.blob, result.filename)}>
            Download PDF
          </button>
          <button className="btn btn-secondary" onClick={reset}>
            Convert more images
          </button>
        </div>
      </section>
    )
  }

  return (
    <section className="tool-page">
      <h1>Image to PDF</h1>
      <p className="subtitle">Convert JPG and PNG images to PDF, one image per page. Drag images to reorder them.</p>

      {items.length === 0 ? (
        <FileDropzone
          accept={ACCEPT}
          onFiles={addFiles}
          onReject={setError}
          label="Select images"
          hint="or drop JPG or PNG images here"
        />
      ) : (
        <>
          <SortableFileList
            items={items}
            onChange={setItems}
            disabled={busy}
            renderPreview={(item) => <ImageThumb file={item.file} />}
          />
          {!busy && <FileDropzone accept={ACCEPT} onFiles={addFiles} onReject={setError} label="Add more images" compact />}
          <div className="actions">
            <button className="btn" onClick={convert} disabled={busy}>
              {busy ? 'Converting…' : 'Convert to PDF'}
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
