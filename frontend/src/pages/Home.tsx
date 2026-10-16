import ToolCard from '../components/ToolCard'
import { TOOLS } from '../tools'

export default function Home() {
  return (
    <>
      <section className="hero">
        <h1>Everyday file tools, all in one place.</h1>
        <p className="hero-lede">
          Merge, split, compress and convert PDFs and images. No sign-up, and your files are deleted before the
          result reaches you.
        </p>
      </section>
      <section className="tool-grid">
        {TOOLS.map((t) => (
          <ToolCard key={t.path} tool={t} />
        ))}
      </section>
    </>
  )
}
