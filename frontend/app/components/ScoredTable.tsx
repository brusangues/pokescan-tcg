'use client';

import ScoredCardRow, { ScoredCardRowData } from './ScoredCardRow';

interface ScoredTableProps {
  cards: ScoredCardRowData[];
  emptyMessage?: string;
}

/**
 * Tabela padrão de cartas escoradas — usada em /hits e /snapshot.
 * Mesma estrutura de colunas e visual em ambas as páginas.
 */
export default function ScoredTable({ cards, emptyMessage = 'Nenhuma carta encontrada nessa categoria.' }: ScoredTableProps) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-2 bg-gray-50 border-b border-gray-200 text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
        <span className="flex-1">Carta</span>
        <span className="w-20 text-right hidden sm:block">Real</span>
        <span className="w-20 text-right hidden sm:block">Predito</span>
        <span className="w-20 text-right">Variação</span>
        <span className="w-10 text-right">iCO</span>
        <span className="w-24 text-right">Status</span>
      </div>

      {cards.length === 0 ? (
        <div className="px-6 py-12 text-center text-gray-400">{emptyMessage}</div>
      ) : (
        cards.map((card, i) => (
          <ScoredCardRow key={`${card.nome}-${card.sigla}-${i}`} card={card} />
        ))
      )}
    </div>
  );
}