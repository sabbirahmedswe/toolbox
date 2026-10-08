import type { KeyboardEvent, ReactNode } from 'react'
import { formatBytes } from '../api/client'

interface Props {
  file: File
  /** The thumbnail shown above the name. */
  preview: ReactNode
  /** Shows a zoom button when set; leave unset while the file is being processed. */
  onZoom?: () => void
  /** Shows a remove button when set; leave unset while the file is being processed. */
  onRemove?: () => void
}

/** The single file picked on a one-file tool page: a card like those in SortableFileList, but not draggable. */
export default function FileCard(props: Props) {
  return (
    <div className="file-card file-card-static">
      <FileCardBody {...props} />
    </div>
  )
}

/** A file card's contents: corner buttons (shown on hover), thumbnail, name and size. */
export function FileCardBody({ file, preview, onZoom, onRemove }: Props) {
  // Keys on the buttons must not reach a sortable card's keyboard drag handler (Space/Enter would pick it up).
  const stopKeys = (e: KeyboardEvent) => e.stopPropagation()
  return (
    <>
      {(onZoom || onRemove) && (
        <div className="file-card-actions">
          {onZoom && (
            <button
              type="button"
              className="icon-btn file-card-action"
              aria-label={`Zoom in on ${file.name}`}
              onClick={onZoom}
              onKeyDown={stopKeys}
            >
              <span className="card-tooltip" aria-hidden="true">
                Zoom in
              </span>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                <circle cx="11" cy="11" r="6.5" />
                <path d="M16 16l4.5 4.5M11 8.5v5M8.5 11h5" />
              </svg>
            </button>
          )}
          {onRemove && (
            <button
              type="button"
              className="icon-btn file-card-action"
              aria-label={`Remove ${file.name}`}
              onClick={onRemove}
              onKeyDown={stopKeys}
            >
              <span className="card-tooltip" aria-hidden="true">
                Remove file
              </span>
              <CloseIcon />
            </button>
          )}
        </div>
      )}
      <div className="file-preview">{preview}</div>
      <div className="file-card-name" title={file.name}>
        {file.name}
      </div>
      <div className="file-size">{formatBytes(file.size)}</div>
    </>
  )
}

/** A drawn ×: the text glyph sits off-centre in a round button. */
export function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
      <path d="M7 7l10 10M17 7L7 17" />
    </svg>
  )
}
