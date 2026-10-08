import { useEffect, useId, useRef, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import type { NavSectionItems } from '../tools'

/** A header nav item that opens a menu of tools in columns: on hover, or on click/tap and keyboard. */
export default function NavGroup({ title, sections }: { title: string; sections: NavSectionItems[] }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const menuId = useId()
  const { pathname } = useLocation()
  const active = sections.some((s) => s.tools.some((t) => t.path === pathname))

  useEffect(() => {
    if (!open) return
    // Close on a click outside the group or Escape (which returns focus to the button).
    const onPointerDown = (e: PointerEvent) => {
      if (!ref.current!.contains(e.target as Node)) setOpen(false)
    }
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      setOpen(false)
      ref.current!.querySelector('button')!.focus()
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  return (
    <div
      ref={ref}
      className={`nav-group${open ? ' nav-group-open' : ''}`}
      // Tabbing out of the menu closes it.
      onBlur={(e) => !e.currentTarget.contains(e.relatedTarget) && setOpen(false)}
    >
      <button
        type="button"
        className={`nav-group-button${active ? ' active' : ''}`}
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((o) => !o)}
      >
        {title}
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      <div id={menuId} className="nav-menu">
        <div className="nav-menu-panel">
          {sections.map((s, i) => (
            <section key={s.title} className="nav-menu-section" aria-labelledby={`${menuId}-${i}`}>
              <h2 id={`${menuId}-${i}`}>{s.title}</h2>
              {s.tools.length > 0 ? (
                s.tools.map((t) => (
                  <NavLink key={t.path} to={t.path} onClick={() => setOpen(false)}>
                    <img src={t.icon} alt="" />
                    {t.title}
                  </NavLink>
                ))
              ) : (
                <p className="nav-menu-empty">Coming soon</p>
              )}
            </section>
          ))}
        </div>
      </div>
    </div>
  )
}
