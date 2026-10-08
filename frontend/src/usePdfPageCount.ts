import { useEffect, useState } from 'react'
import { countPdfPages } from './pdfThumbnail'

/** Page count of a file, or null when pdf.js couldn't read it (the backend still can, or reports why not). */
interface PageCount {
  file: File
  count: number | null
}

/** `file`'s page count: undefined while counting, null if pdf.js can't read it. */
export function usePdfPageCount(file: File | null): number | null | undefined {
  const [pages, setPages] = useState<PageCount | null>(null)

  useEffect(() => {
    if (!file) return
    const controller = new AbortController()
    countPdfPages(file, controller.signal).then(
      (count) => setPages({ file, count }),
      () => {
        if (!controller.signal.aborted) setPages({ file, count: null })
      },
    )
    return () => controller.abort()
  }, [file])

  // Ignores a count left over from a previously selected file.
  return pages?.file === file ? pages.count : undefined
}
