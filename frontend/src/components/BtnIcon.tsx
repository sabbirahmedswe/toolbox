const PATHS = {
  next: 'M5 12h14M13 6l6 6-6 6',
  download: 'M12 5v14M6 13l6 6 6-6',
}

/** Round arrow badge shown inside a large primary button. */
export default function BtnIcon({ kind }: { kind: keyof typeof PATHS }) {
  return (
    <span className={`btn-icon btn-icon-${kind}`} aria-hidden="true">
      <svg viewBox="0 0 24 24">
        <path d={PATHS[kind]} />
      </svg>
    </span>
  )
}
