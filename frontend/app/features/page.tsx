'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  Bug, Search, RefreshCw, ShieldAlert, Database, ChevronDown, ChevronRight,
} from 'lucide-react';
import { getBasePath } from '../lib/basePath';

const FIXAS = [
  'id', 'name', 'set_id', 'set_name', 'release_year',
  'label_usd', 'label_brl', 'pred_usd', 'pred_brl',
];

interface FeatureRow {
  id: string;
  name: string;
  set_id: string;
  set_name: string;
  release_year: string;
  label_usd: string;
  label_brl: string;
  pred_usd: string;
  pred_brl: string;
  [key: string]: any;
}

interface ShapEntry {
  bias: number;
  top: { f: string; g: string; s: number; r: number }[];
}

export default function FeaturesPage() {
  const [rows, setRows] = useState<FeatureRow[]>([]);
  const [cols, setCols] = useState<string[]>([]);
  const [shap, setShap] = useState<Record<string, { usd: ShapEntry; brl: ShapEntry }>>({});
  const [geradoEm, setGeradoEm] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [limit, setLimit] = useState(100);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [shapAberto, setShapAberto] = useState<Record<string, boolean>>({});

  useEffect(() => {
    (async () => {
      try {
        const [fRes, sRes] = await Promise.all([
          fetch(`${getBasePath()}/data/features.json`),
          fetch(`${getBasePath()}/data/features_shap.json`),
        ]);
        const [fData, sData] = await Promise.all([fRes.json(), sRes.json()]);
        setRows(fData.rows || []);
        setCols(fData.cols || []);
        setGeradoEm(fData.geradoEm || null);
        setShap(sData || {});
      } catch (e) {
        console.error('Erro ao carregar features:', e);
        setError('Erro ao carregar features');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const featureCols = useMemo(() => cols.filter(c => !FIXAS.includes(c)), [cols]);

  // Busca client-side (nome, id, set) + paginação
  const filtradas = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(r =>
      (r.name || '').toLowerCase().includes(q) ||
      (r.id || '').toLowerCase().includes(q) ||
      (r.set_id || '').toLowerCase().includes(q) ||
      (r.set_name || '').toLowerCase().includes(q)
    );
  }, [rows, search]);

  const pagina = useMemo(() => filtradas.slice(offset, offset + limit), [filtradas, offset, limit]);
  const total = filtradas.length;

  const fmt = (v: any) => {
    if (v === null || v === undefined || v === '') return '—';
    const n = Number(v);
    if (Number.isNaN(n)) return String(v);
    return n.toLocaleString('pt-BR', { maximumFractionDigits: 2 });
  };
  const fmtR = (v: number) => `${v >= 0 ? '+' : '−'}R$ ${Math.abs(v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  // Barra de SHAP — contribuição da feature ao preço (BRL ou USD)
  const ShapBar = ({ t, moeda, max }: { t: { f: string; g: string; s: number; r: number }; moeda: string; max: number }) => {
    const pos = t.r >= 0;
    const w = Math.max(Math.abs(t.r) / Math.max(max, 0.01) * 100, 3);
    return (
      <div className="flex items-center gap-2 text-[10px]">
        <span className="w-40 truncate text-[#6b6252]" title={`${t.f} — ${t.g}`}>
          {t.f}
        </span>
        <div className="flex-1 h-3.5 bg-[#f3e9d2] rounded overflow-hidden">
          <div
            className={`h-full ${pos ? 'bg-green-500 ml-auto' : 'bg-red-500'}`}
            style={{ width: `${w}%`, float: pos ? 'right' : 'left' }}
          />
        </div>
        <span className={`w-20 text-right font-mono tabular-nums ${pos ? 'text-green-700' : 'text-red-700'}`}>
          {pos ? '+' : '−'}{moeda} {Math.abs(t.r).toFixed(2)}
        </span>
      </div>
    );
  };

  if (error && !loading) {
    return (
      <div className="min-h-screen bg-[#fbf4e6] flex items-center justify-center p-6">
        <div className="bg-[#fffdf7] rounded-2xl shadow-sm border border-[#2b2517]/20 p-8 max-w-md text-center">
          <ShieldAlert className="w-10 h-10 text-red-500 mx-auto mb-4" />
          <h1 className="text-lg font-bold text-[#292318]">Erro ao carregar</h1>
          <p className="text-sm text-[#6b6252] mt-2">{error}</p>
          <p className="text-xs text-[#998f7c] mt-2">Rode <code className="bg-[#f3e9d2] px-1 rounded">script/export_features.py</code> + <code className="bg-[#f3e9d2] px-1 rounded">script/shap_cartas.py</code> e o build.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#fbf4e6] p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center gap-3 mb-1">
          <Bug className="w-6 h-6 text-[#d40b2e]" />
          <h1 className="text-2xl font-bold text-[#292318]">Features do Modelo</h1>
          <span className="text-[10px] font-semibold uppercase bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full ml-2">
            debug
          </span>
        </div>
        <p className="text-sm text-[#6b6252] mb-4">
          Predições com todas as features (CatBoost USD + BRL), labels reais e <b>SHAP values</b> por carta
          (quanto cada feature puxa o preço para cima/baixo).
        </p>

        {/* Barra de controles */}
        <div className="bg-[#fffdf7] rounded-xl shadow-sm border border-[#2b2517]/20 p-4 mb-4 flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[220px]">
            <Search className="w-4 h-4 text-[#998f7c] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              value={search}
              onChange={e => { setSearch(e.target.value); setOffset(0); }}
              placeholder="Buscar por nome, id ou set..."
              className="w-full pl-9 pr-3 py-2 text-sm border border-[#2b2517]/20 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <select
            value={limit}
            onChange={e => { setLimit(Number(e.target.value)); setOffset(0); }}
            className="text-sm border border-[#2b2517]/20 rounded-lg px-3 py-2 bg-[#fffdf7]"
          >
            <option value={50}>50 linhas</option>
            <option value={100}>100 linhas</option>
            <option value={250}>250 linhas</option>
          </select>
          <button
            onClick={() => { setOffset(0); setShapAberto({}); }}
            className="inline-flex items-center gap-2 px-3 py-2 bg-[#d40b2e] text-white text-sm rounded-lg hover:bg-[#a90924]"
          >
            <RefreshCw className="w-4 h-4" /> Reiniciar
          </button>
          <div className="text-xs text-[#6b6252] ml-auto">
            <Database className="w-3.5 h-3.5 inline mr-1" />
            {total} cartas {geradoEm && <>· gerado {new Date(geradoEm).toLocaleString('pt-BR')}</>}
          </div>
        </div>

        {/* Paginação */}
        <div className="flex items-center justify-between mb-2 text-sm">
          <span className="text-[#6b6252]">
            Mostrando {total === 0 ? 0 : offset + 1}–{Math.min(offset + pagina.length, total)} de {total}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setOffset(Math.max(0, offset - limit))}
              disabled={offset === 0}
              className="px-3 py-1.5 border border-[#2b2517]/20 rounded-lg text-xs disabled:opacity-40 hover:bg-[#f3e9d2]"
            >
              ← Anterior
            </button>
            <button
              onClick={() => setOffset(offset + limit)}
              disabled={offset + pagina.length >= total}
              className="px-3 py-1.5 border border-[#2b2517]/20 rounded-lg text-xs disabled:opacity-40 hover:bg-[#f3e9d2]"
            >
              Próxima →
            </button>
          </div>
        </div>

        {/* Tabela */}
        {loading ? (
          <div className="flex items-center justify-center py-20 text-[#998f7c]">
            <RefreshCw className="w-5 h-5 animate-spin mr-2" /> Carregando...
          </div>
        ) : (
          <div className="bg-[#fffdf7] rounded-xl shadow-sm border border-[#2b2517]/20 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-xs whitespace-nowrap">
                <thead className="bg-[#f3e9d2] text-[#6b6252] uppercase tracking-wide text-[10px]">
                  <tr>
                    <th className="px-3 py-2 text-left">Carta</th>
                    <th className="px-3 py-2 text-right">Label R$</th>
                    <th className="px-3 py-2 text-right">Pred R$</th>
                    <th className="px-3 py-2 text-right">Label $</th>
                    <th className="px-3 py-2 text-right">Pred $</th>
                    <th className="px-3 py-2 text-left min-w-[340px]">SHAP (por que o preço é esse?)</th>
                    <th className="px-3 py-2 text-left min-w-[420px]">Features completas ({featureCols.length})</th>
                  </tr>
                </thead>
                <tbody>
                  {pagina.map((r, i) => {
                    const label = Number(r.label_usd);
                    const pred = Number(r.pred_usd);
                    const diff = !Number.isNaN(label) && !Number.isNaN(pred) && label > 0
                      ? ((pred - label) / label) * 100 : null;
                    const s = shap[r.id];
                    const topBrl = s?.brl?.top || [];
                    const maxR = Math.max(...topBrl.map(t => Math.abs(t.r)), 0.01);
                    const aberto = !!shapAberto[r.id];
                    return (
                      <tr key={`${r.id}-${i}`} className="border-t border-[#2b2517]/15 hover:bg-[#f3e9d2]/30 align-top">
                        <td className="px-3 py-2">
                          <div className="font-semibold text-[#292318]">{r.name}</div>
                          <div className="text-[#998f7c] font-mono text-[10px]">
                            {r.id} · {r.set_id}
                          </div>
                          {diff !== null && (
                            <div className={`text-[10px] font-mono mt-1 ${diff >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                              erro {diff >= 0 ? '+' : ''}{diff.toFixed(1)}%
                            </div>
                          )}
                        </td>
                        <td className="px-3 py-2 text-right font-mono tabular-nums">{fmt(r.label_brl)}</td>
                        <td className="px-3 py-2 text-right font-mono tabular-nums">{fmt(r.pred_brl)}</td>
                        <td className="px-3 py-2 text-right font-mono tabular-nums">{fmt(r.label_usd)}</td>
                        <td className="px-3 py-2 text-right font-mono tabular-nums">{fmt(r.pred_usd)}</td>
                        <td className="px-3 py-2">
                          {s ? (
                            <div className="space-y-1 py-1">
                              <div className="text-[10px] text-[#998f7c] font-mono">
                                base ≈ R$ {Math.expm1(s.brl.bias).toFixed(2)} · {topBrl.length} features mais influentes
                              </div>
                              {topBrl.map((t, j) => (
                                <ShapBar key={j} t={t} moeda="R$" max={maxR} />
                              ))}
                              <button
                                onClick={() => setShapAberto({ ...shapAberto, [r.id]: !aberto })}
                                className="text-[10px] text-[#d40b2e] hover:text-[#a90924] inline-flex items-center gap-0.5 mt-1"
                              >
                                {aberto ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                                SHAP em USD
                              </button>
                              {aberto && (
                                <div className="space-y-1 mt-1 pl-2 border-l-2 border-[#2b2517]/15">
                                  {s.usd.top.map((t, j) => (
                                    <ShapBar key={j} t={t} moeda="$" max={Math.max(...s.usd.top.map(x => Math.abs(x.r)), 0.01)} />
                                  ))}
                                </div>
                              )}
                            </div>
                          ) : (
                            <span className="text-gray-300 text-[10px]">sem SHAP</span>
                          )}
                        </td>
                        {/* Lista completa de features (à direita do SHAP) */}
                        <td className="px-3 py-2 align-top">
                          <div className="max-h-72 overflow-y-auto pr-1">
                            <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
                              {featureCols.map(c => (
                                <div key={c} className="flex justify-between gap-2 text-[10px]">
                                  <span className="text-[#998f7c] truncate" title={c}>{c}</span>
                                  <span className="font-mono text-[#292318] shrink-0">{fmt(r[c])}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        </td>
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
