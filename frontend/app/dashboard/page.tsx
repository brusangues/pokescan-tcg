'use client';

import { useState, useEffect } from 'react';
import {
  TrendingUp, TrendingDown, RefreshCw, AlertCircle,
  Zap, Loader, LayoutDashboard, BarChart3, PieChart,
  ArrowUpCircle, ArrowDownCircle, Target, Layers, DollarSign
} from 'lucide-react';
import NavBar from '@/app/components/NavBar';
import { getBasePath } from '@/app/lib/basePath';

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

/** Gráfico de linhas SVG puro (sem lib) — subvalorizadas/inflacionadas/leves por dia. */
function OportunidadesChart({ serie }: { serie: any[] }) {
  const W = 720, H = 240, P = 28;
  const max = Math.max(...serie.flatMap((s: any) => [s.sub, s.infla, s.leve]), 1);
  const x = (i: number) => P + (i / Math.max(serie.length - 1, 1)) * (W - P * 2);
  const y = (v: number) => H - P - (v / max) * (H - P * 2);
  const path = (campo: string) =>
    serie.map((s: any, i: number) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(s[campo]).toFixed(1)}`).join(' ');
  const curto = (d: string) => `${d.slice(8, 10)}/${d.slice(5, 7)}`;
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto">
        {/* grid */}
        {[0, 0.25, 0.5, 0.75, 1].map((f) => (
          <line key={f} x1={P} x2={W - P} y1={y(max * f)} y2={y(max * f)} stroke="#f1f5f9" strokeWidth={1} />
        ))}
        {/* linhas */}
        <path d={path('sub')} fill="none" stroke="#16a34a" strokeWidth={2.5} strokeLinejoin="round" />
        <path d={path('leve')} fill="none" stroke="#f59e0b" strokeWidth={2} strokeLinejoin="round" />
        <path d={path('infla')} fill="none" stroke="#dc2626" strokeWidth={2.5} strokeLinejoin="round" />
        {/* eixo X */}
        {serie.map((s: any, i: number) => (
          <text key={s.data} x={x(i)} y={H - 8} fontSize={9} fill="#94a3b8" textAnchor="middle">
            {curto(s.data)}
          </text>
        ))}
        <text x={P} y={14} fontSize={10} fill="#94a3b8">{max} cartas</text>
      </svg>
      <div className="flex gap-4 mt-2 text-xs text-[#6b6252]">
        <span className="inline-flex items-center gap-1"><span className="w-3 h-0.5 bg-green-600 inline-block" /> Subvalorizadas</span>
        <span className="inline-flex items-center gap-1"><span className="w-3 h-0.5 bg-amber-500 inline-block" /> Leve desconto</span>
        <span className="inline-flex items-center gap-1"><span className="w-3 h-0.5 bg-red-600 inline-block" /> Inflacionadas</span>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${getBasePath()}/data/dashboard.json`);
      if (!res.ok) throw new Error('Erro ao carregar');
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
      <div className="min-h-screen bg-[#fbf4e6] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 text-[#6b6252]">
          <Loader className="w-10 h-10 animate-spin text-[#d40b2e]" />
          <p className="text-sm">Carregando dados de hits e snapshot...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-[#fbf4e6] flex items-center justify-center">
        <div className="bg-[#fffdf7] p-8 rounded-2xl shadow-lg max-w-md text-center space-y-4">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto">
            <AlertCircle className="w-8 h-8 text-red-500" />
          </div>
          <h2 className="text-lg font-bold text-[#292318]">Erro ao carregar</h2>
          <p className="text-sm text-[#6b6252]">{error}</p>
          <button onClick={fetchData} className="inline-flex items-center gap-2 px-4 py-2 bg-[#d40b2e] text-white rounded-lg hover:bg-[#a90924] text-sm">
            <RefreshCw className="w-4 h-4" /> Tentar novamente
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const { hits, snapshot, distribuicao, sets } = data;
  const serieOportunidades: any[] = data.serieOportunidades || [];
  const setsUpside: any[] = data.setsUpside || [];
  const distribuicaoIco: any[] = data.distribuicaoIco || [];
  const maxDist = Math.max(...distribuicao.map((d: any) => d.count), 1);

  // Mini card de métrica
  const MetricCard = ({ label, value, sub, color, icon: Icon }: {
    label: string; value: string | number; sub?: string; color: string; icon: any;
  }) => (
    <div className="bg-[#fffdf7] p-4 rounded-xl border border-[#2b2517]/20 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs text-[#6b6252] uppercase tracking-wide font-medium">{label}</p>
        <Icon className={`w-5 h-5 ${color}`} />
      </div>
      <p className="text-2xl font-bold text-[#292318]">{value}</p>
      {sub && <p className="text-xs text-[#998f7c] mt-0.5">{sub}</p>}
    </div>
  );

  // Row de carta (usada nas top lists)
  const CardRow = ({ card }: { card: ScoredCard }) => (
    <div className="flex items-center gap-2 py-2 text-xs border-b border-gray-50 last:border-0">
      <span className="flex-1 min-w-0 font-medium text-[#292318] truncate">{card.nome}</span>
      <span className="w-12 shrink-0 text-right font-mono text-[#998f7c]">{card.sigla}</span>
      <span className="w-14 shrink-0 text-right text-[#6b6252]">{card.moeda}{card.real.toFixed(0)}</span>
      <span className={`w-12 shrink-0 text-right font-semibold ${card.upside > 0 ? 'text-green-600' : 'text-red-600'}`}>
        {card.upside > 0 ? '+' : ''}{card.upside.toFixed(0)}%
      </span>
      <span className="w-8 shrink-0 text-right text-blue-500">{card.iCO > 0 ? card.iCO : '—'}</span>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#fbf4e6] pb-12">
      {/* Header */}
      <NavBar />
      <div className="bg-[#fffdf7] border-b border-[#2b2517]/20">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-[#292318] flex items-center gap-2">
              <LayoutDashboard className="w-5 h-5 text-[#d40b2e]" />
              Dashboard — PokéScan TCG
            </h1>
            <p className="text-xs text-[#998f7c] mt-0.5">
              Visão geral de hits e snapshot do mercado
            </p>
          </div>
          <button onClick={fetchData} className="p-2 hover:bg-[#f3e9d2] rounded-lg" title="Atualizar">
            <RefreshCw className="w-4 h-4 text-[#6b6252]" />
          </button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-8">

        {/* ── Seção 1: Métricas Chave ── */}
        <section>
          <h2 className="text-sm font-semibold text-[#6b6252] uppercase tracking-wide mb-3 flex items-center gap-2">
            <Target className="w-4 h-4 text-[#998f7c]" />
            Métricas
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
            <MetricCard
              label="Hits escorados"
              value={hits.total}
              sub={hits.meta ? `Último: ${new Date(hits.meta.data).toLocaleDateString('pt-BR')}` : ''}
              color="text-[#d40b2e]"
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
          <h2 className="text-sm font-semibold text-[#6b6252] uppercase tracking-wide mb-3 flex items-center gap-2">
            <PieChart className="w-4 h-4 text-[#6b6252]" />
            Distribuição de Upside (todas as cartas)
          </h2>
          <div className="bg-[#fffdf7] p-6 rounded-2xl border border-[#2b2517]/20 shadow-sm">
            <div className="space-y-2">
              {distribuicao.map((d: any) => {
                const pct = Math.round((d.count / maxDist) * 100);
                const isNegative = d.range.startsWith('-');
                const isPositive = d.range.startsWith('+') || (!isNegative && parseInt(d.range) >= 0);
                return (
                  <div key={d.range} className="flex items-center gap-3">
                    <span className="text-xs font-mono text-[#6b6252] w-20 text-right shrink-0">
                      {d.range}
                    </span>
                    <div className="flex-1 h-6 bg-[#f3e9d2] rounded-md overflow-hidden">
                      <div
                        className={`h-full rounded-md transition-all duration-500 ${
                          isPositive ? 'bg-green-500' : 'bg-red-500'
                        }`}
                        style={{ width: `${Math.max(pct, 2)}%` }}
                      />
                    </div>
                    <span className="text-xs font-medium text-[#6b6252] w-8 shrink-0">{d.count}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* ── Seção 3: Top Oportunidades (Hits) ── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <section className="min-w-0">
            <h2 className="text-sm font-semibold text-green-700 uppercase tracking-wide mb-3 flex items-center gap-2">
              <ArrowUpCircle className="w-4 h-4 shrink-0" />
              🔥 Top 10 — Comprar (Hits)
            </h2>
            <div className="bg-[#fffdf7] rounded-2xl border border-[#2b2517]/20 shadow-sm p-4">
              <div className="flex items-center text-[10px] uppercase font-semibold text-[#998f7c] gap-2 pb-2 border-b border-[#2b2517]/15 mb-1">
                <span className="flex-1 min-w-0">Nome</span>
                <span className="w-12 shrink-0 text-right">Set</span>
                <span className="w-14 shrink-0 text-right">Real</span>
                <span className="w-12 shrink-0 text-right">Upside</span>
                <span className="w-8 shrink-0 text-right">iCO</span>
              </div>
              {hits.topOportunidades.map((c: ScoredCard, i: number) => (
                <CardRow key={`top-${i}`} card={c} />
              ))}
              {hits.topOportunidades.length === 0 && (
                <p className="text-center text-[#998f7c] text-sm py-6">Nenhuma oportunidade encontrada.</p>
              )}
            </div>
          </section>

          <section className="min-w-0">
            <h2 className="text-sm font-semibold text-red-700 uppercase tracking-wide mb-3 flex items-center gap-2">
              <ArrowDownCircle className="w-4 h-4 shrink-0" />
              💀 Top Inflacionadas — Evitar (Hits)
            </h2>
            <div className="bg-[#fffdf7] rounded-2xl border border-[#2b2517]/20 shadow-sm p-4">
              <div className="flex items-center text-[10px] uppercase font-semibold text-[#998f7c] gap-2 pb-2 border-b border-[#2b2517]/15 mb-1">
                <span className="flex-1 min-w-0">Nome</span>
                <span className="w-12 shrink-0 text-right">Set</span>
                <span className="w-14 shrink-0 text-right">Real</span>
                <span className="w-12 shrink-0 text-right">Upside</span>
                <span className="w-8 shrink-0 text-right">iCO</span>
              </div>
              {hits.topInflacionadas.map((c: ScoredCard, i: number) => (
                <CardRow key={`i-${i}`} card={c} />
              ))}
              {hits.topInflacionadas.length === 0 && (
                <p className="text-center text-[#998f7c] text-sm py-6">Nenhuma inflacionada extrema.</p>
              )}
            </div>
          </section>
        </div>

        {/* ── Seção 4: Top Sets ── */}
        {sets.length > 0 && (
          <section>
            <h2 className="text-sm font-semibold text-[#6b6252] uppercase tracking-wide mb-3 flex items-center gap-2">
              <DollarSign className="w-4 h-4 text-[#6b6252]" />
              Sets com mais movimentação (Hits)
            </h2>
            <div className="bg-[#fffdf7] rounded-2xl border border-[#2b2517]/20 shadow-sm p-4">
              <div className="flex flex-wrap gap-3">
                {sets.map((s: any, i: number) => (
                  <div key={s.sigla} className="inline-flex items-center gap-2 px-3 py-2 bg-[#f3e9d2] rounded-lg">
                    <span className="text-xs text-[#998f7c]">{i + 1}</span>
                    <span className="text-sm font-mono font-semibold text-[#292318]">{s.sigla}</span>
                    <span className="text-xs text-[#6b6252]">{s.count} cartas</span>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* ── Seção 5: Evolução temporal de oportunidades (P2.13) ── */}
        {serieOportunidades.length > 1 && (
          <section>
            <h2 className="text-sm font-semibold text-[#6b6252] uppercase tracking-wide mb-3 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-[#6b6252]" />
              Evolução de Oportunidades (hits por dia)
            </h2>
            <div className="bg-[#fffdf7] rounded-2xl border border-[#2b2517]/20 shadow-sm p-4">
              <OportunidadesChart serie={serieOportunidades} />
            </div>
          </section>
        )}

        {/* ── Seção 6: Top sets por upside médio (P2.13) ── */}
        {setsUpside.length > 0 && (
          <section>
            <h2 className="text-sm font-semibold text-[#6b6252] uppercase tracking-wide mb-3 flex items-center gap-2">
              <Zap className="w-4 h-4 text-[#6b6252]" />
              Top Sets por Upside Médio (hits + snapshot)
            </h2>
            <div className="bg-[#fffdf7] rounded-2xl border border-[#2b2517]/20 shadow-sm p-4">
              {(() => {
                const maxMedia = Math.max(...setsUpside.map((s: any) => s.media), 1);
                return (
                  <div className="space-y-2">
                    {setsUpside.map((s: any, i: number) => {
                      const positivo = s.media >= 0;
                      return (
                        <div key={s.sigla} className="flex items-center gap-3">
                          <span className="text-xs text-[#998f7c] w-5 text-right shrink-0">{i + 1}</span>
                          <span className="text-sm font-mono font-semibold text-[#292318] w-16 shrink-0">{s.sigla}</span>
                          <div className="flex-1 h-5 bg-[#f3e9d2] rounded-md overflow-hidden">
                            <div
                              className={`h-full rounded-md transition-all duration-500 ${positivo ? 'bg-green-500' : 'bg-red-500'}`}
                              style={{ width: `${Math.max(Math.abs(s.media) / maxMedia * 100, 2)}%` }}
                            />
                          </div>
                          <span className={`text-xs font-semibold w-20 text-right shrink-0 ${positivo ? 'text-green-600' : 'text-red-600'}`}>
                            {s.media > 0 ? '+' : ''}{s.media.toFixed(1)}%
                          </span>
                          <span className="text-xs text-[#998f7c] w-12 text-right shrink-0">{s.n} cartas</span>
                        </div>
                      );
                    })}
                  </div>
                );
              })()}
            </div>
          </section>
        )}

        {/* ── Seção 7: Distribuição de iCO (P2.13) ── */}
        {distribuicaoIco.length > 0 && (
          <section>
            <h2 className="text-sm font-semibold text-[#6b6252] uppercase tracking-wide mb-3 flex items-center gap-2">
              <Layers className="w-4 h-4 text-[#6b6252]" />
              Distribuição de Vendedores (iCO)
            </h2>
            <div className="bg-[#fffdf7] rounded-2xl border border-[#2b2517]/20 shadow-sm p-4">
              {(() => {
                const maxIco = Math.max(...distribuicaoIco.map((d: any) => d.count), 1);
                return (
                  <div className="space-y-2">
                    {distribuicaoIco.map((d: any) => (
                      <div key={d.range} className="flex items-center gap-3">
                        <span className="text-xs font-mono text-[#6b6252] w-10 text-right shrink-0">{d.range}</span>
                        <span className="text-xs text-[#998f7c] w-20 shrink-0">
                          {d.range === '0' ? 'sem vendedores' : d.range === '1' ? '1 vendedor' : 'vendedores'}
                        </span>
                        <div className="flex-1 h-6 bg-[#f3e9d2] rounded-md overflow-hidden">
                          <div
                            className="h-full rounded-md bg-[#f3e9d2]0 transition-all duration-500"
                            style={{ width: `${Math.max(d.count / maxIco * 100, 2)}%` }}
                          />
                        </div>
                        <span className="text-xs font-medium text-[#6b6252] w-8 shrink-0">{d.count}</span>
                      </div>
                    ))}
                  </div>
                );
              })()}
            </div>
          </section>
        )}

        {/* ── Footer ── */}
        <div className="text-center text-xs text-[#998f7c] pt-4">
          {hits.meta && <>Hits: {new Date(hits.meta.data).toLocaleString('pt-BR')}</>}
          {hits.meta && snapshot.meta && ' · '}
          {snapshot.meta && <>Snapshot: {new Date(snapshot.meta.data).toLocaleString('pt-BR')}</>}
        </div>
      </div>
    </div>
  );
}