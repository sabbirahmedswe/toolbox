import { useRef, type MouseEvent, type PointerEvent } from 'react'

/**
 * Handlers for a modal <dialog> that call `close` when its backdrop is clicked. Both the press and the release must
 * land outside the dialog's box: a drag from inside it (say, a text selection) that's released outside also clicks
 * the dialog, and mustn't close it.
 */
export function useBackdropClose(close: () => void) {
  const pressedOutside = useRef(false)
  return {
    onPointerDown(e: PointerEvent<HTMLDialogElement>) {
      pressedOutside.current = e.target === e.currentTarget && outside(e)
    },
    onClick(e: MouseEvent<HTMLDialogElement>) {
      // Clicks on the dialog's own padding also target the dialog, hence the box check. Keyboard "clicks"
      // (detail 0) have no position.
      if (e.target === e.currentTarget && e.detail !== 0 && pressedOutside.current && outside(e)) close()
      pressedOutside.current = false
    },
  }
}

function outside(e: MouseEvent<HTMLDialogElement>) {
  const r = e.currentTarget.getBoundingClientRect()
  return e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom
}
