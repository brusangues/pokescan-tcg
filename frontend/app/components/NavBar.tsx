'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Camera, Zap, LayoutDashboard, BarChart3, History, Bug, Package, Menu, X, Heart } from 'lucide-react';

// Página de debug/features: só aparece no menu quando habilitada (dev).
// Em produção (sem NEXT_PUBLIC_FEATURES=1) some do menu e a rota retorna 404.
const FEATURES_ENABLED = process.env.NEXT_PUBLIC_FEATURES === '1';

const NAV_ITEMS = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/hits', label: 'Hits', icon: Zap },
  { href: '/snapshot', label: 'Snapshot', icon: BarChart3 },
  { href: '/tendencias', label: 'Tendências', icon: History },
  { href: '/colecoes', label: 'Coleções', icon: Package },
  { href: '/minha-colecao', label: 'Minha coleção', icon: Heart },
  { href: '/scanner', label: 'Scanner', icon: Camera },
  { href: '/changelog', label: 'Changelog', icon: History },
  ...(FEATURES_ENABLED ? [{ href: '/features', label: 'Features', icon: Bug }] : []),
];

/** Logotipo: pokébola estilizada (CSS puro, sem imagem). */
function Pokeball({ className = '' }: { className?: string }) {
  return (
    <span
      className={`inline-block relative overflow-hidden rounded-full border-2 border-[#2b2517] bg-[#fffdf7] ${className}`}
      aria-hidden
    >
      <span className="absolute inset-x-0 top-0 h-1/2 bg-[#d40b2e]" />
      <span className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-[2px] bg-[#2b2517]" />
      <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[38%] aspect-square rounded-full bg-[#fffdf7] border-2 border-[#2b2517]" />
    </span>
  );
}

export default function NavBar() {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  const isActive = (href: string) => pathname === href || pathname?.startsWith(href + '/');

  return (
    <header className="bg-[--color-card-face] border-b-2 border-[#2b2517] sticky top-0 z-10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2.5 shrink-0">
          <Pokeball className="w-8 h-8" />
          <h1 className="font-display text-xl sm:text-2xl font-bold text-[--color-ink] tracking-tight">
            PokéScan <span className="text-[#d40b2e]">TCG</span>
          </h1>
        </Link>

        {/* Navegação desktop */}
        <nav className="hidden md:flex gap-1 items-center">
          {NAV_ITEMS.map(item => {
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-1.5 text-sm font-semibold px-3 py-1.5 rounded-xl transition-colors ${
                  isActive(item.href)
                    ? 'text-white bg-[#d40b2e] shadow-[0_2px_0_0_rgba(43,37,23,0.8)]'
                    : 'text-[--color-ink-soft] hover:text-[--color-ink] hover:bg-[--color-paper-deep]'
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
          className="md:hidden p-2 rounded-lg text-[--color-ink-soft] hover:bg-[--color-paper-deep]"
          aria-label={menuOpen ? 'Fechar menu' : 'Abrir menu'}
        >
          {menuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {/* Menu mobile (dropdown) */}
      {menuOpen && (
        <nav className="md:hidden border-t-2 border-[#2b2517]/20 bg-[--color-card-face] px-4 py-2">
          {NAV_ITEMS.map(item => {
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMenuOpen(false)}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-colors ${
                  isActive(item.href)
                    ? 'text-[#d40b2e] bg-[--color-paper-deep]'
                    : 'text-[--color-ink] hover:bg-[--color-paper-deep]'
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
