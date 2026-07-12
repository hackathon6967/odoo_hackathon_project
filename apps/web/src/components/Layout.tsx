import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Leaf, Users, Shield, Trophy, BarChart3, Settings, Bell, LogOut, Home, ChevronRight, Moon, Sun } from 'lucide-react'
import { useState, useEffect } from 'react'
import api from '../api/client'

const navItems = [
    { to: '/dashboard', icon: Home, label: 'Overview' },
    { to: '/environmental', icon: Leaf, label: 'Environmental' },
    { to: '/social', icon: Users, label: 'Social' },
    { to: '/governance', icon: Shield, label: 'Governance' },
    { to: '/gamification', icon: Trophy, label: 'Honours' },
    { to: '/scoring', icon: BarChart3, label: 'Scorecard' },
    { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function Layout() {
    const { user, login, logout } = useAuth()
    const location = useLocation()
    const [unread, setUnread] = useState(0)
    const [showNotifications, setShowNotifications] = useState(false)
    const [notifications, setNotifications] = useState<any[]>([])
    const [showAccounts, setShowAccounts] = useState(false)
    const [darkMode, setDarkMode] = useState(() => localStorage.getItem('theme') === 'dark')
    const loadNotifications = () => api.get('/notifications/').then(r => setNotifications(r.data)).catch(() => {})
    const loadUnread = () => api.get('/notifications/unread-count').then(r => setUnread(r.data.count)).catch(() => {})

    useEffect(() => {
        loadUnread()
        const interval = setInterval(loadUnread, 30000)
        return () => clearInterval(interval)
    }, [])
    useEffect(() => { document.documentElement.dataset.theme = darkMode ? 'dark' : 'light'; localStorage.setItem('theme', darkMode ? 'dark' : 'light') }, [darkMode])
    useEffect(() => { if (showNotifications) loadNotifications() }, [showNotifications])

    const markRead = async (id: string) => {
        try { await api.put(`/notifications/${id}/read`); setNotifications(n => n.map(x => x.id === id ? { ...x, is_read: true } : x)); loadUnread() } catch {}
    }
    const markAllRead = async () => {
        try { await api.put('/notifications/read-all'); setNotifications(n => n.map(x => ({ ...x, is_read: true }))); loadUnread() } catch {}
    }
    const switchAccount = async (email: string) => {
        try { await login(email, 'admin123'); setShowAccounts(false) } catch {}
    }

    return (
        <div className="flex h-screen overflow-hidden bg-[var(--obsidian)]">
            <aside className="w-64 max-sm:w-16 flex-shrink-0 flex flex-col py-6 px-3 border-r border-[var(--line)] bg-[var(--charcoal)] relative">
                <div className="absolute right-0 top-0 h-full w-px bg-gradient-to-b from-transparent via-[var(--gold)] to-transparent opacity-50" />
                <div className="flex items-center gap-4 px-3 mb-10 max-sm:px-1 max-sm:justify-center">
                    <div className="deco-diamond w-9 h-9 border border-[var(--gold)] flex items-center justify-center shadow-[0_0_16px_rgba(21,153,223,.22)]"><Leaf size={17} className="text-[var(--gold-light)]" /></div>
                    <div className="max-sm:hidden">
                        <h1 className="text-[var(--champagne)] text-sm tracking-[.23em] uppercase" style={{ fontFamily: 'var(--font-display)' }}>EcoSphere</h1>
                        <p className="text-[var(--gold)] text-[9px] mt-1 tracking-[.28em] uppercase">Est. MMXXVI</p>
                    </div>
                </div>
                <div className="text-[var(--pewter)] text-[9px] tracking-[.24em] uppercase px-3 mb-3 max-sm:hidden">The Ledger</div>
                <nav className="flex-1 space-y-1">
                    {navItems.map(({ to, icon: Icon, label }) => (
                        <NavLink key={to} to={to} title={label} className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
                            <Icon size={16} className="text-[var(--gold)] shrink-0" />
                            <span className="max-sm:hidden">{label}</span>
                            {location.pathname.startsWith(to) && to !== '/dashboard' && <ChevronRight size={13} className="ml-auto max-sm:hidden" />}
                        </NavLink>
                    ))}
                    {user?.role === 'admin' && (
                        <NavLink key="/accounts" to="/accounts" title="Accounts" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
                            <Users size={16} className="text-[var(--gold)] shrink-0" />
                            <span className="max-sm:hidden">Accounts</span>
                            {location.pathname.startsWith('/accounts') && <ChevronRight size={13} className="ml-auto max-sm:hidden" />}
                        </NavLink>
                    )}
                </nav>
                <div className="mt-6 pt-5 border-t border-[var(--line)]">
                    <button onClick={() => setShowAccounts(!showAccounts)} className="w-full flex items-center gap-3 px-3 mb-4 max-sm:px-1 max-sm:justify-center text-left" title="Switch account">
                        <div className="deco-diamond w-7 h-7 border border-[var(--gold)] flex items-center justify-center text-xs font-bold text-[var(--gold-light)]"><span>{user?.full_name?.[0] || 'U'}</span></div>
                        <div className="flex-1 min-w-0 max-sm:hidden"><p className="text-[var(--champagne)] text-xs truncate">{user?.full_name}</p><p className="text-[var(--pewter)] text-[9px] uppercase tracking-widest mt-1">{user?.role}</p></div>
                    </button>
                    {showAccounts && <div className="glass mx-2 mb-3 p-2 space-y-1 max-sm:absolute max-sm:bottom-12 max-sm:left-14 max-sm:w-48 z-50">
                        <p className="px-2 py-1 text-[9px] text-[var(--pewter)] uppercase tracking-widest">Available accounts</p>
                        {[['Admin User', 'admin@ecosphere.app'], ['Manager User', 'manager@ecosphere.app'], ['Employee User', 'employee@ecosphere.app']].map(([name, email]) => <button key={email} onClick={() => switchAccount(email)} className="w-full text-left px-2 py-2 hover:bg-[var(--blue)] text-xs text-[var(--champagne)]"><span className="block">{name}</span><span className="block text-[10px] text-[var(--pewter)]">{email}</span></button>)}
                    </div>}
                    <div className="flex items-center gap-3 px-3 mb-3 max-sm:justify-center relative">
                        <button onClick={() => setDarkMode(value => !value)} className="text-[var(--gold)]" aria-label="Toggle dark mode">{darkMode ? <Sun size={16} /> : <Moon size={16} />}</button>
                        <button onClick={() => setShowNotifications(!showNotifications)} className="relative text-[var(--gold)] hover:text-[var(--gold-light)] transition-colors" aria-label="Notifications"><Bell size={16} />
                            {unread > 0 && <span className="absolute -top-2 -right-2 w-4 h-4 bg-[var(--gold)] text-black text-[9px] font-bold flex items-center justify-center">{unread > 9 ? '9+' : unread}</span>}
                        </button>
                        <span className="text-[var(--pewter)] text-[10px] tracking-wider max-sm:hidden">{user?.xp || 0} XP / {user?.points || 0} PTS</span>
                        {showNotifications && <><div className="fixed inset-0 z-40" onClick={() => setShowNotifications(false)} /><div className="glass absolute bottom-9 left-0 w-80 max-h-96 z-50 flex flex-col overflow-hidden text-left cursor-default">
                            <div className="p-4 border-b border-[var(--line)] flex justify-between items-center"><h3 className="text-[var(--gold)] text-xs tracking-[.15em] uppercase" style={{ fontFamily: 'var(--font-display)' }}>Dispatches</h3>{unread > 0 && <button onClick={markAllRead} className="text-[10px] text-[var(--gold-light)] tracking-wider uppercase">Clear all</button>}</div>
                            <div className="overflow-y-auto flex-1 p-2 space-y-1">{notifications.map(n => <button key={n.id} onClick={() => !n.is_read && markRead(n.id)} className={`w-full p-3 text-left border-l ${n.is_read ? 'border-transparent opacity-60' : 'border-[var(--gold)] bg-[var(--gold)]10'}`}><span className="block text-[var(--champagne)] text-xs">{n.title}</span><span className="block text-[var(--pewter)] text-[10px] mt-1">{n.body}</span></button>)}{notifications.length === 0 && <p className="p-5 text-center text-[var(--pewter)] text-xs">No dispatches.</p>}</div>
                        </div></>}
                    </div>
                    <button onClick={logout} className="sidebar-link w-full text-[#b76b58] hover:text-[var(--gold-light)]"><LogOut size={16} /><span className="max-sm:hidden">Depart</span></button>
                </div>
            </aside>
            <main className="flex-1 overflow-y-auto"><Outlet /></main>
        </div>
    )
}
