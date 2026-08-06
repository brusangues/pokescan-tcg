'use client';

import { useEffect, useState } from 'react';
import { lookupHistorico } from '@/app/lib/cardLookup';

interface Ponto {
  data: string;
  real: number;
  pred: number | null;
  moeda: string;
  tipo: string;
}

interface PriceHistoryProps {
  ligaId?: string;
  nome?: string;
  sigla?: string;
  moeda?: string;
}

/**
 * Gráfico de evolução de preço (real vs predito) da carta.
 * Busca /data/historico.json (via lookupHistorico) e desenha um line chart
 * em SVG puro (sem lib).
 */
export default function PriceHistory({ ligaId, nome, sigla, moeda }: PriceHistoryProps) {
  const [serie, setSerie] = useState<Ponto[] | null>(null);
  const [erro, setErro] = useState(false);

  useEffect(() => {
    if (!ligaId && !nome) return;

    lookupHistorico({ ligaId, nome, sigla })
      .then(d => {
        setSerie(d.serie && d.serie.length >= 2 ? d.serie : null);
      })
      .catch(() => setErro(true));
  }, [ligaId, nome, sigla]);

  if (erro) return null;
  if (!serie) {
    return (
      <p className="text-xs text-gray-400 py-2">
        {ligaId || nome ? 'Carregando histórico…' : 'Sem histórico disponível para esta carta.'}
      </p>
    );
  }

  const W = 560;
  const H = 180;
  const PAD = { top: 16, right: 14, bottom: 28, left: 52 };

  const precos = serie.flatMap(p => [p.real, p.pred ?? null]).filter((v): v is number => v !== null);
  let min = Math.min(...precos);
  let max = Math.max(...precos);
  if (min === max) { min -= 1; max += 1; }
  const range = max - min;

  const x = (i: number) => PAD.left + (i / (serie.length - 1)) * (W - PAD.left - PAD.right);
  const y = (v: number) => PAD.top + (1 - (v - min) / range) * (H - PAD.top - PAD.bottom);

  const pathReal = serie.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p.real).toFixed(1)}`).join(' ');
  const predPontos = serie.filter(p => p.pred !== null);
  const pathPred = predPontos.map((p, i) => {
    const j = serie.indexOf(p);
    return `${i === 0 ? 'M' : 'L'}${x(j).toFixed(1)},${y(p.pred as number).toFixed(1)}`;
  }).join(' ');

  const fmt = (v: number) => v.toLocaleString('pt-BR', { maximumFractionDigits: 0 });
  const moedaS = moeda || serie[0].moeda || 'R$';
  const ultimo = serie[serie.length - 1];
  const primeiro = serie[0];
  const varPct = primeiro.real > 0 ? ((ultimo.real - primeiro.real) / primeiro.real) * 100 : 0;

  // Rótulos de data (máx 5)
  const step = Math.ceil(serie.length / 5);
  const labels = serie.filter((_, i) => i % step === 0 || i === serie.length - 1);

  return (
    <div className="mt-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-bold text-gray-900">Evolução de Preço</h3>
        <span className={`text-xs font-semibold ${varPct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
          {varPct >= 0 ? '+' : ''}{varPct.toFixed(0)}% no período
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="Evolução de preço da carta">
        {/* Grid */}
        {[0.25, 0.5, 0.75].map(f => {
          const yv = PAD.top + (1 - f) * (H - PAD.top - PAD.bottom);
          const val = min + f * range;
          return (
            <g key={f}>
              <line x1={PAD.left} y1={yv} x2={W - PAD.right} y2={yv} stroke="#f0f0f0" strokeWidth={1} />
              <text x={PAD.left - 6} y={yv + 3} textAnchor="end" fontSize={9} fill="#9ca3af">
                {fmt(val)}
              </text>
            </g>
          );
        })}

        {/* Série predita (tracejada) */}
        {predPontos.length >= 2 && (
          <path d={pathPred} fill="none" stroke="#818cf8" strokeWidth={1.8} strokeDasharray="5 4" />
        )}
        {/* Série real */}
        <path d={pathReal} fill="none" stroke="#10b981" strokeWidth={2.4} strokeLinejoin="round" />

        {/* Pontos + rótulos de data */}
        {serie.map((p, i) => (
          <g key={i}>
            <circle cx={x(i)} cy={y(p.real)} r={3} fill="#10b981" />
            {(i % step === 0 || i === serie.length - 1) && (
              <text x={x(i)} y={H - 8} textAnchor="middle" fontSize={9} fill="#9ca3af">
                {p.data.slice(5)} {/* MM-DD */}
              </text>
            )}
          </g>
        ))}

        {/* Tooltip-like: último valor */}
        <circle cx={x(serie.length - 1)} cy={y(ultimo.real)} r={4} fill="#059669" stroke="white" strokeWidth={1.5} />
      </svg>

      {/* Legenda */}
      <div className="flex items-center gap-4 mt-2 text-[11px] text-gray-500">
        <span className="inline-flex items-center gap-1.5">
          <span className="w-3 h-0.5 bg-emerald-500 inline-block rounded" /> Preço real ({moedaS})
        </span>
        {predPontos.length >= 2 && (
          <span className="inline-flex items-center gap-1.5">
            <span className="w-3 h-0.5 bg-indigo-400 inline-block rounded" style={{ borderTop: '2px dashed #818cf8', background: 'transparent' }} />
            Preço justo (modelo)
          </span>
        )}
        <span className="ml-auto text-gray-400">{serie.length} pontos · hits diários + snapshots</span>
      </div>
    </div>
  );
}
