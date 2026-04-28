import { Link, NavLink } from 'react-router-dom';
import type { PropsWithChildren } from 'react';

const navItemClass = ({ isActive }: { isActive: boolean }): string =>
  isActive
    ? 'rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white'
    : 'rounded-md px-3 py-2 text-sm font-medium text-slate-300 hover:bg-slate-800 hover:text-white';

export default function Layout({ children }: PropsWithChildren) {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/90">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
          <Link to="/deployments" className="text-lg font-semibold text-indigo-300">
            Agentcys Deployments
          </Link>
          <nav className="flex items-center gap-2">
            <NavLink to="/setup" className={navItemClass}>
              Setup
            </NavLink>
            <NavLink to="/deployments" className={navItemClass}>
              Deployments
            </NavLink>
            <NavLink to="/deployments/new" className={navItemClass}>
              New Deployment
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
    </div>
  );
}
