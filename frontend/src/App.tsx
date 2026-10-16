import { Link, Route, Routes, useLocation } from 'react-router-dom'
import Home from './pages/Home'
import Logo from './components/Logo'
import ThemeToggle from './components/ThemeToggle'
import ToolSearch from './components/ToolSearch'
import { TOOLS } from './tools'

export default function App() {
  const { pathname } = useLocation()
  return (
    <div className="app">
      <header className={pathname === '/' ? 'header' : 'header header-wide'}>
        <Link to="/" className="logo">
          <Logo />
          <span>toolbox</span>
        </Link>
        <div className="header-actions">
          <ToolSearch />
          <ThemeToggle />
        </div>
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
