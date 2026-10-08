import type { ReactNode } from 'react'

interface Props {
  title: string
  /** The settings, notes and errors; scrolls if it runs long. */
  children?: ReactNode
  /** The main button, pinned to the bottom. */
  action: ReactNode
}

/** The full-height settings panel on the right of a tool's workspace. */
export default function ToolSidebar({ title, children, action }: Props) {
  return (
    <aside className="workspace-sidebar">
      <div className="workspace-sidebar-body">
        <h1>{title}</h1>
        {children}
      </div>
      <div className="workspace-sidebar-footer">{action}</div>
    </aside>
  )
}
