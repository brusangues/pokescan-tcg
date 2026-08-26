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
      <div className="min-h-screen bg-[#fbf4e6] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 text-[#6b6252]">
          <Loader className="w-8 h-8 animate-spin text-[#d40b2e]" />
          <p className="text-sm">Carregando dados dos hits...</p>
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
          <button onClick={() => fetchData()} className="inline-flex items-center gap-2 px-4 py-2 bg-[#d40b2e] text-white rounded-lg hover:bg-[#a90924] transition-colors text-sm">
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
    <div className="min-h-screen bg-[#fbf4e6]">
      <NavBar />
      <div className="bg-[#fffdf7] border-b border-[#2b2517]/20">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-[#292318] flex items-center gap-2">
              <Zap className="w-5 h-5 text-[#d40b2e]" />
              Hits da Liga Pokémon
            </h1>
            <p className="text-xs text-[#998f7c] mt-0.5">
              {data.ultimaAtualizacao && (
                <><Clock className="w-3 h-3 inline mr-1" />{new Date(data.ultimaAtualizacao).toLocaleString('pt-BR')}</>
              )}
            </p>
          </div>
          <button onClick={() => fetchData(selectedFile ?? undefined)} className="p-2 hover:bg-[#f3e9d2] rounded-lg transition-colors" title="Atualizar">
            <RefreshCw className="w-4 h-4 text-[#6b6252]" />
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
          <div className="bg-[#fffdf7] rounded-2xl p-4 border border-[#2b2517]/20 mb-6 shadow-sm">
            <div className="flex items-center gap-2 mb-3">
              <Calendar className="w-4 h-4 text-[#d40b2e]" />
              <h2 className="text-sm font-semibold text-[#292318]">Selecionar janela</h2>
            </div>
            <div className="flex flex-wrap gap-2">
              {dias.map((dia: Dia) => (
                <div key={dia.data} className="relative">
                  <button
                    onClick={() => {
                      const abrindo = expandedDay !== dia.data;
                      setExpandedDay(abrindo ? dia.data : null);
                      // Feedback no 1º clique: dia antigo não tem dados no build estático
                      if (abrindo && selectedFile && !dia.arquivos.includes(selectedFile)) {
                        setAviso('Execuções antigas não estão no build estático — mostrando a mais recente.');
                      }
                    }}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors border ${
                      selectedFile && dia.arquivos.includes(selectedFile)
                        ? 'bg-[#d40b2e] text-white border-[#d40b2e]'
                        : 'bg-[#fffdf7] text-[#292318] border-[#2b2517]/20 hover:bg-[#f3e9d2]'
                    }`}
                  >
                    {dia.label}
                    <ChevronDown className={`w-3 h-3 transition-transform ${expandedDay === dia.data ? 'rotate-180' : ''}`} />
                  </button>
                  {expandedDay === dia.data && (
                    <div className="absolute top-full mt-1 left-0 bg-[#fffdf7] rounded-lg shadow-lg border border-[#2b2517]/20 py-1 z-20 min-w-[200px]">
                      {dia.arquivos.length <= 1 ? (
                        <button
                          onClick={() => { selectArquivo(dia.arquivos[0]); setExpandedDay(null); }}
                          className="w-full text-left px-3 py-1.5 text-xs text-[#6b6252] hover:bg-[#f3e9d2] flex items-center gap-2"
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
                              className={`w-full text-left px-3 py-1.5 text-xs hover:bg-[#f3e9d2] flex items-center gap-2 ${
                                isActive ? 'bg-[#f3e9d2] text-[#a90924] font-medium' : 'text-[#6b6252]'
                              }`}
                            >
                              <FileText className={`w-3 h-3 ${isActive ? 'text-[#d40b2e]' : 'text-[#998f7c]'}`} />
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
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 sm:gap-4 mb-6">
          <div className="bg-[#fffdf7] p-3 sm:p-4 rounded-xl border border-[#2b2517]/20">
            <p className="text-[10px] sm:text-xs text-[#6b6252] uppercase tracking-wide">Total escorado</p>
            <p className="text-xl sm:text-2xl font-bold text-[#292318]">{data.total}</p>
          </div>
          <div className="bg-green-50 p-3 sm:p-4 rounded-xl border border-green-200">
            <p className="text-[10px] sm:text-xs text-green-700 uppercase tracking-wide">🔥 Subvalorizadas</p>
            <p className="text-xl sm:text-2xl font-bold text-green-900">{data.subvalorizadas.length}</p>
          </div>
          <div className="bg-red-50 p-3 sm:p-4 rounded-xl border border-red-200">
            <p className="text-[10px] sm:text-xs text-red-700 uppercase tracking-wide">💀 Inflacionadas</p>
            <p className="text-xl sm:text-2xl font-bold text-red-900">
              {data.todas.filter((c: ScoredCard) => c.oportunidade === '💀 Inflacionada').length}
            </p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-4 overflow-x-auto pb-1 -mx-4 px-4 sm:mx-0 sm:px-0">
          {['oportunidades', 'inflacionadas', 'todas'].map(t => (
            <button
              key={t}
              onClick={() => setTab(t as any)}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors whitespace-nowrap shrink-0 ${
                tab === t ? 'bg-[#d40b2e] text-white shadow-sm' : 'bg-[#fffdf7] text-[#6b6252] hover:bg-[#f3e9d2] border border-[#2b2517]/20'
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
          <p className="text-xs text-[#998f7c] text-right pt-3">
            Arquivo: {data.arquivo} · {new Date(data.ultimaAtualizacao).toLocaleString('pt-BR')}
          </p>
        )}
      </div>
    </div>
  );
}