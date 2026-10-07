import { Link } from 'react-router-dom'
import type { Tool } from '../tools'

export default function ToolCard({ tool }: { tool: Tool }) {
  return (
    <Link to={tool.path} className="tool-card">
      <div className="tool-icon">{tool.icon}</div>
      <h3>{tool.title}</h3>
      <p>{tool.description}</p>
    </Link>
  )
}
