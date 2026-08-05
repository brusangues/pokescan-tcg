'use client';

import { useEffect, useMemo, useState } from 'react';
import { Search, Database, Bug, ShieldAlert, RefreshCw } from 'lucide-react';

interface FeatureRow {
  id: string;
  name: string;
  set_id: string;
  set_name: string;
  label_usd?: number;
  label_brl?: number;
  pred_usd?: number;
  pred_brl?: number;
  [key: string]: any;
}

const FIXAS = ['id', 'name', 'set_id', 'set_name', 'release_year', 'label_usd', 'label_brl', 'pred_usd', 'pred_brl'];

export default function FeaturesPage() {
  const [rows, setRows] = useState<FeatureRow[]>([]);
  const [cols, setCols] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [geradoEm, setGeradoEm] = useState('');
  const [search, setSearch] = useState('');
  const [limit, setLimit] = useState(100);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [disabled, setDisabled] = useState(false);
  const [error, setError] = useState('');

  const fetchData = async (searchTerm = search, off = offset) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        limit: String(limit),
        offset: String(off),
      });
      if (searchTerm) params.set('search', searchTerm);
      const res = await fetch(`/api/features?${params}`);
      if (res.status === 404) {
        setDisabled(true);
        setLoading(false);
        return;
      }
      const data = await res.json();
      if (data.error) {
        setError(data.error);
      } else {
        setRows(data.rows);
        setCols(data.cols);
        setTotal(data.total);
        setGeradoEm(data.geradoEm);
        setDisabled(false);
        setError('');
      }
    } catch {
      setError('Erro ao carregar features');
    }
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  // Colunas de features (tudo que não é fixo)
  const featureCols = useMemo(() => cols.filter(c => !FIXAS.includes(c)), [cols]);

  const fmt = (v: any) => {
    if (v === null || v === undefined || v === '') return '—';
    const n = Number(v);
    if (Number.isNaN(n)) return String(v);
    return n.toLocaleString('pt-BR', { maximumFractionDigits: 2 });
  };

  if (disabled) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8 max-w-md text-center">
          <ShieldAlert className="w-10 h-10 text-amber-500 mx-auto mb-4" />
          <h1 className="text-lg font-bold text-gray-900">Página desabilitada</h1>
          <p className="text-sm text-gray-500 mt-2">
            Esta página de debug está desligada. Para habilitar em desenvolvimento,
            defina <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded">NEXT_PUBLIC_FEATURES=1</code>.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center gap-3 mb-1">
          <Bug className="w-6 h-6 text-indigo-600" />
          <h1 className="text-2xl font-bold text-gray-900">Features do Modelo</h1>
          <span className="text-[10px] font-semibold uppercase bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full ml-2">
            debug
          </span>
        </div>
        <p className="text-sm text-gray-500 mb-4">
          Últimas predições com todas as features usadas pelo CatBoost (USD + BRL) e labels reais.
        </p>

        {/* Barra de controles */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-4 flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[220px]">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') { setOffset(0); fetchData(search, 0); } }}
              placeholder="Buscar por nome, id ou set..."
              className="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <select
            value={limit}
            onChange={e => { setLimit(Number(e.target.value)); setOffset(0); fetchData(search, 0); }}
            className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white"
          >
            <option value={50}>50 linhas</option>
            <option value={100}>100 linhas</option>
            <option value={250}>250 linhas</option>
            <option value={500}>500 linhas</option>
          </select>
          <button
            onClick={() => { setOffset(0); fetchData(search, 0); }}
            className="inline-flex items-center gap-2 px-3 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700"
          >
            <RefreshCw className="w-4 h-4" /> Atualizar
          </button>
          <div className="text-xs text-gray-500 ml-auto">
            <Database className="w-3.5 h-3.5 inline mr-1" />
            {total} cartas {geradoEm && <>· gerado {new Date(geradoEm).toLocaleString('pt-BR')}</>}
          </div>
        </div>

        {error && <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-2 mb-4">{error}</p>}

        {/* Paginação */}
        <div className="flex items-center justify-between mb-2 text-sm">
          <span className="text-gray-500">
            Mostrando {offset + 1}–{Math.min(offset + rows.length, total)} de {total}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => { const o = Math.max(0, offset - limit); setOffset(o); fetchData(search, o); }}
              disabled={offset === 0}
              className="px-3 py-1.5 border border-gray-200 rounded-lg text-xs disabled:opacity-40 hover:bg-gray-50"
            >
              ← Anterior
            </button>
            <button
              onClick={() => { const o = offset + limit; setOffset(o); fetchData(search, o); }}
              disabled={offset + rows.length >= total}
              className="px-3 py-1.5 border border-gray-200 rounded-lg text-xs disabled:opacity-40 hover:bg-gray-50"
            >
              Próxima →
            </button>
          </div>
        </div>

        {/* Tabela */}
        {loading ? (
          <div className="flex items-center justify-center py-20 text-gray-400">
            <RefreshCw className="w-5 h-5 animate-spin mr-2" /> Carregando...
          </div>
        ) : (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            <div className="overflow-x-auto max-h-[70vh] overflow-y-auto">
              <table className="w-full text-xs whitespace-nowrap">
                <thead className="sticky top-0 bg-gray-50 text-gray-500 uppercase tracking-wide text-[10px]">
                  <tr>
                    <th className="px-3 py-2 text-left">Carta</th>
                    <th className="px-3 py-2 text-right">Label $</th>
                    <th className="px-3 py-2 text-right">Pred $</th>
                    <th className="px-3 py-2 text-right">Label R$</th>
                    <th className="px-3 py-2 text-right">Pred R$</th>
                    {featureCols.map(c => (
                      <th key={c} className="px-3 py-2 text-right font-mono">{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => {
                    const label = Number(r.label_usd);
                    const pred = Number(r.pred_usd);
                    const diff = !Number.isNaN(label) && !Number.isNaN(pred) && label > 0
                      ? ((pred - label) / label) * 100 : null;
                    return (
                      <tr key={`${r.id}-${i}`} className="border-t border-gray-100 hover:bg-indigo-50/30">
                        <td className="px-3 py-2">
                          <div className="font-semibold text-gray-800">{r.name}</div>
                          <div className="text-gray-400 font-mono text-[10px]">
                            {r.id} · {r.set_id}
                          </div>
                        </td>
                        <td className="px-3 py-2 text-right font-mono tabular-nums">
                          {fmt(r.label_usd)}
                        </td>
                        <td className="px-3 py-2 text-right font-mono tabular-nums">
                          {fmt(r.pred_usd)}
                        </td>
                        <td className="px-3 py-2 text-right font-mono tabular-nums">
                          {fmt(r.label_brl)}
                        </td>
                        <td className="px-3 py-2 text-right font-mono tabular-nums">
                          {fmt(r.pred_brl)}
                        </td>
                        {featureCols.map(c => (
                          <td key={c} className="px-3 py-2 text-right font-mono tabular-nums text-gray-600">
                            {fmt(r[c])}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
