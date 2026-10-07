import { useDropzone, type Accept, type FileRejection } from 'react-dropzone'

interface Props {
  accept: Accept
  multiple?: boolean
  onFiles: (files: File[]) => void
  onReject?: (message: string) => void
  /** Compact variant used for "add more files" once some are selected. */
  compact?: boolean
  label: string
  hint?: string
}

export default function FileDropzone({ accept, multiple = true, onFiles, onReject, compact, label, hint }: Props) {
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

  return (
    <div
      {...getRootProps({
        className: `dropzone${compact ? ' dropzone-compact' : ''}${isDragActive ? ' dropzone-active' : ''}`,
      })}
    >
      <input {...getInputProps()} />
      {compact ? (
        <span className="dropzone-add">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 5v14M5 12h14" />
          </svg>
          {label}
        </span>
      ) : (
        <>
          <span className="btn">{label}</span>
          <p className="muted">{isDragActive ? 'Drop files here' : (hint ?? 'or drop files here')}</p>
        </>
      )}
    </div>
  )
}
