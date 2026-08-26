'use client';

import { TrendingUp, TrendingDown, ExternalLink } from 'lucide-react';
import { cardLink, ligaLink } from '@/app/lib/cards';

export interface ScoredCardRowData {
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
  card_id?: string;
}

/**
 * Linha padrão de tabela para cartas escoradas (hits e snapshot).
 * Colunas: Nome (link para /card) | Set (sigla + nome, link Liga) | Real | Pred | Upside | iCO | Status
 */
export default function ScoredCardRow({ card }: { card: ScoredCardRowData }) {
  const real = Number(card.real) || 0;
  const pred = Number(card.pred) || 0;
  const upside = Number(card.upside) || 0;
  const ico = Number(card.iCO) || 0;
  const isUp = upside > 0;
  const isSub = card.oportunidade === '🔥 Subvalorizada';
  const isInfla = card.oportunidade === '💀 Inflacionada';

  const ligaUrl = ligaLink({
    nEN: card.nEN,
    sSigla: card.sigla,
    sNumber: card.sNumber,
    num: card.num,
  });

  return (
    <div className={`flex items-center gap-2 px-4 py-2.5 border-b border-[#2b2517]/15 last:border-0 hover:bg-[#f3e9d2] transition-colors ${isSub ? 'bg-green-50/30' : isInfla ? 'bg-red-50/30' : ''}`}>
      {/* Nome */}
      <div className="flex-1 min-w-0">
        {/* <a> com href já prefixado por cardLink (getBasePath) — o next/link
            duplica o basePath em hrefs com query no client */}
        <a
          href={cardLink({ card_id: card.card_id, nome_en: card.nEN || card.nome, sSigla: card.sigla })}
          className="text-sm font-semibold text-[#d40b2e] hover:text-indigo-800 hover:underline truncate block"
        >
          {card.nome}
        </a>
        {/* Set: sigla + nome completo + link Liga */}
        <div className="flex items-center gap-1.5 mt-0.5 min-w-0">
          <span className="text-[10px] font-mono bg-[#f3e9d2] px-1.5 py-0.5 rounded text-[#6b6252] shrink-0">
            {card.sigla}
          </span>
          {card.setNome && (
            <span className="text-[11px] text-[#998f7c] truncate">{card.setNome}</span>
          )}
          {ligaUrl && (
            <a
              href={ligaUrl}
              target="_blank"
              rel="noopener noreferrer"
              title={`Ver ${card.nome} na Liga Pokémon`}
              className="text-[10px] text-blue-500 hover:text-blue-700 shrink-0 inline-flex items-center gap-0.5"
            >
              <ExternalLink className="w-3 h-3" />
              Liga
            </a>
          )}
        </div>
      </div>

      {/* Real */}
      <div className="text-right shrink-0 w-20">
        <p className="text-sm font-bold text-[#292318]">{card.moeda}{real.toFixed(2)}</p>
      </div>

      {/* Pred */}
      <div className="text-right shrink-0 w-20">
        <p className="text-sm text-[#6b6252]">{card.moeda}{pred.toFixed(2)}</p>
      </div>

      {/* Upside */}
      <div className="text-right shrink-0 w-20">
        <span className={`inline-flex items-center gap-1 text-xs font-bold px-2 py-1 rounded-full ${isUp ? 'text-green-700 bg-green-100' : 'text-red-700 bg-red-100'}`}>
          {isUp ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
          {isUp ? '+' : ''}{upside.toFixed(0)}%
        </span>
      </div>

      {/* iCO */}
      <div className="text-right shrink-0 w-10">
        {ico > 0 ? (
          <span className="text-[11px] font-medium text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">{ico}</span>
        ) : (
          <span className="text-[11px] text-gray-300">—</span>
        )}
      </div>

      {/* Status */}
      <div className="shrink-0 w-24 text-right">
        <span className={`text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full ${isSub ? 'text-green-700 bg-green-100' : isInfla ? 'text-red-700 bg-red-100' : 'text-[#6b6252] bg-[#f3e9d2]'}`}>
          {card.oportunidade.replace('🔥 ', '').replace('💀 ', '')}
        </span>
      </div>
    </div>
  );
}