import type { PDFDocumentLoadingTask, RenderTask } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

type PdfJs = typeof import('pdfjs-dist')

// pdf.js is ~1 MB, so it's only loaded once the first PDF thumbnail is needed.
let lib: Promise<PdfJs> | undefined

function loadPdfJs() {
  lib ??= import('pdfjs-dist').catch((err: unknown) => {
    lib = undefined // allow a retry, e.g. after a failed chunk download
    throw err
  })
  return lib
}

// Render a few files at a time so dropping 20 large PDFs doesn't load them all into memory at once.
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

/**
 * Draw the first page of `file` into `canvas`, scaled to fit a `width` x `height` CSS box.
 * Rejects if the PDF can't be read (e.g. encrypted or corrupt), takes too long, or `signal` aborts.
 */
export async function renderPdfThumbnail(
  file: File,
  canvas: HTMLCanvasElement,
  box: { width: number; height: number },
  signal: AbortSignal,
): Promise<void> {
  await acquireSlot(signal)
  try {
    const pdfjs = await abortable(loadPdfJs(), signal)
    const stop = AbortSignal.any([signal, AbortSignal.timeout(RENDER_TIMEOUT_MS)])
    // Each document gets its own worker, created here rather than by pdf.js: terminating it is the only way to
    // stop a worker stuck on a bad file, and pdf.js would otherwise fall back to parsing on the main thread
    // (for good) if a worker ever failed to start.
    const webWorker = new Worker(workerUrl, { type: 'module' })
    const worker = pdfjs.PDFWorker.create({ port: webWorker })
    let task: PDFDocumentLoadingTask | undefined
    let render: RenderTask | undefined
    try {
      await abortable(
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
          const doc = await task.promise
          const page = await doc.getPage(1)
          stop.throwIfAborted()
          const base = page.getViewport({ scale: 1 })
          const dpr = Math.min(window.devicePixelRatio || 1, 2)
          const viewport = page.getViewport({
            scale: Math.min(box.width / base.width, box.height / base.height) * dpr,
          })
          canvas.width = Math.max(1, Math.floor(viewport.width))
          canvas.height = Math.max(1, Math.floor(viewport.height))
          render = page.render({ canvas, viewport })
          await render.promise
        })(),
        stop,
      )
    } finally {
      render?.cancel()
      // Not awaited: a stuck worker never answers, and terminating it below frees everything anyway.
      task?.destroy().catch(() => {})
      worker.destroy()
      webWorker.terminate()
    }
  } finally {
    releaseSlot()
  }
}
