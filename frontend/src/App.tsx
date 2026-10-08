import { Link, NavLink, Route, Routes } from 'react-router-dom'
import Home from './pages/Home'
import NavGroup from './components/NavGroup'
import { NAV, TOOLS } from './tools'

export default function App() {
  return (
    <div className="app">
      <header className="header">
        <Link to="/" className="logo">
          <img src="/favicon.svg" alt="" className="logo-icon" />
          <span>Toolbox</span>
        </Link>
        <nav>
          {NAV.map((item) =>
            'group' in item ? (
              <NavGroup key={item.group} title={item.group} sections={item.sections} />
            ) : (
              <NavLink key={item.tool.path} to={item.tool.path}>
                {item.tool.title}
              </NavLink>
            ),
          )}
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
