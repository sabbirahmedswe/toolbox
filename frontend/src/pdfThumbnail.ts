import type { PDFDocumentLoadingTask, PDFDocumentProxy, PDFWorker } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

type PdfJs = typeof import('pdfjs-dist')

// pdf.js is ~1 MB, so it's only loaded once the first PDF is opened.
let lib: Promise<PdfJs> | undefined

function loadPdfJs() {
  lib ??= import('pdfjs-dist').catch((err: unknown) => {
    lib = undefined // allow a retry, e.g. after a failed chunk download
    throw err
  })
  return lib
}

// Open a few files at a time so dropping 20 large PDFs doesn't load them all into memory at once.
const MAX_CONCURRENT = 2
let active = 0
const waiting: (() => void)[] = []

async function acquireSlot(signal: AbortSignal) {
  signal.throwIfAborted()
  if (active < MAX_CONCURRENT) {
    active++
    return
  }
  await new Promise<void>((resolve, reject) => {
    const take = () => {
      signal.removeEventListener('abort', cancel)
      resolve()
    }
    // A removed card leaves the queue straight away instead of waiting for a slot just to give it up.
    const cancel = () => {
      waiting.splice(waiting.indexOf(take), 1)
      reject(signal.reason)
    }
    waiting.push(take)
    signal.addEventListener('abort', cancel, { once: true })
  })
}

function releaseSlot() {
  // Hand the slot straight to the next waiter so a new caller can't jump in between.
  const next = waiting.shift()
  if (next) next()
  else active--
}

/** Settle with `promise`, or reject as soon as `signal` aborts, even if `promise` never settles. */
function abortable<T>(promise: Promise<T>, signal: AbortSignal): Promise<T> {
  return new Promise((resolve, reject) => {
    const onAbort = () => reject(signal.reason)
    if (signal.aborted) return onAbort()
    signal.addEventListener('abort', onAbort, { once: true })
    promise.then(resolve, reject).finally(() => signal.removeEventListener('abort', onAbort))
  })
}

// A PDF that takes longer than this (e.g. a pathological content stream) gets its worker killed.
const RENDER_TIMEOUT_MS = 20_000
// Images larger than this are skipped (left blank) rather than decoded; plenty for a thumbnail.
const MAX_IMAGE_PIXELS = 25_000_000
// Image decoders, CMaps, colour profile and standard fonts, served by the pdfjs-data plugin in vite.config.ts.
const dataUrl = (pdfjs: PdfJs, dir: string) =>
  new URL(`${import.meta.env.BASE_URL}pdfjs-${pdfjs.version}/${dir}/`, location.href).href

/** A PDF opened in its own pdf.js worker. */
interface OpenedPdf {
  doc: PDFDocumentProxy
  /** Aborts when the caller's signal does, or `timeoutMs` after opening started. */
  stop: AbortSignal
  /** Destroy the document and its worker and free the slot. Safe to call more than once. */
  close: () => void
}

/**
 * Open `file` with pdf.js in its own worker. The caller must `close()` it.
 * Rejects if the PDF can't be read (e.g. encrypted or corrupt), takes too long, or `signal` aborts.
 */
async function openPdf(file: File, signal: AbortSignal, timeoutMs: number): Promise<OpenedPdf> {
  await acquireSlot(signal)
  let closed = false
  let webWorker: Worker | undefined
  let worker: PDFWorker | undefined
  let task: PDFDocumentLoadingTask | undefined
  const close = () => {
    if (closed) return
    closed = true
    // Not awaited: a stuck worker never answers, and terminating it below frees everything anyway.
    task?.destroy().catch(() => {})
    worker?.destroy()
    webWorker?.terminate()
    releaseSlot()
  }
  try {
    const pdfjs = await abortable(loadPdfJs(), signal)
    const stop = AbortSignal.any([signal, AbortSignal.timeout(timeoutMs)])
    // Each document gets its own worker, created here rather than by pdf.js: terminating it is the only way to
    // stop a worker stuck on a bad file, and pdf.js would otherwise fall back to parsing on the main thread
    // (for good) if a worker ever failed to start.
    webWorker = new Worker(workerUrl, { type: 'module' })
    worker = pdfjs.PDFWorker.create({ port: webWorker })
    const doc = await abortable(
      (async () => {
        const data = new Uint8Array(await file.arrayBuffer())
        stop.throwIfAborted()
        task = pdfjs.getDocument({
          data,
          worker,
          maxImageSize: MAX_IMAGE_PIXELS,
          enableXfa: false,
          wasmUrl: dataUrl(pdfjs, 'wasm'),
          cMapUrl: dataUrl(pdfjs, 'cmaps'),
          iccUrl: dataUrl(pdfjs, 'iccs'),
          standardFontDataUrl: dataUrl(pdfjs, 'standard_fonts'),
        })
        return task.promise
      })(),
      stop,
    )
    return { doc, stop, close }
  } catch (err) {
    close()
    throw err
  }
}

/** Open `file`, run `run` on the document and close it. Rejects like `openPdf`; the timeout covers `run` too. */
async function withPdf<T>(
  file: File,
  signal: AbortSignal,
  run: (doc: PDFDocumentProxy, stop: AbortSignal) => Promise<T>,
): Promise<T> {
  const { doc, stop, close } = await openPdf(file, signal, RENDER_TIMEOUT_MS)
  try {
    return await abortable(run(doc, stop), stop)
  } finally {
    close()
  }
}

/** Draw page `n` of `doc` into `canvas`, scaled to fit a `width` x `height` CSS box. */
async function drawPage(
  doc: PDFDocumentProxy,
  n: number,
  canvas: HTMLCanvasElement,
  box: { width: number; height: number },
  stop: AbortSignal,
) {
  const page = await doc.getPage(n)
  stop.throwIfAborted()
  const base = page.getViewport({ scale: 1 })
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const viewport = page.getViewport({
    scale: Math.min(box.width / base.width, box.height / base.height) * dpr,
  })
  canvas.width = Math.max(1, Math.floor(viewport.width))
  canvas.height = Math.max(1, Math.floor(viewport.height))
  const render = page.render({ canvas, viewport, background: 'white' })
  // Rendering runs on the main thread, so stop it as soon as the caller gives up or the timeout fires.
  const cancel = () => render.cancel()
  stop.addEventListener('abort', cancel, { once: true })
  try {
    await render.promise
  } finally {
    stop.removeEventListener('abort', cancel)
  }
}

/**
 * Draw the first page of `file` into `canvas`, scaled to fit a `width` x `height` CSS box.
 * Rejects if the PDF can't be read (e.g. encrypted or corrupt), takes too long, or `signal` aborts.
 */
export function renderPdfThumbnail(
  file: File,
  canvas: HTMLCanvasElement,
  box: { width: number; height: number },
  signal: AbortSignal,
): Promise<void> {
  return withPdf(file, signal, (doc, stop) => drawPage(doc, 1, canvas, box, stop))
}

/** Number of pages in `file`. Rejects like `renderPdfThumbnail`. */
export function countPdfPages(file: File, signal: AbortSignal): Promise<number> {
  return withPdf(file, signal, async (doc) => doc.numPages)
}

/** A PDF kept open to preview its pages. */
export interface PdfPages {
  numPages: number
  /**
   * Render page `n` (1-based) to fit a `width` x `height` CSS box, as a JPEG: an image costs far less memory
   * than a canvas per page. Pages render one at a time, in the order asked for.
   * Rejects if the page can't be rendered, takes too long, `signal` aborts, or the PDF has been closed.
   */
  renderPage: (n: number, box: { width: number; height: number }, signal: AbortSignal) => Promise<Blob>
}

/**
 * Open `file` to preview its pages. It stays open (holding a worker and a slot) until `signal` aborts.
 * Rejects like `renderPdfThumbnail`.
 */
export async function openPdfPages(file: File, signal: AbortSignal): Promise<PdfPages> {
  const { doc, close } = await openPdf(file, signal, RENDER_TIMEOUT_MS)
  if (signal.aborted) close()
  signal.addEventListener('abort', close, { once: true })
  signal.throwIfAborted()
  let closed = false
  let queue: Promise<unknown> = Promise.resolve()

  async function render(n: number, box: { width: number; height: number }, pageSignal: AbortSignal) {
    if (closed) throw new Error('The PDF preview has been closed.')
    const stop = AbortSignal.any([signal, pageSignal, AbortSignal.timeout(RENDER_TIMEOUT_MS)])
    // A canvas per page, so a cancelled render still finishing in the background can't draw over the next one.
    const canvas = document.createElement('canvas')
    try {
      return await abortable(
        (async () => {
          await drawPage(doc, n, canvas, box, stop)
          const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.85))
          if (!blob) throw new Error(`Page ${n} could not be previewed.`)
          return blob
        })(),
        stop,
      )
    } catch (err) {
      // A page that times out may have left the worker stuck, which would hold up every page after it.
      if (stop.reason instanceof DOMException && stop.reason.name === 'TimeoutError') {
        closed = true
        close()
      }
      throw err
    } finally {
      canvas.width = canvas.height = 0 // free the pixels now rather than at the next garbage collection
    }
  }

  return {
    numPages: doc.numPages,
    renderPage(n, box, pageSignal) {
      const result = queue.then(() => {
        pageSignal.throwIfAborted() // skip pages that scrolled away while waiting
        return render(n, box, pageSignal)
      })
      queue = result.catch(() => {})
      return result
    },
  }
}
