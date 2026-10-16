import { Link } from 'react-router-dom'
import type { Tool } from '../tools'

export default function ToolCard({ tool }: { tool: Tool }) {
  return (
    <Link to={tool.path} className="tool-card">
      <span className="tool-icon-tile">
        <img className="tool-icon" src={tool.icon} alt="" />
      </span>
      <h3>{tool.title}</h3>
    </Link>
  )
}
