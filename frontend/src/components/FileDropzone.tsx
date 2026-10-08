import { useDropzone, type Accept, type FileRejection } from 'react-dropzone'

interface Props {
  accept: Accept
  multiple?: boolean
  onFiles: (files: File[]) => void
  onReject?: (message: string) => void
  /** A round "+" button used for "add more files" once some are selected; `label` becomes its tooltip. */
  floating?: boolean
  /** With `floating`: a count shown as a badge on the button, e.g. the files picked so far. */
  badge?: number
  label: string
  hint?: string
}

export default function FileDropzone({ accept, multiple = true, onFiles, onReject, floating, badge, label, hint }: Props) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept,
    multiple,
    onDrop: (accepted: File[], rejected: FileRejection[]) => {
      if (accepted.length) onFiles(accepted)
      if (rejected.length && onReject) {
        if (rejected.some((r) => r.errors.some((e) => e.code === 'too-many-files'))) {
          onReject('Please select only one file.')
          return
        }
        const names = rejected.map((r) => r.file.name).join(', ')
        onReject(`Unsupported file${rejected.length > 1 ? 's' : ''}: ${names}`)
      }
    },
  })

  if (floating) {
    return (
      <div
        {...getRootProps({
          className: `fab fab-primary${isDragActive ? ' fab-active' : ''}`,
          role: 'button',
          'aria-label': badge === undefined ? label : `${label} (${badge} selected)`,
        })}
      >
        <input {...getInputProps()} />
        <span className="fab-tooltip" aria-hidden="true">
          {label}
        </span>
        {badge !== undefined && (
          <span className="fab-badge" aria-hidden="true">
            {badge}
          </span>
        )}
        <svg className="fab-plus" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 5v14M5 12h14" />
        </svg>
      </div>
    )
  }

  return (
    <div {...getRootProps({ className: `dropzone${isDragActive ? ' dropzone-active' : ''}` })}>
      <input {...getInputProps()} />
      <span className="btn">{label}</span>
      <p className="muted">{isDragActive ? 'Drop files here' : (hint ?? 'or drop files here')}</p>
    </div>
  )
}
