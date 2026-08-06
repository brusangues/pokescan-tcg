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
    <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">{label}</p>
        <Icon className={`w-5 h-5 ${color}`} />
      </div>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );

  // Row compacto para tabela (substituído pelo componente ScoredCardRow)

  if (loading && !data) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 text-gray-500">
          <Loader className="w-10 h-10 animate-spin text-indigo-600" />
          <p className="text-sm">Carregando dados do snapshot...</p>
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
          <button onClick={() => fetchData()} className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm">
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
    <div className="min-h-screen bg-slate-50 pb-12">
      {/* Header */}
      <NavBar />
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-purple-600" />
              Snapshot da Liga Pokémon
            </h1>
            <p className="text-xs text-gray-400 mt-0.5">
              {data.ultimaAtualizacao && (
                <><Clock className="w-3 h-3 inline mr-1" />{new Date(data.ultimaAtualizacao).toLocaleString('pt-BR')}</>
              )}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {loading && <Loader className="w-4 h-4 animate-spin text-gray-400" />}
            <button onClick={() => fetchData(selectedFile ?? undefined)} className="p-2 hover:bg-gray-100 rounded-lg" title="Atualizar">
              <RefreshCw className="w-4 h-4 text-gray-500" />
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
          <section className="bg-white rounded-2xl p-4 border border-gray-200 shadow-sm">
            <div className="flex items-center gap-2 mb-3">
              <Calendar className="w-4 h-4 text-purple-500" />
              <h2 className="text-sm font-semibold text-gray-700">Selecionar snapshot</h2>
            </div>
            <div className="flex flex-wrap gap-2">
              {semanas.map((sem: Semana) => {
                const isActive = sem.arquivos.some(a => a.arquivo === selectedFile);
                return (
                  <div key={sem.label} className="relative">
                    <button
                      onClick={() => setExpandedWeek(expandedWeek === sem.label ? null : sem.label)}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors border ${
                        isActive ? 'bg-purple-600 text-white border-purple-600' : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
                      }`}
                    >
                      {sem.label}
                      <ChevronDown className={`w-3 h-3 transition-transform ${expandedWeek === sem.label ? 'rotate-180' : ''}`} />
                    </button>
                    {expandedWeek === sem.label && (
                      <div className="absolute top-full mt-1 left-0 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-20 min-w-[230px]">
                        {sem.arquivos.map((f: ArquivoDisponivel) => (
                          <button
                            key={f.arquivo}
                            onClick={() => { selectArquivo(f.arquivo); setExpandedWeek(null); }}
                            className={`w-full text-left px-3 py-1.5 text-xs hover:bg-gray-50 flex items-center justify-between gap-2 ${
                              f.arquivo === selectedFile ? 'bg-purple-50 text-purple-700 font-medium' : 'text-gray-600'
                            }`}
                          >
                            <span className="flex items-center gap-2">
                              <FileText className={`w-3 h-3 ${f.arquivo === selectedFile ? 'text-purple-500' : 'text-gray-400'}`} />
                              {f.label}
                            </span>
                            <span className="text-[10px] text-gray-400">{f.cartas} cartas</span>
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
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-2">
            <Target className="w-4 h-4 text-gray-400" />
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
        <div className="flex gap-2">
          {['oportunidades', 'inflacionadas', 'todas'].map(t => (
            <button
              key={t}
              onClick={() => setTab(t as any)}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                tab === t ? 'bg-purple-600 text-white shadow-sm' : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'
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
        <div className="text-center text-xs text-gray-400 pt-4">
          Arquivo: {data.arquivo} · {new Date(data.ultimaAtualizacao).toLocaleString('pt-BR')}
        </div>
      </div>
    </div>
  );
}