import type { Tool } from '../tools'

export default function ComingSoon({ tool }: { tool: Tool }) {
  return (
    <section className="tool-page">
      <h1>{tool.title}</h1>
      <p className="subtitle">{tool.description}</p>
      <p className="muted">Coming soon.</p>
    </section>
  )
}
