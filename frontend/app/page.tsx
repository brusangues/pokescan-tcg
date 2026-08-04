import Link from 'next/link';
import NavBar from '@/app/components/NavBar';
import { Camera, Zap, LayoutDashboard, BarChart3, TrendingUp, TrendingDown, Sparkles, ArrowRight, Database, LineChart } from 'lucide-react';

const FEATURES = [
  {
    href: '/dashboard',
    title: 'Dashboard',
    description: 'Visão geral unificada: métricas de hits e snapshot, histograma de upside e top oportunidades.',
    icon: LayoutDashboard,
    color: 'bg-indigo-600',
    badge: 'Visão geral',
  },
  {
    href: '/hits',
    title: 'Hits Diários',
    description: 'Cartas em alta e queda raspadas hoje da Liga Pokémon, escoradas com o modelo CatBoost.',
    icon: Zap,
    color: 'bg-amber-500',
    badge: 'Diário · 07:00',
  },
  {
    href: '/snapshot',
    title: 'Snapshot Semanal',
    description: 'Escoragem completa dos 174 sets: 7.000+ cartas com preço justo, subvalorizadas e inflacionadas.',
    icon: BarChart3,
    color: 'bg-purple-600',
    badge: 'Semanal · Seg 06:00',
  },
  {
    href: '/scanner',
    title: 'Scanner de IA',
    description: 'Identifique qualquer carta por foto. Modelo Vision roda direto no seu navegador.',
    icon: Camera,
    color: 'bg-emerald-600',
    badge: 'IA no browser',
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <NavBar />

      {/* Hero */}
      <div className="bg-indigo-900 text-white relative overflow-hidden">
        <div className="absolute inset-0 opacity-10 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-white via-transparent to-transparent" />
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 text-center relative z-10">
          <div className="inline-flex items-center gap-2 bg-white/10 text-indigo-100 text-xs font-medium px-4 py-1.5 rounded-full mb-6">
            <Sparkles className="w-3.5 h-3.5" />
            Previsão de preços com CatBoost + raspagem diária
          </div>
          <h2 className="text-4xl sm:text-5xl md:text-6xl font-bold tracking-tight">
            Identifique, escore e compre
            <br />
            <span className="text-indigo-300">na hora certa</span>
          </h2>
          <p className="text-indigo-200 text-lg sm:text-xl max-w-2xl mx-auto mt-6 leading-relaxed">
            O PokéScan TCG monitora a Liga Pokémon diariamente, compara com o mercado global
            (TCGPlayer + Cardmarket) e aponta onde o preço justo está acima ou abaixo do real.
          </p>

          {/* Stats rápidos */}
          <div className="grid grid-cols-3 max-w-lg mx-auto gap-6 mt-10 text-center">
            <div>
              <p className="text-3xl font-bold text-white">20k+</p>
              <p className="text-xs text-indigo-300 mt-1">cartas na base</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-white">174</p>
              <p className="text-xs text-indigo-300 mt-1">sets monitorados</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-white">07:00</p>
              <p className="text-xs text-indigo-300 mt-1">escoragem diária</p>
            </div>
          </div>
        </div>
      </div>

      {/* Feature Cards */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <div className="grid md:grid-cols-2 gap-6">
          {FEATURES.map(f => {
            const Icon = f.icon;
            return (
              <Link
                key={f.href}
                href={f.href}
                className="group bg-white rounded-2xl border border-gray-200 shadow-sm hover:shadow-lg hover:border-indigo-200 transition-all p-6 flex flex-col"
              >
                <div className="flex items-center justify-between mb-4">
                  <div className={`w-12 h-12 rounded-xl ${f.color} flex items-center justify-center text-white shadow-sm`}>
                    <Icon className="w-6 h-6" />
                  </div>
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-gray-400 bg-gray-50 px-2.5 py-1 rounded-full">
                    {f.badge}
                  </span>
                </div>
                <h3 className="text-lg font-bold text-gray-900 group-hover:text-indigo-700 transition-colors flex items-center gap-2">
                  {f.title}
                  <ArrowRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity text-indigo-500" />
                </h3>
                <p className="text-sm text-gray-500 mt-2 leading-relaxed flex-1">{f.description}</p>
              </Link>
            );
          })}
        </div>

        {/* Como funciona */}
        <div className="mt-14 bg-white rounded-2xl border border-gray-200 shadow-sm p-8">
          <h3 className="text-lg font-bold text-gray-900 mb-6 text-center">Como funciona</h3>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="w-10 h-10 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center font-bold text-sm mx-auto mb-3">1</div>
              <p className="font-semibold text-sm text-gray-800">Raspagem diária</p>
              <p className="text-xs text-gray-500 mt-1">Crawlers coletam preços e ofertas da Liga Pokémon em 6 combinações de período</p>
            </div>
            <div className="text-center">
              <div className="w-10 h-10 rounded-full bg-amber-100 text-amber-600 flex items-center justify-center font-bold text-sm mx-auto mb-3">2</div>
              <p className="font-semibold text-sm text-gray-800">Modelo CatBoost</p>
              <p className="text-xs text-gray-500 mt-1">Preço justo (USD + BRL) calculado a partir de raridade, pool size, pull cost e 20k cartas</p>
            </div>
            <div className="text-center">
              <div className="w-10 h-10 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center font-bold text-sm mx-auto mb-3">3</div>
              <p className="font-semibold text-sm text-gray-800">Oportunidades</p>
              <p className="text-xs text-gray-500 mt-1">🔥 Subvalorizadas (pred &gt; real +25%) vs 💀 Inflacionadas — com liquidez real (iCO)</p>
            </div>
          </div>
        </div>

        {/* CTA */}
        <div className="mt-14 text-center">
          <Link
            href="/hits"
            className="inline-flex items-center gap-2 px-8 py-4 bg-indigo-600 text-white rounded-2xl font-semibold hover:bg-indigo-700 transition-colors shadow-lg shadow-indigo-200"
          >
            <TrendingUp className="w-5 h-5" />
            Ver oportunidades de hoje
            <ArrowRight className="w-4 h-4" />
          </Link>
          <p className="text-xs text-gray-400 mt-3">
            Ou explore o <Link href="/scanner" className="text-indigo-500 hover:underline">scanner de IA</Link> para identificar cartas por foto
          </p>
        </div>
      </div>

      <footer className="border-t border-gray-200 py-8 text-center text-xs text-gray-400">
        <p>PokéScan TCG — dados da Liga Pokémon + pokemontcg.io. Não é afiliado à Pokémon Company.</p>
      </footer>
    </div>
  );
}