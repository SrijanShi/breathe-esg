import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'
import {
  LayoutDashboard,
  Upload,
  ClipboardCheck,
  ScrollText,
  LogOut,
  Leaf,
} from 'lucide-react'

const NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard', exact: true },
  { to: '/ingestion', icon: Upload, label: 'Ingestion' },
  { to: '/review', icon: ClipboardCheck, label: 'Review Queue' },
  { to: '/audit', icon: ScrollText, label: 'Audit Trail' },
]

export function AppShell() {
  const { user, logout } = useAuth()

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Sidebar */}
      <aside className="w-60 shrink-0 flex flex-col bg-white border-r border-slate-200">
        {/* Logo */}
        <div className="h-16 flex items-center gap-2.5 px-5 border-b border-slate-200">
          <div className="w-7 h-7 rounded-lg bg-emerald-600 flex items-center justify-center">
            <Leaf className="w-4 h-4 text-white" />
          </div>
          <div>
            <p className="text-sm font-bold text-slate-900 leading-none">Breathe ESG</p>
            <p className="text-[10px] text-slate-400 mt-0.5 leading-none">Emissions Platform</p>
          </div>
        </div>

        {/* Org */}
        <div className="px-4 py-3 border-b border-slate-100">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Organization</p>
          <p className="text-sm font-medium text-slate-700 mt-0.5 truncate">
            {user?.organization?.name ?? '—'}
          </p>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-3 space-y-0.5">
          {NAV_ITEMS.map(({ to, icon: Icon, label, exact }) => (
            <NavLink
              key={to}
              to={to}
              end={exact}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-all',
                  isActive
                    ? 'bg-emerald-600 text-white shadow-sm'
                    : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'
                )
              }
            >
              <Icon className="w-4 h-4 shrink-0 opacity-80" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* User footer */}
        <div className="p-3 border-t border-slate-200">
          <div className="flex items-center gap-2.5 px-2 py-2">
            <div className="w-7 h-7 rounded-full bg-slate-200 flex items-center justify-center shrink-0">
              <span className="text-xs font-semibold text-slate-600">
                {user?.first_name?.[0] ?? user?.username?.[0]?.toUpperCase() ?? '?'}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-slate-900 truncate">
                {user?.first_name || user?.username}
              </p>
              <p className="text-[10px] text-slate-400 capitalize">{user?.role}</p>
            </div>
            <button
              onClick={logout}
              className="text-slate-400 hover:text-slate-600 transition-colors"
              title="Log out"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 min-w-0 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
