import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

type PdfJs = typeof import('pdfjs-dist')

// pdf.js is ~1 MB, so it's only loaded once the first PDF thumbnail is needed.
// All documents share one worker instead of starting a worker each.
let lib: Promise<{ pdfjs: PdfJs; worker: InstanceType<PdfJs['PDFWorker']> }> | undefined

function loadPdfJs() {
  lib ??= import('pdfjs-dist').then(
    (pdfjs) => {
      pdfjs.GlobalWorkerOptions.workerSrc = workerUrl
      return { pdfjs, worker: new pdfjs.PDFWorker() }
    },
    (err: unknown) => {
      lib = undefined // allow a retry, e.g. after a failed chunk download
      throw err
    },
  )
  return lib
}

// Render a few files at a time so dropping 20 large PDFs doesn't load them all into memory at once.
const MAX_CONCURRENT = 2
let active = 0
const waiting: (() => void)[] = []

async function withSlot<T>(fn: () => Promise<T>): Promise<T> {
  if (active < MAX_CONCURRENT) active++
  else await new Promise<void>((resolve) => waiting.push(resolve))
  try {
    return await fn()
  } finally {
    // Hand the slot straight to the next waiter so a new caller can't jump in between.
    const next = waiting.shift()
    if (next) next()
    else active--
  }
}

// Images larger than this are skipped (left blank) rather than decoded; plenty for a thumbnail.
const MAX_IMAGE_PIXELS = 25_000_000

/**
 * Draw the first page of `file` into `canvas`, scaled to fit a `width` x `height` CSS box.
 * Rejects if the PDF can't be read (e.g. encrypted or corrupt) or `signal` aborts.
 */
export function renderPdfThumbnail(
  file: File,
  canvas: HTMLCanvasElement,
  box: { width: number; height: number },
  signal: AbortSignal,
): Promise<void> {
  return withSlot(async () => {
    signal.throwIfAborted()
    const { pdfjs, worker } = await loadPdfJs()
    const data = new Uint8Array(await file.arrayBuffer())
    signal.throwIfAborted()

    const task = pdfjs.getDocument({ data, worker, maxImageSize: MAX_IMAGE_PIXELS, enableXfa: false })
    // Destroying the loading task also cancels a render in progress.
    const abort = () => void task.destroy()
    signal.addEventListener('abort', abort)
    try {
      const doc = await task.promise
      const page = await doc.getPage(1)
      const base = page.getViewport({ scale: 1 })
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      const viewport = page.getViewport({
        scale: Math.min(box.width / base.width, box.height / base.height) * dpr,
      })
      canvas.width = Math.max(1, Math.floor(viewport.width))
      canvas.height = Math.max(1, Math.floor(viewport.height))
      await page.render({ canvas, viewport }).promise
    } finally {
      signal.removeEventListener('abort', abort)
      await task.destroy()
    }
  })
}
