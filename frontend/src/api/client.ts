export interface FileResult {
  blob: Blob
  filename: string
  headers: Headers
}

export class ApiError extends Error {}

/** POST multipart form data and return the response file. */
export async function postForFile(url: string, form: FormData, fallbackName: string): Promise<FileResult> {
  let res: Response
  try {
    res = await fetch(url, { method: 'POST', body: form })
  } catch {
    throw new ApiError('Could not reach the server. Is the backend running?')
  }

  if (!res.ok) {
    let message = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join(', ')
    } catch {
      // non-JSON error body; keep default message
    }
    throw new ApiError(message)
  }

  const disposition = res.headers.get('Content-Disposition') ?? ''
  const match = /filename="?([^";]+)"?/.exec(disposition)
  return { blob: await res.blob(), filename: match?.[1] ?? fallbackName, headers: res.headers }
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}
