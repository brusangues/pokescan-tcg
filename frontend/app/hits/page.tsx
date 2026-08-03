'use client';

import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, RefreshCw, AlertCircle, Clock, Zap, Loader } from 'lucide-react';

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

export default function HitsPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<'oportunidades' | 'inflacionadas' | 'todas'>('oportunidades');

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/hits');
      if (!res.ok) throw new Error((await res.json()).error || 'Erro ao carregar');
      const json = await res.json();
      setData(json);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const CardRow = ({ card }: { card: ScoredCard }) => {
    const isUp = card.upside > 0;
    const isSub = card.oportunidade === '🔥 Subvalorizada';
    const isInfla = card.oportunidade === '💀 Inflacionada';

    return (
      <div className={`
        flex items-center gap-3 px-4 py-3 border-b border-gray-100 last:border-0
        hover:bg-gray-50 transition-colors
        ${isSub ? 'bg-green-50/30' : isInfla ? 'bg-red-50/30' : ''}
      `}>
        {/* Nome + Sigla */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold text-gray-900 truncate">{card.nome}</p>
            <span className="text-[10px] font-mono bg-gray-100 px-1.5 py-0.5 rounded text-gray-500 shrink-0">
              {card.sigla}
            </span>
          </div>
        </div>

        {/* Preço Real */}
        <div className="text-right shrink-0 w-24">
          <p className="text-sm font-bold text-gray-800">
            {card.moeda}{card.real.toFixed(2)}
          </p>
        </div>

        {/* Preço Predito */}
        <div className="text-right shrink-0 w-24">
          <p className="text-sm text-gray-600">
            {card.moeda}{card.pred.toFixed(2)}
          </p>
        </div>

        {/* Upside */}
        <div className={`text-right shrink-0 w-20`}>
          <span className={`inline-flex items-center gap-1 text-xs font-bold px-2 py-1 rounded-full ${
            isUp ? 'text-green-700 bg-green-100' : 'text-red-700 bg-red-100'
          }`}>
            {isUp ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
            {isUp ? '+' : ''}{card.upside.toFixed(0)}%
          </span>
        </div>

        {/* iCO (liquidez) */}
        <div className="text-right shrink-0 w-12">
          {card.iCO > 0 ? (
            <span className="text-[11px] font-medium text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">
              {card.iCO}
            </span>
          ) : (
            <span className="text-[11px] text-gray-300">—</span>
          )}
        </div>

        {/* Status */}
        <div className="shrink-0 w-28 text-right">
          <span className={`text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full ${
            isSub ? 'text-green-700 bg-green-100' :
            isInfla ? 'text-red-700 bg-red-100' :
            'text-gray-500 bg-gray-100'
          }`}>
            {card.oportunidade.replace('🔥 ', '').replace('💀 ', '')}
          </span>
        </div>
      </div>
    );
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
          <button
            onClick={fetchData}
            className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors text-sm"
          >
            <RefreshCw className="w-4 h-4" /> Tentar novamente
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const { todas, subvalorizadas, inflacionadas } = data;
  const cards = tab === 'oportunidades' ? subvalorizadas :
                tab === 'inflacionadas' ? inflacionadas :
                todas;

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm">
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
          <button
            onClick={fetchData}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            title="Atualizar"
          >
            <RefreshCw className="w-4 h-4 text-gray-500" />
          </button>
        </div>
      </header>

      {/* Stats */}
      <div className="max-w-6xl mx-auto px-4 py-6">
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="bg-white p-4 rgounded-xl border border-gray-200">
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
                tab === t
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'
              }`}
            >
              {t === 'oportunidades' ? `🔥 Comprar (${subvalorizadas.length})` :
               t === 'inflacionadas' ? `💀 Evitar (${inflacionadas.length})` :
               `📋 Todas (${todas.length})`}
            </button>
          ))}
        </div>

        {/* Cards Table */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
          {/* Table Header */}
          <div className="flex items-center gap-3 px-4 py-2 bg-gray-50 border-b border-gray-200 text-xs font-semibold text-gray-500 uppercase tracking-wide">
            <span className="flex-1">Novo</span>
            <span className="w-24 text-right ms-1 hidden sm:inline">Real</span>
            <span className="w-24 text-right hidden sm:inline">Predito</span>
            <span className="w-20 text-right">Variação</span>
            <span className="w-12 text-right">iCO</span>
            <span className="w-16 text-right">Status</span>
          </div>

          {cards.length === 0 ? (
            <div className="px-6 py-12 text-center text-gray-400">
              Nenhuma carta encontrada nessa categoria.
            </div>
          ) : (
            cards.map((card: ScoredCard, i: number) => (
              <CardRow key={`${card.nome}-${card.sigla}-${i}`} card={card} />
            ))
          )}
        </div>

        {data.ultimaAtualizacao && (
          <p className="text-sm text-gray-400 text-right pt-4">
            Última atualização: {new Date(data.ultimaAtualizacao).toLocaleString('pt-BR')}
          </p>
        )}
      </div>
    </div>
  );
}