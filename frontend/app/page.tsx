import Link from 'next/link';
import NavBar from '@/app/components/NavBar';
import { Camera, Zap, LayoutDashboard, BarChart3, TrendingUp, ArrowRight, Search } from 'lucide-react';

const FEATURES = [
  {
    href: '/dashboard',
    title: 'Dashboard',
    description: 'Visão geral unificada: métricas de hits e snapshot, histograma de upside e top oportunidades.',
    icon: LayoutDashboard,
    accent: '#2a75bb', // água
    badge: 'Visão geral',
  },
  {
    href: '/hits',
    title: 'Hits Diários',
    description: 'Cartas em alta e queda no mercado brasileiro hoje, escoradas com o modelo CatBoost.',
    icon: Zap,
    accent: '#dd9f00', // elétrico
    badge: 'Diário · 07:00',
  },
  {
    href: '/snapshot',
    title: 'Snapshot Semanal',
    description: 'Escoragem completa dos 170+ sets: 15.000+ cartas com preço justo, subvalorizadas e inflacionadas.',
    icon: BarChart3,
    accent: '#b23c2b', // luta (remove o roxo psíquico; evita remeter ao indigo antigo)
    badge: 'Semanal · Seg 06:00',
  },
  {
    href: '/scanner',
    title: 'Scanner de IA',
    description: 'Escaneie a carta pela câmera ou busque pelo nome. Identificação roda direto no seu navegador.',
    icon: Camera,
    accent: '#3fa129', // grama
    badge: 'IA no browser',
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[--color-paper]">
      <NavBar />

      {/* Hero — assimétrico, tipografia display, sem gradiente */}
      <div className="border-b-2 border-[#2b2517] bg-[--color-paper-deep]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 md:py-20">
          <div className="grid md:grid-cols-[1.4fr_1fr] gap-10 items-center">
            <div>
              <span className="badge-poke mb-5">Preço justo de Pokémon TCG em R$</span>
              <h2 className="font-display text-4xl sm:text-5xl md:text-6xl font-bold leading-[1.05] text-[--color-ink]">
                Saiba quanto a sua carta{' '}
                <span className="relative inline-block">
                  <span className="relative z-10">vale no Brasil</span>
                  <span className="absolute inset-x-0 bottom-1 h-3 bg-[#f2c11e]/70 -rotate-1" aria-hidden />
                </span>
                {' '}— antes de pagar.
              </h2>
              <p className="text-[--color-ink-soft] text-lg max-w-xl mt-6 leading-relaxed">
                Monitoramos o mercado brasileiro todos os dias, comparamos com o mercado
                global (TCGPlayer + Cardmarket) e apontamos onde o preço está torto.
                Escaneie a carta ou busque pelo nome.
              </p>
              <div className="flex flex-wrap items-center gap-4 mt-8">
                <Link href="/scanner" className="btn-poke">
                  <Search className="w-5 h-5" />
                  Buscar uma carta
                </Link>
                <Link
                  href="/hits"
                  className="inline-flex items-center gap-2 font-display font-bold text-[#d40b2e] hover:text-[#a90924] transition-colors"
                >
                  <TrendingUp className="w-5 h-5" />
                  Oportunidades de hoje
                </Link>
              </div>
            </div>

            {/* Stats em card-moldura, não em colunas centradas */}
            <div className="card-frame p-6 grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="font-display text-2xl sm:text-3xl font-bold tnum">20k+</p>
                <p className="text-xs text-[--color-ink-faint] mt-1">cartas na base</p>
              </div>
              <div>
                <p className="font-display text-2xl sm:text-3xl font-bold tnum">170+</p>
                <p className="text-xs text-[--color-ink-faint] mt-1">sets na base</p>
              </div>
              <div>
                <p className="font-display text-2xl sm:text-3xl font-bold tnum">07:00</p>
                <p className="text-xs text-[--color-ink-faint] mt-1">escoragem diária</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Feature Cards — moldura estilo carta TCG, acento por tipo */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <h3 className="font-display text-2xl font-bold mb-6 flex items-center gap-3">
          Explore
          <span className="h-[3px] flex-1 bg-[#2b2517]/15 rounded-full" aria-hidden />
        </h3>
        <div className="grid md:grid-cols-2 gap-6">
          {FEATURES.map(f => {
            const Icon = f.icon;
            return (
              <Link
                key={f.href}
                href={f.href}
                className="card-frame card-frame-hover group p-6 flex flex-col"
                style={{ borderTopColor: f.accent }}
              >
                <div className="flex items-center justify-between mb-4">
                  <div
                    className="w-11 h-11 rounded-xl border-2 border-[#2b2517] flex items-center justify-center text-white"
                    style={{ backgroundColor: f.accent }}
                  >
                    <Icon className="w-6 h-6" />
                  </div>
                  <span className="badge-poke">{f.badge}</span>
                </div>
                <h4 className="font-display text-lg font-bold group-hover:text-[#d40b2e] transition-colors flex items-center gap-2">
                  {f.title}
                  <ArrowRight className="w-4 h-4 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all" />
                </h4>
                <p className="text-sm text-[--color-ink-soft] mt-2 leading-relaxed flex-1">{f.description}</p>
              </Link>
            );
          })}
        </div>

        {/* Como funciona — numeração estilo barra de energia */}
        <div className="card-frame mt-14 p-8">
          <h3 className="font-display text-xl font-bold mb-6 flex items-center gap-3">
            Como funciona
            <span className="h-[3px] flex-1 bg-[#2b2517]/15 rounded-full" aria-hidden />
          </h3>
          <div className="grid md:grid-cols-3 gap-8">
            {[
              ['Raspagem diária', 'Crawlers coletam preços e ofertas do mercado brasileiro em 6 combinações de período', '#2a75bb'],
              ['Modelo CatBoost', 'Preço justo (USD + BRL) calculado a partir de raridade, pool size, pull cost e 20k cartas', '#dd9f00'],
              ['Oportunidades', 'Subvalorizadas vs inflacionadas — com liquidez real (vendedores na Liga)', '#ee5f18'],
            ].map(([titulo, desc, cor], i) => (
              <div key={titulo} className="flex gap-4">
                <div
                  className="shrink-0 w-10 h-10 rounded-full border-2 border-[#2b2517] flex items-center justify-center font-display font-bold"
                  style={{ backgroundColor: cor as string, color: '#fff' }}
                >
                  {i + 1}
                </div>
                <div>
                  <p className="font-display font-bold text-sm">{titulo}</p>
                  <p className="text-xs text-[--color-ink-soft] mt-1 leading-relaxed">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* CTA final */}
        <div className="mt-14 text-center">
          <Link href="/hits" className="btn-poke">
            <TrendingUp className="w-5 h-5" />
            Ver oportunidades de hoje
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>

      <footer className="border-t-2 border-[#2b2517] py-8 text-center text-xs text-[--color-ink-faint]">
        <p>PokéScan TCG — preços do mercado brasileiro e global. Não é afiliado à Pokémon Company.</p>
      </footer>
    </div>
  );
}
