import ToolCard from '../components/ToolCard'
import { TOOLS } from '../tools'

export default function Home() {
  return (
    <>
      <section className="hero">
        <div className="hero-art" aria-hidden="true">
          {TOOLS.map((t) => (
            <img key={t.path} src={t.icon} alt="" />
          ))}
        </div>
        <p className="hero-eyebrow">
          <span className="hero-dot" />
          No sign-up · Nothing stored
        </p>
        <h1>
          Everyday file tools, <em>all in one place.</em>
        </h1>
        <p className="hero-lede">
          Merge, compress and convert your documents and images in seconds. Each file is processed in a temporary
          folder and deleted as soon as you get the result.
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
