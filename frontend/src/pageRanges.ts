/** A 1-based, inclusive page range. */
export type PageRange = [first: number, last: number]

const RANGE = /^([0-9]+)(?:\s*-\s*([0-9]+))?$/

/**
 * Parse `1-3, 5, 8-10` the way the backend does, so mistakes show before uploading.
 * `pageCount` is null when the page count isn't known; the backend then checks the bounds.
 */
export function parseRanges(text: string, pageCount: number | null): { ranges: PageRange[] } | { error: string } {
  const ranges: PageRange[] = []
  for (const item of text.split(',').map((s) => s.trim())) {
    if (!item) continue
    const match = RANGE.exec(item)
    const first = match ? Number(match[1]) : 0
    const last = match?.[2] ? Number(match[2]) : first
    if (first < 1 || first > last) {
      return { error: `"${item}" is not a valid page range. Use page numbers like 1-3, 5, 8-10.` }
    }
    if (pageCount !== null && last > pageCount) {
      return { error: `"${item}" is outside the document, which has ${plural(pageCount, 'page')}.` }
    }
    ranges.push([first, last])
  }
  if (!ranges.length) return { error: 'Enter at least one page range, like 1-3.' }
  const ordered = [...ranges].sort((a, b) => a[0] - b[0] || a[1] - b[1])
  for (let i = 1; i < ordered.length; i++) {
    if (ordered[i][0] <= ordered[i - 1][1]) {
      return { error: `Page ${ordered[i][0]} is in more than one range. Ranges must not overlap.` }
    }
  }
  return { ranges }
}

export function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}
