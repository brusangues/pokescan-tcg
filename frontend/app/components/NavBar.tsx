'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Sparkles, Camera, Zap, LayoutDashboard, BarChart3, History, Bug, Package, Menu, X } from 'lucide-react';

// Página de debug/features: só aparece no menu quando habilitada (dev).
// Em produção (sem NEXT_PUBLIC_FEATURES=1) some do menu e a rota retorna 404.
const FEATURES_ENABLED = process.env.NEXT_PUBLIC_FEATURES === '1';

const NAV_ITEMS = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/hits', label: 'Hits', icon: Zap },
  { href: '/snapshot', label: 'Snapshot', icon: BarChart3 },
  { href: '/colecoes', label: 'Coleções', icon: Package },
  { href: '/scanner', label: 'Scanner', icon: Camera },
  { href: '/changelog', label: 'Changelog', icon: History },
  ...(FEATURES_ENABLED ? [{ href: '/features', label: 'Features', icon: Bug }] : []),
];

export default function NavBar() {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  const isActive = (href: string) => pathname === href || pathname?.startsWith(href + '/');

  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 shrink-0">
          <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center text-white shadow-sm">
            <Sparkles className="w-5 h-5" />
          </div>
          <h1 className="text-lg sm:text-xl font-bold text-gray-900 tracking-tight">PokéScan TCG</h1>
        </Link>

        {/* Navegação desktop */}
        <nav className="hidden md:flex gap-2 items-center">
          {NAV_ITEMS.map(item => {
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2 text-sm font-medium px-3 py-1.5 rounded-full transition-colors ${
                  isActive(item.href)
                    ? 'text-indigo-600 bg-indigo-50'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                }`}
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Botão hambúrguer (mobile) */}
        <button
          onClick={() => setMenuOpen(!menuOpen)}
          className="md:hidden p-2 rounded-lg text-gray-600 hover:bg-gray-100"
          aria-label={menuOpen ? 'Fechar menu' : 'Abrir menu'}
        >
          {menuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {/* Menu mobile (dropdown) */}
      {menuOpen && (
        <nav className="md:hidden border-t border-gray-100 bg-white px-4 py-2">
          {NAV_ITEMS.map(item => {
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMenuOpen(false)}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive(item.href)
                    ? 'text-indigo-600 bg-indigo-50'
                    : 'text-gray-700 hover:bg-gray-50'
                }`}
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      )}
    </header>
  );
}
