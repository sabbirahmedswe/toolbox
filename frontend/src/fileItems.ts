import { formatBytes } from './api/client'

// Keep in sync with backend/app/config.py defaults.
export const MAX_FILES = 20
export const MAX_FILE_SIZE = 50 * 1024 * 1024
export const MAX_TOTAL_SIZE = 200 * 1024 * 1024
// Split: most PDFs one split may create, and the longest page-ranges text.
export const MAX_SPLIT_PARTS = 500
export const MAX_RANGES_LENGTH = 1000
// The backend limits the whole request body, which adds multipart boundaries and part headers to the files.
const MULTIPART_HEADROOM = 1024 * 1024

export interface FileItem {
  id: string
  file: File
}

export function toFileItems(files: File[]): FileItem[] {
  return files.map((file) => ({ id: crypto.randomUUID(), file }))
}

/**
 * Append `incoming` to `existing`, dropping files that would break the
 * backend's limits. Returns the new list and a message describing anything dropped.
 */
export function addWithinLimits(existing: FileItem[], incoming: File[]): { items: FileItem[]; error: string | null } {
  const problems: string[] = []
  const added: File[] = []
  let total = existing.reduce((sum, i) => sum + i.file.size, 0)

  for (const file of incoming) {
    if (existing.length + added.length >= MAX_FILES) {
      problems.push(`You can add at most ${MAX_FILES} files.`)
      break
    }
    if (file.size > MAX_FILE_SIZE) {
      problems.push(`"${file.name}" is larger than ${formatBytes(MAX_FILE_SIZE)}.`)
      continue
    }
    if (total + file.size > MAX_TOTAL_SIZE - MULTIPART_HEADROOM) {
      problems.push(`"${file.name}" would exceed the ${formatBytes(MAX_TOTAL_SIZE)} total limit.`)
      continue
    }
    total += file.size
    added.push(file)
  }

  return { items: [...existing, ...toFileItems(added)], error: problems.length ? problems.join(' ') : null }
}
