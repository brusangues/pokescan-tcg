'use client';

import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, RefreshCw, AlertCircle, Loader, Calendar } from 'lucide-react';
import NavBar from '@/app/components/NavBar';
import { getBasePath } from '@/app/lib/basePath';

interface TendCard {
  card_id: string;
  nome: string;
  set: string;
  setNome: string;
  num: string;
  rarity: string;
  img: string;
  atual: number;
  prev: number;
  tendencia_pct: number;
}

function href(card: TendCard) {
  // id do catálogo → card detail via set+num+nome (Estratégia 2 do lookup)
  return `${getBasePath()}/card?set=${encodeURIComponent(card.set)}&num=${encodeURIComponent(card.num)}&nome=${encodeURIComponent(card.nome)}`;
}

function RowTendencia({ c, dir }: { c: TendCard; dir: 'up' | 'down' }) {
  const up = dir === 'up';
  return (
    <a href={href(c)} className="block">
      <div className="flex items-center gap-3 py-2.5 border-b border-gray-50 last:border-0 hover:bg-slate-50 rounded-lg px-2 -mx-2 transition-colors">
        <img
          src={c.img}
          alt={c.nome}
          className="w-9 h-[12.6px] object-contain rounded-sm"
          loading="lazy"
          onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
        />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-800 truncate">{c.nome}</p>
          <p className="text-[11px] text-gray-400 truncate">{c.setNome} #{c.num} · {c.rarity}</p>
        </div>
        <div className="text-right shrink-0">
          <p className="text-xs text-gray-500 tabular-nums">
            <span className="line-through text-gray-400">${c.atual.toFixed(2)}</span>
            <span className="ml-1 font-semibold text-gray-900">${c.prev.toFixed(2)}</span>
          </p>
        </div>
        <span
          className={`shrink-0 inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full ${
            up ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'
          }`}
        >
          {up ? '▲' : '▼'} {Math.abs(c.tendencia_pct).toFixed(1)}%
        </span>
      </div>
    </a>
  );
}

export default function TendenciasPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${getBasePath()}/data/tendencias.json`);
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
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader className="w-10 h-10 animate-spin text-indigo-600" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="bg-white p-8 rounded-2xl shadow-lg max-w-md text-center space-y-4">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto">
            <AlertCircle className="w-8 h-8 text-red-500" />
          </div>
          <h2 className="text-lg font-bold text-gray-900">Erro ao carregar tendências</h2>
          <p className="text-sm text-gray-500">{error}</p>
          <button onClick={fetchData} className="mx-auto inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm">
            <RefreshCw className="w-4 h-4" /> Tentar novamente
          </button>
        </div>
      </div>
    );
  }

  const subidas: TendCard[] = data.subidas || [];
  const quedas: TendCard[] = data.quedas || [];

  return (
    <div className="min-h-screen bg-slate-50 pb-12">
      <NavBar />
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-indigo-600" />
              Tendência — próxima semana
            </h1>
            <p className="text-xs text-gray-400 mt-0.5">
              Previsão do modelo com base no histórico de preços (TCGCSV), em USD
            </p>
          </div>
          <button onClick={fetchData} className="p-2 hover:bg-gray-100 rounded-lg" title="Atualizar">
            <RefreshCw className="w-4 h-4 text-gray-500" />
          </button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-6 space-y-8">
        {data.gerado_em && (
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <Calendar className="w-3.5 h-3.5" />
            Previsto em {new Date(data.gerado_em).toLocaleString('pt-BR')} ·{' '}
            {data.total} cartas na faixa de preço analisada (${2}–${150}, |tend|≥3%)
          </div>
        )}

        <div className="grid md:grid-cols-2 gap-6">
          <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100 bg-emerald-50/50">
              <TrendingUp className="w-4 h-4 text-emerald-600" />
              <h2 className="text-sm font-bold text-gray-800">Subidas previstas</h2>
              <span className="ml-auto text-xs text-gray-400">{subidas.length} cartas</span>
            </div>
            <div className="px-3 py-2">
              {subidas.length === 0 && <p className="text-sm text-gray-400 py-4 text-center">Sem dados</p>}
              {subidas.map((c) => <RowTendencia key={c.card_id} c={c} dir="up" />)}
            </div>
          </section>

          <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100 bg-red-50/50">
              <TrendingDown className="w-4 h-4 text-red-600" />
              <h2 className="text-sm font-bold text-gray-800">Quedas previstas</h2>
              <span className="ml-auto text-xs text-gray-400">{quedas.length} cartas</span>
            </div>
            <div className="px-3 py-2">
              {quedas.length === 0 && <p className="text-sm text-gray-400 py-4 text-center">Sem dados</p>}
              {quedas.map((c) => <RowTendencia key={c.card_id} c={c} dir="down" />)}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}