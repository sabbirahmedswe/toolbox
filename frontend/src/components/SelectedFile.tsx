import type { ReactNode } from 'react'
import { formatBytes } from '../api/client'

interface Props {
  file: File
  /** Extra details shown after the size, e.g. the page count. */
  detail?: ReactNode
  /** Shows a Change button when set; leave unset while the file is being processed. */
  onChange?: () => void
}

/** The single PDF picked on a one-file tool page. */
export default function SelectedFile({ file, detail, onChange }: Props) {
  return (
    <div className="selected-file">
      <div className="file-badge">PDF</div>
      <div className="selected-file-info">
        <div className="file-name" title={file.name}>
          {file.name}
        </div>
        <div className="file-size">
          {formatBytes(file.size)}
          {detail && <> · {detail}</>}
        </div>
      </div>
      {onChange && (
        <button className="btn btn-secondary btn-small" onClick={onChange}>
          Change
        </button>
      )}
    </div>
  )
}
