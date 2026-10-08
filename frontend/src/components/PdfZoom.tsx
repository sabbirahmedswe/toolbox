import { useEffect, useRef, useState, type MouseEvent, type PointerEvent } from 'react'
import { CloseIcon } from './FileCard'
import PdfThumb from './PdfThumb'

/** The box the page is fitted to: up to 1000px wide within the window, and 80% of its height, leaving room above
 *  and below. Less the dialog's margin and padding (4rem across, 4rem down incl. the close button's strip). The
 *  canvas is given the same box as its max size, so it's shown at exactly the size it was rendered for. */
function zoomBox() {
  const { clientWidth, clientHeight } = document.documentElement
  return { width: Math.max(100, Math.min(clientWidth - 64, 1000)), height: Math.max(100, clientHeight * 0.8 - 64) }
}

/** The first page of `file`, enlarged in a modal dialog. */
export default function PdfZoom({ file, onClose }: { file: File; onClose: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const [box, setBox] = useState(zoomBox)

  useEffect(() => {
    // A modal <dialog> traps focus, closes on Escape and returns focus to the zoom button when it closes.
    // No close() on cleanup: its close event would arrive late and shut the dialog straight after StrictMode's
    // remount. Unmounting takes the dialog off the screen anyway.
    const dialog = dialogRef.current!
    if (!dialog.open) dialog.showModal()
  }, [])

  useEffect(() => {
    // Render again, sharp, after the window is resized or the phone rotated; once it has settled, not per pixel.
    let timer: number | undefined
    const onResize = () => {
      clearTimeout(timer)
      timer = window.setTimeout(() => setBox(zoomBox()), 200)
    }
    window.addEventListener('resize', onResize)
    return () => {
      clearTimeout(timer)
      window.removeEventListener('resize', onResize)
    }
  }, [])

  // Whether the current press started on the backdrop: a drag from inside the dialog that's released outside it
  // also clicks the dialog, and mustn't close it.
  const pressedOutside = useRef(false)

  function onPointerDown(e: PointerEvent<HTMLDialogElement>) {
    pressedOutside.current = e.target === e.currentTarget && outside(e)
  }

  function closeOnBackdrop(e: MouseEvent<HTMLDialogElement>) {
    // Clicks on the dialog's own padding also target the dialog, so check the press and release were outside its
    // box. Keyboard "clicks" (detail 0) have no position.
    if (e.target === e.currentTarget && e.detail !== 0 && pressedOutside.current && outside(e)) e.currentTarget.close()
    pressedOutside.current = false
  }

  return (
    <dialog
      ref={dialogRef}
      className="pdf-zoom"
      aria-label={`First page of ${file.name}`}
      // Every way out goes through close(), so the browser puts focus back on the zoom button.
      onClose={onClose}
      onPointerDown={onPointerDown}
      onClick={closeOnBackdrop}
    >
      <button
        type="button"
        className="icon-btn pdf-zoom-close"
        onClick={() => dialogRef.current!.close()}
        aria-label="Close"
        autoFocus
      >
        <CloseIcon />
      </button>
      <PdfThumb
        file={file}
        box={box}
        className="pdf-zoom-page"
        style={{ maxWidth: box.width, maxHeight: box.height }}
        fallback={(failed) => (
          <p className="pdf-zoom-status">{failed ? "This PDF can't be previewed." : 'Loading page…'}</p>
        )}
      />
    </dialog>
  )
}

function outside(e: MouseEvent<HTMLDialogElement>) {
  const r = e.currentTarget.getBoundingClientRect()
  return e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom
}
