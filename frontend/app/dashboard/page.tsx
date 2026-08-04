'use client';

import { useState, useEffect } from 'react';
import {
  TrendingUp, TrendingDown, RefreshCw, AlertCircle,
  Zap, Loader, LayoutDashboard, BarChart3, PieChart,
  ArrowUpCircle, ArrowDownCircle, Target, Layers, DollarSign
} from 'lucide-react';
import NavBar from '@/app/components/NavBar';

interface ScoredCard {
  nome: string;
  sigla: string;
  real: number;
  pred: number;
  upside: number;
  oportunidade: string;
  iCO: number;
  moeda: string;
}

export default function DashboardPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/dashboard');
      if (!res.ok) throw new Error((await res.json()).error || 'Erro');
      setData(await res.json());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 text-gray-500">
          <Loader className="w-10 h-10 animate-spin text-indigo-600" />
          <p className="text-sm">Carregando dados de hits e snapshot...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="bg-white p-8 rounded-2xl shadow-lg max-w-md text-center space-y-4">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto">
            <AlertCircle className="w-8 h-8 text-red-500" />
          </div>
          <h2 className="text-lg font-bold text-gray-900">Erro ao carregar</h2>
          <p className="text-sm text-gray-500">{error}</p>
          <button onClick={fetchData} className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm">
            <RefreshCw className="w-4 h-4" /> Tentar novamente
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const { hits, snapshot, distribuicao, sets } = data;
  const maxDist = Math.max(...distribuicao.map((d: any) => d.count), 1);

  // Mini card de métrica
  const MetricCard = ({ label, value, sub, color, icon: Icon }: {
    label: string; value: string | number; sub?: string; color: string; icon: any;
  }) => (
    <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">{label}</p>
        <Icon className={`w-5 h-5 ${color}`} />
      </div>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );

  // Row de carta (usada nas top lists)
  const CardRow = ({ card }: { card: ScoredCard }) => (
    <div className="flex items-center gap-2 py-2 text-xs border-b border-gray-50 last:border-0">
      <span className="flex-1 font-medium text-gray-800 truncate">{card.nome}</span>
      <span className="w-12 text-right font-mono text-gray-400">{card.sigla}</span>
      <span className="w-14 text-right text-gray-600">{card.moeda}{card.real.toFixed(0)}</span>
      <span className={`w-12 text-right font-semibold ${card.upside > 0 ? 'text-green-600' : 'text-red-600'}`}>
        {card.upside > 0 ? '+' : ''}{card.upside.toFixed(0)}%
      </span>
      <span className="w-8 text-right text-blue-500">{card.iCO > 0 ? card.iCO : '—'}</span>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50 pb-12">
      {/* Header */}
      <NavBar />
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
              <LayoutDashboard className="w-5 h-5 text-indigo-600" />
              Dashboard — PokéScan TCG
            </h1>
            <p className="text-xs text-gray-400 mt-0.5">
              Visão geral de hits e snapshot da Liga Pokémon
            </p>
          </div>
          <button onClick={fetchData} className="p-2 hover:bg-gray-100 rounded-lg" title="Atualizar">
            <RefreshCw className="w-4 h-4 text-gray-500" />
          </button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-8">

        {/* ── Seção 1: Métricas Chave ── */}
        <section>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-2">
            <Target className="w-4 h-4 text-gray-400" />
            Métricas
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
            <MetricCard
              label="Hits escorados"
              value={hits.total}
              sub={hits.meta ? `Último: ${new Date(hits.meta.data).toLocaleDateString('pt-BR')}` : ''}
              color="text-indigo-600"
              icon={Zap}
            />
            <MetricCard
              label="Snapshot"
              value={snapshot.total}
              sub={snapshot.meta ? new Date(snapshot.meta.data).toLocaleDateString('pt-BR') : ''}
              color="text-purple-600"
              icon={BarChart3}
            />
            <MetricCard
              label="🔥 Subvalorizadas (Hits)"
              value={hits.subvalorizadas}
              sub="Pred > Real +25%"
              color="text-green-600"
              icon={ArrowUpCircle}
            />
            <MetricCard
              label="💀 Inflacionadas (Hits)"
              value={hits.inflacionadas}
              sub="Real > Pred +25%"
              color="text-red-600"
              icon={ArrowDownCircle}
            />
            <MetricCard
              label="⚖ Preço Justo"
              value={(hits.justo || 0) + (snapshot.justo || 0)}
              sub="Hits + Snapshot"
              color="text-blue-500"
              icon={Target}
            />
          </div>
        </section>

        {/* ── Seção 2: Distribuição de Upside ── */}
        <section>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-2">
            <PieChart className="w-4 h-4 text-gray-500" />
            Distribuição de Upside (todas as cartas)
          </h2>
          <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm">
            <div className="space-y-2">
              {distribuicao.map((d: any) => {
                const pct = Math.round((d.count / maxDist) * 100);
                const isNegative = d.range.startsWith('-');
                const isPositive = d.range.startsWith('+') || (!isNegative && parseInt(d.range) >= 0);
                return (
                  <div key={d.range} className="flex items-center gap-3">
                    <span className="text-xs font-mono text-gray-500 w-20 text-right shrink-0">
                      {d.range}
                    </span>
                    <div className="flex-1 h-6 bg-gray-100 rounded-md overflow-hidden">
                      <div
                        className={`h-full rounded-md transition-all duration-500 ${
                          isPositive ? 'bg-green-500' : 'bg-red-500'
                        }`}
                        style={{ width: `${Math.max(pct, 2)}%` }}
                      />
                    </div>
                    <span className="text-xs font-medium text-gray-600 w-8 shrink-0">{d.count}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* ── Seção 3: Top Oportunidades (Hits) ── */}
        <div className="grid md:grid-cols-2 gap-6">
          <section>
            <h2 className="text-sm font-semibold text-green-700 uppercase tracking-wide mb-3 flex items-center gap-2">
              <ArrowUpCircle className="w-4 h-4" />
              🔥 Top 10 — Comprar (Hits)
            </h2>
            <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-4">
              <div className="flex items-center text-[10px] uppercase font-semibold text-gray-400 gap-2 pb-2 border-b border-gray-100 mb-1">
                <span className="flex-1">Nome</span>
                <span className="w-12 text-right">Set</span>
                <span className="w-14 text-right">Real</span>
                <span className="w-12 text-right">Upside</span>
                <span className="w-8 text-right">iCO</span>
              </div>
              {hits.topOportunidades.map((c: ScoredCard, i: number) => (
                <CardRow key={`top-${i}`} card={c} />
              ))}
              {hits.topOportunidades.length === 0 && (
                <p className="text-center text-gray-400 text-sm py-6">Nenhuma oportunidade encontrada.</p>
              )}
            </div>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-red-700 uppercase tracking-wide mb-3 flex items-center gap-2">
              <ArrowDownCircle className="w-4 h-4" />
              💀 Top Inflacionadas — Evitar (Hits)
            </h2>
            <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-4">
              <div className="flex items-center text-[10px] uppercase font-semibold text-gray-400 gap-2 pb-2 border-b border-gray-100 mb-1">
                <span className="flex-1">Nome</span>
                <span className="w-12 text-right">Set</span>
                <span className="w-14 text-right">Real</span>
                <span className="w-12 text-right">Upside</span>
                <span className="w-8 text-right">iCO</span>
              </div>
              {hits.topInflacionadas.map((c: ScoredCard, i: number) => (
                <CardRow key={`i-${i}`} card={c} />
              ))}
              {hits.topInflacionadas.length === 0 && (
                <p className="text-center text-gray-400 text-sm py-6">Nenhuma inflacionada extrema.</p>
              )}
            </div>
          </section>
        </div>

        {/* ── Seção 4: Top Sets ── */}
        {sets.length > 0 && (
          <section>
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-2">
              <DollarSign className="w-4 h-4 text-gray-500" />
              Sets com mais movimentação (Hits)
            </h2>
            <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-4">
              <div className="flex flex-wrap gap-3">
                {sets.map((s: any, i: number) => (
                  <div key={s.sigla} className="inline-flex items-center gap-2 px-3 py-2 bg-gray-50 rounded-lg">
                    <span className="text-xs text-gray-400">{i + 1}</span>
                    <span className="text-sm font-mono font-semibold text-gray-800">{s.sigla}</span>
                    <span className="text-xs text-gray-500">{s.count} cartas</span>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* ── Footer ── */}
        <div className="text-center text-xs text-gray-400 pt-4">
          {hits.meta && <>Hits: {new Date(hits.meta.data).toLocaleString('pt-BR')}</>}
          {hits.meta && snapshot.meta && ' · '}
          {snapshot.meta && <>Snapshot: {new Date(snapshot.meta.data).toLocaleString('pt-BR')}</>}
        </div>
      </div>
    </div>
  );
}