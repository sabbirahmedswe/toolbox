import ToolCard from '../components/ToolCard'
import { TOOLS } from '../tools'

export default function Home() {
  return (
    <>
      <section className="hero">
        <h1>Every tool you need to work with PDFs</h1>
        <p>Merge, compress and convert PDFs. Files are processed and never stored.</p>
      </section>
      <section className="tool-grid">
        {TOOLS.map((t) => (
          <ToolCard key={t.path} tool={t} />
        ))}
      </section>
    </>
  )
}
