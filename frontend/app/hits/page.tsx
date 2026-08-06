'use client';

import { useState, useEffect } from 'react';
import { RefreshCw, AlertCircle, Clock, Zap, Loader, Calendar, ChevronDown, FileText } from 'lucide-react';

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

interface Dia {
  data: string;
  label: string;
  arquivos: string[];
}

export default function HitsPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<'oportunidades' | 'inflacionadas' | 'todas'>('oportunidades');
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [expandedDay, setExpandedDay] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const fetchData = async (arquivo?: string) => {
    setLoading(true);
    setError(null);
    try {
      // Build estático: os dados são pré-gerados em public/data/hits.json
      // (apenas o arquivo mais recente; a lista `dias` preserva o histórico)
      const res = await fetch(`${getBasePath()}/data/hits.json`);
      if (!res.ok) throw new Error('Erro ao carregar');
      const json = await res.json();
      setData(json);
      if (!arquivo) setSelectedFile(json.arquivo);
      else if (arquivo !== json.arquivo) {
        setAviso('Execuções antigas não estão no build estático — mostrando a mais recente.');
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

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 text-gray-500">
          <Loader className="w-8 h-8 animate-spin text-indigo-600" />
          <p className="text-sm">Carregando dados dos hits...</p>
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
          <button onClick={() => fetchData()} className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors text-sm">
            <RefreshCw className="w-4 h-4" /> Tentar novamente
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const { todas, subvalorizadas, inflacionadas, dias } = data;
  const cards = tab === 'oportunidades' ? subvalorizadas :
                tab === 'inflacionadas' ? inflacionadas :
                todas;

  return (
    <div className="min-h-screen bg-slate-50">
      <NavBar />
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
              <Zap className="w-5 h-5 text-indigo-600" />
              Hits da Liga Pokémon
            </h1>
            <p className="text-xs text-gray-400 mt-0.5">
              {data.ultimaAtualizacao && (
                <><Clock className="w-3 h-3 inline mr-1" />{new Date(data.ultimaAtualizacao).toLocaleString('pt-BR')}</>
              )}
            </p>
          </div>
          <button onClick={() => fetchData(selectedFile ?? undefined)} className="p-2 hover:bg-gray-100 rounded-lg transition-colors" title="Atualizar">
            <RefreshCw className="w-4 h-4 text-gray-500" />
          </button>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-6">
        {aviso && (
          <div className="bg-amber-50 border border-amber-200 text-amber-800 text-xs rounded-lg px-3 py-2 mb-4 flex items-center justify-between">
            <span>{aviso}</span>
            <button onClick={() => setAviso(null)} className="ml-2 font-bold hover:text-amber-900">✕</button>
          </div>
        )}
        {/* Seletor de data e janela */}
        {dias && dias.length > 0 && (
          <div className="bg-white rounded-2xl p-4 border border-gray-200 mb-6 shadow-sm">
            <div className="flex items-center gap-2 mb-3">
              <Calendar className="w-4 h-4 text-indigo-500" />
              <h2 className="text-sm font-semibold text-gray-700">Selecionar janela</h2>
            </div>
            <div className="flex flex-wrap gap-2">
              {dias.map((dia: Dia) => (
                <div key={dia.data} className="relative">
                  <button
                    onClick={() => setExpandedDay(expandedDay === dia.data ? null : dia.data)}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors border ${
                      selectedFile && dia.arquivos.includes(selectedFile)
                        ? 'bg-indigo-600 text-white border-indigo-600'
                        : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
                    }`}
                  >
                    {dia.label}
                    <ChevronDown className={`w-3 h-3 transition-transform ${expandedDay === dia.data ? 'rotate-180' : ''}`} />
                  </button>
                  {expandedDay === dia.data && (
                    <div className="absolute top-full mt-1 left-0 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-20 min-w-[200px]">
                      {dia.arquivos.length <= 1 ? (
                        <button
                          onClick={() => { selectArquivo(dia.arquivos[0]); setExpandedDay(null); }}
                          className="w-full text-left px-3 py-1.5 text-xs text-gray-500 hover:bg-gray-50 flex items-center gap-2"
                        >
                          <FileText className="w-3 h-3" />
                          Única execução
                        </button>
                      ) : (
                        dia.arquivos.map((f: string) => {
                          const timeMatch = f.match(/_(\d{6})\.csv$/);
                          const time = timeMatch ? `${timeMatch[1].slice(0, 2)}:${timeMatch[1].slice(2, 4)}` : '';
                          const isActive = f === selectedFile;
                          return (
                            <button
                              key={f}
                              onClick={() => { selectArquivo(f); setExpandedDay(null); }}
                              className={`w-full text-left px-3 py-1.5 text-xs hover:bg-gray-50 flex items-center gap-2 ${
                                isActive ? 'bg-indigo-50 text-indigo-700 font-medium' : 'text-gray-600'
                              }`}
                            >
                              <FileText className={`w-3 h-3 ${isActive ? 'text-indigo-500' : 'text-gray-400'}`} />
                              {time ? `${time}` : 'Última'}
                              {isActive && <span className="text-[10px] text-indigo-400 ml-auto">✓</span>}
                            </button>
                          );
                        })
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="bg-white p-4 rounded-xl border border-gray-200">
            <p className="text-xs text-gray-500 uppercase tracking-wide">Total escorado</p>
            <p className="text-2xl font-bold text-gray-900">{data.total}</p>
          </div>
          <div className="bg-green-50 p-4 rounded-xl border border-green-200">
            <p className="text-xs text-green-700 uppercase tracking-wide">🔥 Subvalorizadas</p>
            <p className="text-2xl font-bold text-green-900">{data.subvalorizadas.length}</p>
          </div>
          <div className="bg-red-50 p-4 rounded-xl border border-red-200">
            <p className="text-xs text-red-700 uppercase tracking-wide">💀 Inflacionadas</p>
            <p className="text-2xl font-bold text-red-900">
              {data.todas.filter((c: ScoredCard) => c.oportunidade === '💀 Inflacionada').length}
            </p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-4">
          {['oportunidades', 'inflacionadas', 'todas'].map(t => (
            <button
              key={t}
              onClick={() => setTab(t as any)}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                tab === t ? 'bg-indigo-600 text-white shadow-sm' : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'
              }`}
            >
              {t === 'oportunidades' ? `🔥 Comprar (${subvalorizadas.length})` :
               t === 'inflacionadas' ? `💀 Evitar (${inflacionadas.length})` :
               `📋 Todas (${todas.length})`}
            </button>
          ))}
        </div>

        {/* Cards Table */}
        <ScoredTable cards={cards} />

        {data.ultimaAtualizacao && (
          <p className="text-xs text-gray-400 text-right pt-3">
            Arquivo: {data.arquivo} · {new Date(data.ultimaAtualizacao).toLocaleString('pt-BR')}
          </p>
        )}
      </div>
    </div>
  );
}