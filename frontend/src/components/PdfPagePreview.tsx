import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { openPdfPages, type PdfPages } from '../pdfThumbnail'

// Matches the max width of .page-tile-image in index.css.
const MAX_PAGE_WIDTH = 560
// height / width of the placeholder, until a page's real shape is known.
const A4_ASPECT = Math.SQRT2

/** Watches page tiles scrolling into and out of view, with one observer for all of them (a PDF can have thousands). */
interface Watcher {
  /** Calls `onChange` when `el` scrolls into or out of view; returns a function that stops watching. */
  watch: (el: Element, onChange: (visible: boolean) => void) => () => void
  disconnect: () => void
}

function createWatcher(): Watcher {
  const callbacks = new Map<Element, (visible: boolean) => void>()
  let observer: IntersectionObserver | undefined
  return {
    watch(el, onChange) {
      // Tiles scroll within their grid, their parent. The observer is made on first use, and again if the grid is
      // replaced.
      const root = el.parentElement
      if (observer?.root !== root) {
        observer?.disconnect()
        observer = new IntersectionObserver(
          (entries) => entries.forEach((e) => callbacks.get(e.target)?.(e.isIntersecting)),
          { root, rootMargin: '100% 0px' },
        )
      }
      const current = observer
      callbacks.set(el, onChange)
      current.observe(el)
      return () => {
        current.unobserve(el)
        callbacks.delete(el)
      }
    },
    disconnect() {
      observer?.disconnect()
      observer = undefined
      callbacks.clear()
    },
  }
}

/** Every page of `file`, one below another, rendered as they scroll into view. */
export default function PdfPagePreview({ file }: { file: File }) {
  const [pdf, setPdf] = useState<{ file: File; pages: PdfPages | null } | null>(null)
  const [watcher] = useState(createWatcher)

  useEffect(() => {
    const controller = new AbortController()
    openPdfPages(file, controller.signal).then(
      (pages) => setPdf({ file, pages }),
      () => {
        if (!controller.signal.aborted) setPdf({ file, pages: null })
      },
    )
    // Closes the PDF too.
    return () => controller.abort()
  }, [file])

  useEffect(() => () => watcher.disconnect(), [watcher])

  const pages = pdf?.file === file ? pdf.pages : undefined

  if (pages === undefined) return <p className="page-preview-status">Loading preview…</p>
  if (pages === null) return <p className="page-preview-status">This PDF can't be previewed.</p>

  return (
    <ol className="page-grid" aria-label="Pages">
      {Array.from({ length: pages.numPages }, (_, i) => (
        <PreviewPage key={i} pages={pages} n={i + 1} watch={watcher.watch} />
      ))}
    </ol>
  )
}

function PreviewPage({ pages, n, watch }: { pages: PdfPages; n: number; watch: Watcher['watch'] }) {
  const ref = useRef<HTMLLIElement>(null)
  const [url, setUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  // height / width, once the page has rendered; kept when the image is dropped so the layout doesn't jump.
  const [aspect, setAspect] = useState<number | null>(null)

  useEffect(() => {
    if (failed) return
    const tile = ref.current!
    let controller: AbortController | undefined
    const stopWatching = watch(tile, (visible) => {
      // Render near the view; a page that moves well away drops its image (they're large) and renders again if it
      // comes back.
      if (!visible) {
        controller?.abort()
        controller = undefined
        setUrl(null)
      } else if (!controller) {
        const current = (controller = new AbortController())
        // Each page is sized (in CSS) to fit the visible part of the grid, up to MAX_PAGE_WIDTH; render to fit that.
        const grid = tile.parentElement!
        const size = { width: Math.min(grid.clientWidth, MAX_PAGE_WIDTH), height: grid.clientHeight }
        pages.renderPage(n, size, current.signal).then(
          (blob) => {
            if (!current.signal.aborted) setUrl(URL.createObjectURL(blob))
          },
          () => {
            if (!current.signal.aborted) setFailed(true)
          },
        )
      }
    })
    return () => {
      stopWatching()
      controller?.abort()
    }
  }, [pages, n, watch, failed])

  useEffect(() => (url ? () => URL.revokeObjectURL(url) : undefined), [url])

  return (
    <li ref={ref} className="page-tile">
      <div
        className="page-tile-image"
        style={{ '--aspect': aspect ?? A4_ASPECT } as CSSProperties}
      >
        {url ? (
          <img
            src={url}
            alt={`Page ${n}`}
            onLoad={(e) => setAspect(e.currentTarget.naturalHeight / e.currentTarget.naturalWidth)}
          />
        ) : (
          <span className="page-tile-placeholder" title={failed ? "This page couldn't be previewed" : undefined}>
            {failed && '?'}
          </span>
        )}
      </div>
      <span className="page-number" aria-hidden={!!url}>
        Page {n}
      </span>
    </li>
  )
}
