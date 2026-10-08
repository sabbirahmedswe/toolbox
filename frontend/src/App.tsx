import { Link, NavLink, Route, Routes } from 'react-router-dom'
import Home from './pages/Home'
import { TOOLS } from './tools'

export default function App() {
  return (
    <div className="app">
      <header className="header">
        <Link to="/" className="logo">
          <img src="/favicon.svg" alt="" className="logo-icon" />
          <span>Toolbox</span>
        </Link>
        <nav>
          {TOOLS.map((t) => (
            <NavLink key={t.path} to={t.path}>
              {t.title}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="main">
        <Routes>
          <Route path="/" element={<Home />} />
          {TOOLS.map((t) => (
            <Route key={t.path} path={t.path} element={t.page} />
          ))}
        </Routes>
      </main>
    </div>
  )
}
