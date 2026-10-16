import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { TOOLS, type Tool } from '../tools'

// Lowercased once so searching doesn't redo it on every keystroke.
const SEARCHABLE = TOOLS.map((tool) => ({
  tool,
  title: tool.title.toLowerCase(),
  text: `${tool.title} ${tool.description}`.toLowerCase(),
}))

/** Tools whose title or description contains every word of the query; title matches come first. */
function searchTools(query: string): Tool[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean)
  if (words.length === 0) return TOOLS
  const titleMatches: Tool[] = []
  const otherMatches: Tool[] = []
  for (const { tool, title, text } of SEARCHABLE) {
    if (words.every((w) => title.includes(w))) titleMatches.push(tool)
    else if (words.every((w) => text.includes(w))) otherMatches.push(tool)
  }
  return [...titleMatches, ...otherMatches]
}

/** True when a key press would type into the focused element, so "/" shouldn't be taken over. */
function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  return target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)
}

function SearchIcon({ className }: { className: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="11" cy="11" r="7" />
      <path d="M20 20l-3.5-3.5" />
    </svg>
  )
}

/**
 * Header search trigger and the command palette it opens. Press "/" (or Ctrl/Cmd+K) anywhere to open it.
 * The palette is a modal <dialog>, so the browser handles focus trapping, Esc and making the page inert.
 */
export default function ToolSearch() {
  const navigate = useNavigate()
  const location = useLocation()
  const dialogRef = useRef<HTMLDialogElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  // Whether the current mouse press started on the backdrop; a drag out of the panel mustn't close it.
  const pressOnBackdrop = useRef(false)
  const listId = useId()
  const emptyId = useId()
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const results = useMemo(() => searchTools(query), [query])

  const openPalette = () => {
    const dialog = dialogRef.current
    if (!dialog || dialog.open) return
    setQuery('')
    setActive(0)
    if (listRef.current) listRef.current.scrollTop = 0
    dialog.showModal()
    inputRef.current?.focus()
  }

  const closePalette = () => dialogRef.current?.close()

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const slash = e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey && !isTyping(e.target)
      // Some browser-generated keydowns (e.g. Chrome autofill) have no key.
      const cmdK = (e.key === 'k' || e.key === 'K') && (e.ctrlKey || e.metaKey) && !e.altKey
      if (!slash && !cmdK) return
      e.preventDefault()
      openPalette()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [])

  // Keep the highlighted row visible when moving through a long list with the arrow keys.
  useEffect(() => {
    listRef.current?.children[active]?.scrollIntoView({ block: 'nearest' })
  }, [active])

  const go = (tool: Tool) => {
    closePalette()
    // Like <Link>: picking the page you're on replaces the history entry instead of adding a duplicate.
    navigate(tool.path, { replace: location.pathname === tool.path })
  }

  const onInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    // While an IME is composing text, Enter and the arrows belong to it.
    if (e.nativeEvent.isComposing) return
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      if (results.length === 0) return
      const step = e.key === 'ArrowDown' ? 1 : -1
      setActive((i) => (i + step + results.length) % results.length)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (results[active]) go(results[active])
    }
  }

  return (
    <>
      <button type="button" className="search-trigger" onClick={openPalette} aria-keyshortcuts="/ Control+K Meta+K">
        <SearchIcon className="search-trigger-icon" />
        <span className="search-trigger-label">Search tools</span>
        <kbd className="search-trigger-kbd" aria-hidden="true">/</kbd>
      </button>

      <dialog
        ref={dialogRef}
        className="palette"
        aria-label="Search tools"
        // A click on the dialog element itself (not its contents) is a click on the backdrop.
        // Both the press and the release must land there, or a text selection dragged out of the field closes it.
        onMouseDown={(e) => {
          pressOnBackdrop.current = e.target === e.currentTarget
        }}
        onClick={(e) => {
          if (pressOnBackdrop.current && e.target === e.currentTarget) closePalette()
          pressOnBackdrop.current = false
        }}
      >
        <div className="palette-panel">
          <div className="palette-field">
            <SearchIcon className="palette-field-icon" />
            <input
              ref={inputRef}
              type="text"
              className="palette-input"
              placeholder="What do you want to do?"
              role="combobox"
              aria-label="Search tools"
              aria-expanded={results.length > 0}
              aria-controls={results.length > 0 ? listId : undefined}
              aria-describedby={results.length === 0 ? emptyId : undefined}
              aria-autocomplete="list"
              aria-activedescendant={results[active] ? `${listId}-${active}` : undefined}
              autoComplete="off"
              spellCheck={false}
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                setActive(0)
              }}
              onKeyDown={onInputKeyDown}
            />
            <button type="button" className="palette-esc" onClick={closePalette}>
              Esc
            </button>
          </div>

          {results.length === 0 ? (
            <p id={emptyId} className="palette-empty" role="status">
              No tools match “{query.trim()}”. Try a shorter or different word.
            </p>
          ) : (
            <ul ref={listRef} id={listId} className="palette-list" role="listbox" aria-label="Tools">
              {results.map((t, i) => (
                <li
                  key={t.path}
                  id={`${listId}-${i}`}
                  role="option"
                  aria-selected={i === active}
                  className="palette-option"
                  onClick={() => go(t)}
                  onMouseMove={() => setActive(i)}
                >
                  <span className="palette-option-tile">
                    <img src={t.icon} alt="" />
                  </span>
                  <span className="palette-option-text">
                    <span className="palette-option-title">{t.title}</span>
                    <span className="palette-option-desc">{t.description}</span>
                  </span>
                  <kbd className="palette-option-enter" aria-hidden="true">↵</kbd>
                </li>
              ))}
            </ul>
          )}

          <div className="palette-footer" aria-hidden="true">
            <span><kbd>↑</kbd><kbd>↓</kbd> to move</span>
            <span><kbd>↵</kbd> to open</span>
            <span><kbd>esc</kbd> to close</span>
          </div>
        </div>
      </dialog>
    </>
  )
}
