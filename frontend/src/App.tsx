import { Link, NavLink, Navigate, Route, Routes } from 'react-router-dom'
import AdminPage from './pages/AdminPage'
import CareFinderPage from './pages/CareFinderPage'

function NotFound() {
  return (
    <div className="text-center py-5">
      <h1 className="h3">Page not found</h1>
      <Link to="/care-finder">Go to Care Finder</Link>
    </div>
  )
}

const linkClass = ({ isActive }: { isActive: boolean }) =>
  'nav-link px-3' + (isActive ? ' active fw-semibold' : '')

export default function App() {
  return (
    <>
      <nav className="navbar navbar-expand bg-white border-bottom">
        <div className="container flex-wrap">
          <Link className="navbar-brand fw-bold text-success" to="/">HealthGrid AI</Link>
          <ul className="navbar-nav me-auto">
            <li className="nav-item"><NavLink className={linkClass} to="/care-finder">Care Finder</NavLink></li>
            <li className="nav-item"><NavLink className={linkClass} to="/admin">Admin</NavLink></li>
          </ul>
          <span className="badge text-bg-warning">Demo data</span>
        </div>
      </nav>
      <main className="container py-3">
        <Routes>
          <Route path="/" element={<Navigate to="/care-finder" replace />} />
          <Route path="/care-finder" element={<CareFinderPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </>
  )
}