import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Package,
  BarChart3,
  Settings,
  ExternalLink,
} from 'lucide-react';
import { StoreInfo } from '../hooks/useBigCommerceFetch';

interface LayoutProps {
  children: React.ReactNode;
  store: StoreInfo | null;
}

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/products', label: 'Products', icon: Package },
  { path: '/analytics', label: 'Analytics', icon: BarChart3 },
  { path: '/settings', label: 'Settings', icon: Settings },
];

export function Layout({ children, store }: LayoutProps) {
  const location = useLocation();
  const storeHash = new URLSearchParams(window.location.search).get('store_hash');

  return (
    <div className="min-h-screen bg-slate-950">
      {/* Sidebar */}
      <aside className="fixed top-0 left-0 w-64 h-screen bg-slate-900/50 border-r border-slate-800">
        {/* Logo */}
        <div className="p-6 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center">
              <span className="text-white font-bold text-lg">A</span>
            </div>
            <div>
              <h1 className="text-white font-semibold">Affilync</h1>
              <p className="text-slate-500 text-xs">BigCommerce App</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="p-4 space-y-1">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            const href = `${item.path}${storeHash ? `?store_hash=${storeHash}` : ''}`;

            return (
              <Link
                key={item.path}
                to={href}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                  isActive
                    ? 'bg-blue-600/20 text-blue-400'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                }`}
              >
                <item.icon className="w-5 h-5" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Store Info */}
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-slate-800">
          <div className="flex items-center justify-between">
            <div className="truncate">
              <p className="text-white text-sm font-medium truncate">
                {store?.store_name || 'Store'}
              </p>
              <p className="text-slate-500 text-xs truncate">
                {store?.store_domain || store?.store_hash}
              </p>
            </div>
            <a
              href="https://app.affilync.com"
              target="_blank"
              rel="noopener noreferrer"
              className="p-2 text-slate-500 hover:text-white transition-colors"
              title="Open Affilync Dashboard"
            >
              <ExternalLink className="w-4 h-4" />
            </a>
          </div>
          <div className="mt-2">
            <span
              className={`inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full ${
                store?.is_connected
                  ? 'bg-green-500/20 text-green-400'
                  : 'bg-amber-500/20 text-amber-400'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  store?.is_connected ? 'bg-green-400' : 'bg-amber-400'
                }`}
              />
              {store?.is_connected ? 'Connected' : 'Not Connected'}
            </span>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="ml-64 min-h-screen">{children}</main>
    </div>
  );
}
