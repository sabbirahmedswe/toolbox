// The same stacked-layers mark as public/favicon.svg (a static file, so it can't share this); keep the paths in sync.
// Drawn inline so it follows the theme: a tile in --logo-text with the layers in --logo-cutout.
export default function Logo() {
  return (
    <svg className="logo-icon" viewBox="0 0 64 64" aria-hidden="true">
      <rect className="logo-tile" width="64" height="64" rx="16" />
      <g className="logo-layers" fill="none" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 38l18 9 18-9" />
        <path d="M14 31l18 9 18-9" />
        <path d="M32 15l18 9-18 9-18-9z" />
      </g>
    </svg>
  )
}
