'use client';

import { useState, useEffect, useMemo } from 'react';
import { TrendingUp, TrendingDown, Minus, Info, Loader, AlertTriangle } from 'lucide-react';

import NavBar from '@/app/components/NavBar';
import { getBasePath } from '@/app/lib/basePath';

interface BucketInfo {
  media?: number;
  n?: number;
  '1em'?: number;
  contrib?: number;
  prob?: number;
}

interface SetEv {
  set: string;
  nome: string;
  ev: number;
  cobertura: number;
  breakdown: Record<string, BucketInfo>;
  booster_preco?: number | null;
  upside?: number | null;
  caixa?: { menor: number; medio: number; maior: number; tipo: string };
}

const BUCKET_LABEL: Record<string, string> = {
  dr: 'Double Rare (ex)',
  fa: 'Ultra Rare (FA)',
  ar: 'Illustration Rare',
  sir: 'Special Illustration Rare',
  hr: 'Hyper Rare (ouro)',
  filler: 'Comuns/Raras',
};

const RARITY_COLOR: Record<string, string> = {
  dr: 'text-slate-600',
  fa: 'text-amber-600',
  ar: 'text-rose-600',
  sir: 'text-purple-600',
  hr: 'text-yellow-600',
  filler: 'text-slate-400',
};

function fmt(v: number | undefined | null, dec = 2): string {
  if (v === undefined || v === null || isNaN(v)) return '—';
  return v.toLocaleString('pt-BR', { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

export default function ColecoesPage() {
  const [data, setData] = useState<SetEv[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [precoBooster, setPrecoBooster] = useState(15);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${getBasePath()}/data/ev_booster.json`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((j) => {
        setData(j);
        // default do slider = média dos preços de mercado disponíveis
        const precos = (j as SetEv[]).map((x) => x.booster_preco).filter((p): p is number => !!p);
        if (precos.length) setPrecoBooster(Math.round(precos.reduce((a, b) => a + b, 0) / precos.length));
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const rows = useMemo(() => {
    if (!data) return [];
    return data
      .map((r) => ({ ...r, upsideSlider: r.ev - precoBooster }))
      .sort((a, b) => b.upsideSlider - a.upsideSlider);
  }, [data, precoBooster]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50">
        <NavBar />
        <div className="flex items-center justify-center py-24 text-slate-400">
          <Loader className="animate-spin mr-2" size={20} /> Carregando coleções…
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <NavBar />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h1 className="text-2xl font-bold text-slate-800 mb-1">Coleções — EV do booster</h1>
        <p className="text-sm text-slate-500 mb-4">
          Valor esperado (R$) de um booster de cada coleção, calculado com os preços atuais da Liga
          (Σ probabilidade de pull × preço médio das cartas da raridade). Fonte das taxas: cronograma oficial de pull rates.
        </p>

        {/* Slider do preço do booster */}
        <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-semibold text-slate-700">
              Preço do booster (R$)
            </label>
            <span className="text-lg font-bold text-indigo-600 tabular-nums">R$ {fmt(precoBooster, 2)}</span>
          </div>
          <input
            type="range"
            min={1}
            max={100}
            step={0.5}
            value={precoBooster}
            onChange={(e) => setPrecoBooster(parseFloat(e.target.value))}
            className="w-full accent-indigo-600"
          />
          <div className="flex justify-between text-[11px] text-slate-400 mt-1">
            <span>R$ 1</span>
            <span>R$ 100</span>
          </div>
          <p className="text-xs text-slate-400 mt-2">
            Use o slider para simular o custo do booster — o ranking reordena pelo ganho esperado (EV − preço).
            O preço de mercado da Liga (caixa/36 ou avulso) aparece em cada linha como referência.
          </p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 mb-4 text-sm">
            Erro ao carregar: {error}
          </div>
        )}

        {/* Tabela */}
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-100 text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-3">Coleção</th>
                  <th className="px-3 py-3 text-right">EV/booster</th>
                  <th className="px-3 py-3 text-right">Mercado</th>
                  <th className="px-3 py-3 text-right">Upside (slider)</th>
                  <th className="px-3 py-3 text-center">Cobertura</th>
                  <th className="px-3 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const upside = r.upsideSlider;
                  const chip =
                    upside > 0.5 ? (
                      <span className="inline-flex items-center gap-1 text-emerald-600 font-semibold">
                        <TrendingUp size={14} /> +R$ {fmt(upside)}
                      </span>
                    ) : upside < -0.5 ? (
                      <span className="inline-flex items-center gap-1 text-red-500 font-medium">
                        <TrendingDown size={14} /> −R$ {fmt(Math.abs(upside))}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-slate-500">
                        <Minus size={14} /> ≈ equilibrado
                      </span>
                    );
                  const cov = r.cobertura ?? 0;
                  const covBadge =
                    cov >= 80 ? (
                      <span className="text-emerald-600 font-medium">{cov}%</span>
                    ) : cov >= 50 ? (
                      <span className="text-amber-600 font-medium">{cov}%</span>
                    ) : (
                      <span className="text-red-400 font-medium" title="Cobertura baixa — EV parcial">
                        {cov}%
                      </span>
                    );
                  return (
                    <tr
                      key={r.set}
                      className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer"
                      onClick={() => setExpanded(expanded === r.set ? null : r.set)}
                    >
                      <td className="px-4 py-3">
                        <div className="font-medium text-slate-800">{r.nome}</div>
                        <div className="text-xs text-slate-400 uppercase">{r.set}</div>
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums font-semibold text-slate-800">
                        R$ {fmt(r.ev)}
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums text-slate-500">
                        {r.booster_preco != null ? (
                          <>
                            R$ {fmt(r.booster_preco)}
                            <div className="text-[11px] text-slate-400">
                              {r.caixa?.tipo === 'caixa' ? `caixa/36 · ${r.caixa?.menor ? 'menor R$ ' + fmt(r.caixa.menor, 2) : ''}` : 'avulso'}
                            </div>
                          </>
                        ) : (
                          <span className="text-slate-300">—</span>
                        )}
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums">{chip}</td>
                      <td className="px-3 py-3 text-center">
                        {covBadge}
                        {cov < 50 && <AlertTriangle size={12} className="inline ml-1 text-red-400" />}
                      </td>
                      <td className="px-3 py-3 text-slate-300">
                        {expanded === r.set ? '▴' : '▾'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Linha expandida com breakdown */}
          {expanded && (
            <div className="border-t border-slate-100 bg-slate-50/60 px-4 py-4">
              <p className="text-xs text-slate-500 mb-2 flex items-center gap-1">
                <Info size={13} /> Contribuição esperada de cada raridade (probabilidade × preço médio):
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {(() => {
                  const r = rows.find((x) => x.set === expanded);
                  if (!r) return null;
                  return Object.entries(r.breakdown).map(([b, v]) => (
                    <div key={b} className="bg-white rounded-lg border border-slate-200 px-3 py-2">
                      <div className={`text-xs font-medium ${RARITY_COLOR[b] || 'text-slate-600'}`}>
                        {BUCKET_LABEL[b] || b}
                      </div>
                      <div className="text-sm font-semibold text-slate-800 tabular-nums">
                        R$ {fmt((v as BucketInfo).contrib)}
                      </div>
                      <div className="text-[11px] text-slate-400">
                        {(v as BucketInfo)['1em']
                          ? `1 em ${(v as BucketInfo)['1em']} · média R$ ${fmt((v as BucketInfo).media)}`
                          : `prob. ${((v as BucketInfo).prob ?? 0 * 100).toFixed(1)}% · média R$ ${fmt((v as BucketInfo).media)}`}
                      </div>
                    </div>
                  ));
                })()}
              </div>
            </div>
          )}
        </div>

        <p className="text-xs text-slate-400 mt-4">
          ⚠️ Coleções com cobertura &lt;50% têm o EV subestimado (faltam preços de cartas da Liga no snapshot) — trate
          o ranking delas com cautela. O EV usa o preço <strong>médio</strong> das cartas da raridade no set; o valor
          real por booster depende das cartas sorteadas.
        </p>
      </div>
    </div>
  );
}
