'use client';

import { useState, useEffect } from 'react';
import {
  RefreshCw, AlertCircle,
  Clock, Loader, BarChart3, Calendar, ChevronDown,
  FileText, Target, ArrowUpCircle, ArrowDownCircle, DollarSign,
} from 'lucide-react';
import NavBar from '@/app/components/NavBar';
import ScoredTable from '@/app/components/ScoredTable';
import { getBasePath } from '@/app/lib/basePath';

interface ScoredCard {
  nome: string;
  sigla: string;
  setNome?: string;
  real: number;
  pred: number;
  upside: number;
  oportunidade: string;
  iCO: number;
  moeda: string;
  nEN?: string;
  sNumber?: string;
  num?: string;
}

interface ArquivoDisponivel {
  arquivo: string;
  label: string;
  data: string;
  cartas: number;
}

interface Semana {
  label: string;
  arquivos: ArquivoDisponivel[];
}

export default function SnapshotPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<'oportunidades' | 'inflacionadas' | 'todas'>('oportunidades');
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [expandedWeek, setExpandedWeek] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const fetchData = async (arquivo?: string) => {
    setLoading(true);
    setError(null);
    try {
      // Build estático: dados pré-gerados em public/data/snapshots.json
      // (apenas o snapshot mais recente; disponiveis/semanas preservam o histórico)
      const res = await fetch(`${getBasePath()}/data/snapshots.json`);
      if (!res.ok) throw new Error('Erro ao carregar');
      const json = await res.json();
      setData(json);
      if (!arquivo) setSelectedFile(json.arquivo);
      else if (arquivo !== json.arquivo) {
        setAviso('Snapshots antigos não estão no build estático — mostrando o mais recente.');
        setSelectedFile(json.arquivo);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const selectArquivo = (f: string) => {
    setSelectedFile(f);
    fetchData(f);
  };

  // Card de métrica
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

  // Row compacto para tabela (substituído pelo componente ScoredCardRow)

  if (loading && !data) {
    return (
      <div className="min-h-screen bg-[#fbf4e6] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 text-[#6b6252]">
          <Loader className="w-10 h-10 animate-spin text-[#d40b2e]" />
          <p className="text-sm">Carregando dados do snapshot...</p>
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
          <button onClick={() => fetchData()} className="inline-flex items-center gap-2 px-4 py-2 bg-[#d40b2e] text-white rounded-lg hover:bg-[#a90924] text-sm">
            <RefreshCw className="w-4 h-4" /> Tentar novamente
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const { total, subvalorizadas, inflacionadas, todas, justo, sets, disponiveis, semanas } = data;
  const cards = tab === 'oportunidades' ? subvalorizadas :
                tab === 'inflacionadas' ? inflacionadas :
                todas;

  return (
    <div className="min-h-screen bg-[#fbf4e6] pb-12">
      {/* Header */}
      <NavBar />
      <div className="bg-[#fffdf7] border-b border-[#2b2517]/20">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-[#292318] flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-purple-600" />
              Snapshot da Liga Pokémon
            </h1>
            <p className="text-xs text-[#998f7c] mt-0.5">
              {data.ultimaAtualizacao && (
                <><Clock className="w-3 h-3 inline mr-1" />{new Date(data.ultimaAtualizacao).toLocaleString('pt-BR')}</>
              )}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {loading && <Loader className="w-4 h-4 animate-spin text-[#998f7c]" />}
            <button onClick={() => fetchData(selectedFile ?? undefined)} className="p-2 hover:bg-[#f3e9d2] rounded-lg" title="Atualizar">
              <RefreshCw className="w-4 h-4 text-[#6b6252]" />
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">

        {aviso && (
          <div className="bg-amber-50 border border-amber-200 text-amber-800 text-xs rounded-lg px-3 py-2 flex items-center justify-between">
            <span>{aviso}</span>
            <button onClick={() => setAviso(null)} className="ml-2 font-bold hover:text-amber-900">✕</button>
          </div>
        )}

        {/* Seletor de semana/arquivo */}
        {semanas && semanas.length > 0 && (
          <section className="bg-[#fffdf7] rounded-2xl p-4 border border-[#2b2517]/20 shadow-sm">
            <div className="flex items-center gap-2 mb-3">
              <Calendar className="w-4 h-4 text-purple-500" />
              <h2 className="text-sm font-semibold text-[#292318]">Selecionar snapshot</h2>
            </div>
            <div className="flex flex-wrap gap-2">
              {semanas.map((sem: Semana) => {
                const isActive = sem.arquivos.some(a => a.arquivo === selectedFile);
                return (
                  <div key={sem.label} className="relative">
                    <button
                      onClick={() => {
                        const abrindo = expandedWeek !== sem.label;
                        setExpandedWeek(abrindo ? sem.label : null);
                        // Feedback no 1º clique: semana antiga não tem dados no build estático
                        if (abrindo && selectedFile && !sem.arquivos.some(a => a.arquivo === selectedFile)) {
                          setAviso('Execuções antigas não estão no build estático — mostrando a mais recente.');
                        }
                      }}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors border ${
                        isActive ? 'bg-purple-600 text-white border-purple-600' : 'bg-[#fffdf7] text-[#292318] border-[#2b2517]/20 hover:bg-[#f3e9d2]'
                      }`}
                    >
                      {sem.label}
                      <ChevronDown className={`w-3 h-3 transition-transform ${expandedWeek === sem.label ? 'rotate-180' : ''}`} />
                    </button>
                    {expandedWeek === sem.label && (
                      <div className="absolute top-full mt-1 left-0 bg-[#fffdf7] rounded-lg shadow-lg border border-[#2b2517]/20 py-1 z-20 min-w-[230px]">
                        {sem.arquivos.map((f: ArquivoDisponivel) => (
                          <button
                            key={f.arquivo}
                            onClick={() => { selectArquivo(f.arquivo); setExpandedWeek(null); }}
                            className={`w-full text-left px-3 py-1.5 text-xs hover:bg-[#f3e9d2] flex items-center justify-between gap-2 ${
                              f.arquivo === selectedFile ? 'bg-purple-50 text-purple-700 font-medium' : 'text-[#6b6252]'
                            }`}
                          >
                            <span className="flex items-center gap-2">
                              <FileText className={`w-3 h-3 ${f.arquivo === selectedFile ? 'text-purple-500' : 'text-[#998f7c]'}`} />
                              {f.label}
                            </span>
                            <span className="text-[10px] text-[#998f7c]">{f.cartas} cartas</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* Métricas */}
        <section>
          <h2 className="text-sm font-semibold text-[#6b6252] uppercase tracking-wide mb-3 flex items-center gap-2">
            <Target className="w-4 h-4 text-[#998f7c]" />
            Métricas do Snapshot
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <MetricCard label="Total escorado" value={total} color="text-purple-600" icon={BarChart3} />
            <MetricCard label="🔥 Subvalorizadas" value={subvalorizadas.length} sub="Pred > Real +25%" color="text-green-600" icon={ArrowUpCircle} />
            <MetricCard label="💀 Inflacionadas" value={inflacionadas.length} color="text-red-600" icon={ArrowDownCircle} />
            <MetricCard label="⚖ Preço Justo" value={justo} color="text-blue-500" icon={Target} />
            <MetricCard
              label="Sets"
              value={sets.length}
              sub={`Top: ${sets[0]?.sigla || '—'} (${sets[0]?.count || 0})`}
              color="text-amber-500"
              icon={DollarSign}
            />
          </div>
        </section>

        {/* Tabs */}
        {(data.subvalorizadas_usd?.length || data.inflacionadas_usd?.length) > 0 && (
          <div className="bg-sky-50 border border-sky-200 text-sky-800 text-xs rounded-lg px-3 py-2 flex items-center justify-between">
            <span>
              ⚠️ {data.subvalorizadas_usd?.length || 0} subvalorizada(s) e{' '}
              {data.inflacionadas_usd?.length || 0} inflacionada(s) listadas em <b>US$</b>{' '}
              (sem preço BR na Liga) — veja a aba “Todas”.
            </span>
            <button onClick={() => setTab('todas')} className="ml-2 font-bold hover:text-sky-900 shrink-0">
              Ver todas →
            </button>
          </div>
        )}

        <div className="flex gap-2 mb-4 overflow-x-auto pb-1 -mx-4 px-4 sm:mx-0 sm:px-0">
          {['oportunidades', 'inflacionadas', 'todas'].map(t => (
            <button
              key={t}
              onClick={() => setTab(t as any)}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors whitespace-nowrap shrink-0 ${
                tab === t ? 'bg-purple-600 text-white shadow-sm' : 'bg-[#fffdf7] text-[#6b6252] hover:bg-[#f3e9d2] border border-[#2b2517]/20'
              }`}
            >
              {t === 'oportunidades' ? `🔥 Comprar (${subvalorizadas.length})` :
               t === 'inflacionadas' ? `💀 Evitar (${inflacionadas.length})` :
               `📋 Todas (${todas.length})`}
            </button>
          ))}
        </div>

        {/* Tabela */}
        <ScoredTable cards={cards} />

        {/* Footer */}
        <div className="text-center text-xs text-[#998f7c] pt-4">
          Arquivo: {data.arquivo} · {new Date(data.ultimaAtualizacao).toLocaleString('pt-BR')}
        </div>
      </div>
    </div>
  );
}