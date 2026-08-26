'use client';

import { useState, useEffect } from 'react';
import {
  History, FlaskConical, RefreshCw, AlertCircle,
  Trophy, TrendingUp, X, Check, GitBranch,
} from 'lucide-react';
import { getBasePath } from '@/app/lib/basePath';
import NavBar from '@/app/components/NavBar';

type Commit = {
  hash: string;
  date: string;
  author: string;
  subject: string;
  type: string;
  scope: string | null;
};

type Ablation = {
  label: string;
  modelo: string;
  agregacao: string;
  pca: number | null;
  mae: number;
  r2: number;
  n_train: number;
  n_test: number;
};

const TYPE_STYLE: Record<string, string> = {
  feat: 'bg-emerald-100 text-emerald-700',
  fix: 'bg-red-100 text-red-700',
  docs: 'bg-sky-100 text-sky-700',
  refactor: 'bg-amber-100 text-amber-700',
  perf: 'bg-violet-100 text-violet-700',
  other: 'bg-[#f3e9d2] text-[#6b6252]',
};

const MODEL_LABEL: Record<string, string> = {
  small: 'DINOv2-small',
  base: 'DINOv2-base',
  large: 'DINOv2-large',
};

const AGG_LABEL: Record<string, string> = {
  cls: 'CLS token',
  mean: 'Mean pool',
  'cls+mean': 'CLS + Mean',
};

function fmtData(iso: string) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' }) +
    ' ' + d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

export default function ChangelogPage() {
  const [commits, setCommits] = useState<Commit[] | null>(null);
  const [ablations, setAblations] = useState<Ablation[] | null>(null);
  const [melhor, setMelhor] = useState<Ablation | null>(null);
  const [erro, setErro] = useState('');
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setErro('');
    try {
      const res = await fetch(`${getBasePath()}/data/changelog.json`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setCommits(data.commits || []);
      setAblations(data.ablations || []);
      setMelhor(data.melhor || null);
    } catch (e: any) {
      setErro(e.message || 'Falha ao carregar changelog');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <div className="min-h-screen bg-[#fbf4e6]">
      <NavBar />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center gap-3 mb-2">
        <div className="w-10 h-10 bg-[#d40b2e] rounded-xl flex items-center justify-center text-white shadow-sm">
          <History className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-[#292318]">Changelog</h1>
          <p className="text-sm text-[#6b6252]">Histórico de commits e experimentos do modelo</p>
        </div>
      </div>

      <div className="flex gap-2 mt-4 mb-6">
        <button
          onClick={load}
          disabled={loading}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium bg-[#f3e9d2] text-[#292318] hover:bg-[#ece0c8] disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Atualizar
        </button>
      </div>

      {erro && (
        <div className="flex items-center gap-2 bg-red-50 text-red-700 text-sm px-4 py-3 rounded-xl mb-6">
          <AlertCircle className="w-4 h-4 shrink-0" /> {erro}
        </div>
      )}

      {loading && commits === null ? (
        <div className="text-center py-16 text-[#998f7c]">Carregando changelog...</div>
      ) : (
        <>
          {/* ── Ablações ── */}
          <section className="mb-10">
            <div className="flex items-center gap-2 mb-4">
              <FlaskConical className="w-5 h-5 text-violet-600" />
              <h2 className="text-lg font-semibold text-[#292318]">Ablações de embeddings</h2>
              <span className="text-xs text-[#998f7c]">({ablations?.length ?? 0} configs · split temporal)</span>
            </div>

            {melhor && (
              <div className="flex items-center gap-3 bg-gradient-to-r from-amber-50 to-yellow-50 border border-amber-200 rounded-xl px-4 py-3 mb-4">
                <Trophy className="w-5 h-5 text-amber-500 shrink-0" />
                <div className="text-sm">
                  <span className="font-semibold text-[#292318]">Melhor config:</span>{' '}
                  <span className="font-medium">{melhor.modelo === 'base' ? 'DINOv2-base' : melhor.modelo === 'large' ? 'DINOv2-large' : 'DINOv2-small'} · {AGG_LABEL[melhor.agregacao] || melhor.agregacao} · PCA{melhor.pca}</span>
                  <span className="text-[#6b6252]"> — R² {melhor.r2.toFixed(4)} · MAE ${melhor.mae.toFixed(2)}</span>
                </div>
              </div>
            )}

            <div className="bg-[#fffdf7] rounded-2xl shadow-sm border border-[#2b2517]/20 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-[#f3e9d2] border-b border-[#2b2517]/20 text-left text-xs uppercase tracking-wider text-[#6b6252]">
                      <th className="px-4 py-2.5">Configuração</th>
                      <th className="px-4 py-2.5 text-right">MAE</th>
                      <th className="px-4 py-2.5 text-right">R²</th>
                      <th className="px-4 py-2.5 text-right">Treino</th>
                      <th className="px-4 py-2.5 text-right">Teste</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ablations?.map((a, i) => {
                      const isBest = melhor && a.label === melhor.label;
                      return (
                        <tr key={a.label} className={`border-b border-[#2b2517]/15 last:border-0 ${isBest ? 'bg-amber-50/60' : i % 2 ? 'bg-[#f3e9d2]/40' : ''}`}>
                          <td className="px-4 py-2.5">
                            <div className="flex items-center gap-2">
                              {isBest && <Trophy className="w-3.5 h-3.5 text-amber-500 shrink-0" />}
                              <span className="font-medium text-[#292318]">
                                {MODEL_LABEL[a.modelo] || a.modelo}
                              </span>
                              <span className="text-[#998f7c]">·</span>
                              <span>{AGG_LABEL[a.agregacao] || a.agregacao}</span>
                              <span className="text-[#998f7c]">·</span>
                              <span className="text-[#6b6252]">PCA{a.pca}</span>
                            </div>
                          </td>
                          <td className="px-4 py-2.5 text-right font-mono text-[#292318]">${a.mae.toFixed(2)}</td>
                          <td className="px-4 py-2.5 text-right font-mono font-semibold text-[#292318]">{a.r2.toFixed(4)}</td>
                          <td className="px-4 py-2.5 text-right text-[#6b6252]">{a.n_train.toLocaleString('pt-BR')}</td>
                          <td className="px-4 py-2.5 text-right text-[#6b6252]">{a.n_test.toLocaleString('pt-BR')}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </section>

          {/* ── Commits ── */}
          <section>
            <div className="flex items-center gap-2 mb-4">
              <GitBranch className="w-5 h-5 text-[#d40b2e]" />
              <h2 className="text-lg font-semibold text-[#292318]">Histórico de commits</h2>
              <span className="text-xs text-[#998f7c]">({commits?.length ?? 0} recentes · branch hermes)</span>
            </div>

            <div className="bg-[#fffdf7] rounded-2xl shadow-sm border border-[#2b2517]/20 overflow-hidden">
              <ul className="divide-y divide-gray-100">
                {commits?.map(c => (
                  <li key={c.hash} className="px-4 py-3 flex items-start gap-3">
                    <span className="font-mono text-xs text-[#998f7c] mt-1 w-16 shrink-0">{c.hash}</span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-[#292318] font-medium leading-snug">{c.subject}</p>
                      <p className="text-xs text-[#998f7c] mt-0.5">{fmtData(c.date)} · {c.author}</p>
                    </div>
                    <span className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full shrink-0 mt-0.5 ${TYPE_STYLE[c.type] || TYPE_STYLE.other}`}>
                      {c.type}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </section>
        </>
      )}
      </div>
    </div>
  );
}
