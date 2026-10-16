import { Link, Route, Routes } from 'react-router-dom'
import Home from './pages/Home'
import Logo from './components/Logo'
import ThemeToggle from './components/ThemeToggle'
import { TOOLS } from './tools'

export default function App() {
  return (
    <div className="app">
      <header className="header">
        <Link to="/" className="logo">
          <Logo />
          <span>Toolbox</span>
        </Link>
        <ThemeToggle />
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
