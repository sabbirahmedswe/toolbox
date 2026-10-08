import type { ReactNode } from 'react'
import { formatBytes } from '../api/client'
import PdfPagePreview from './PdfPagePreview'

interface Props {
  file: File
  /** Extra details shown after the size, e.g. the page count. */
  detail?: ReactNode
  /** Shows a × button that discards the file when set; leave unset while the file is being processed. */
  onRemove?: () => void
}

/** The single PDF picked on a one-file tool page: its name and size above a preview of its pages. */
export default function FilePanel({ file, detail, onRemove }: Props) {
  return (
    <div className="file-panel">
      <div className="file-panel-header">
        <div className="file-panel-info">
          <div className="file-name" title={file.name}>
            {file.name}
          </div>
          <div className="file-size">
            {formatBytes(file.size)}
            {detail && <> · {detail}</>}
          </div>
        </div>
        {onRemove && (
          <button className="file-panel-remove" onClick={onRemove} aria-label="Remove file" title="Remove file">
            ×
          </button>
        )}
      </div>
      <PdfPagePreview file={file} />
    </div>
  )
}
