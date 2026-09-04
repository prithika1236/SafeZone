import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useState } from 'react'

const navigation = [['/', 'Overview', '⌂'], ['/crimes', 'Crime management', '◇'], ['/map', 'SafeZone map', '◎'], ['/optimization', 'PRP optimization', '△'], ['/assignments', 'Patrol assignments', '⇄']]
export default function Layout({ profile, onLogout }) {
  const [open, setOpen] = useState(false); const location = useLocation()
  const title = navigation.find(([path]) => path === location.pathname)?.[1] || 'SafeZone'
  return <div className="dashboard-shell">
    <aside className={`sidebar ${open ? 'open' : ''}`}><div className="brand"><span className="brand-mark">SZ</span><div><strong>SafeZone</strong><small>Command center</small></div></div><nav>{navigation.map(([path, label, icon]) => <NavLink key={path} to={path} end={path === '/'} onClick={() => setOpen(false)}><span className="nav-icon">{icon}</span>{label}</NavLink>)}</nav><div className="sidebar-foot"><span className="live-dot" />API connection secured</div></aside>
    {open && <button className="scrim" aria-label="Close menu" onClick={() => setOpen(false)} />}
    <div className="workspace"><header className="topbar"><button className="menu-button" onClick={() => setOpen(!open)}>☰</button><div><p>ADMIN CONSOLE</p><h1>{title}</h1></div><div className="profile-block"><span className="avatar">{profile.name?.[0]?.toUpperCase()}</span><div><strong>{profile.name}</strong><small>{profile.email}</small></div><button className="text-button" onClick={onLogout}>Sign out</button></div></header><main className="content"><Outlet /></main></div>
  </div>
}
