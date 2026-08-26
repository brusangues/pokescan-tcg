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
    <div className="bg-[#fffdf7] rounded-2xl shadow-sm border border-[#2b2517]/20 overflow-hidden">
      {cards.length === 0 ? (
        <div className="px-6 py-12 text-center text-[#998f7c]">{emptyMessage}</div>
      ) : (
        /* Scroll horizontal (mobile): header + rows rolam juntos, como no /features */
        <div className="overflow-x-auto">
          <div className="min-w-[660px]">
            {/* Header */}
            <div className="flex items-center gap-2 px-4 py-2 bg-[#f3e9d2] border-b border-[#2b2517]/20 text-[11px] font-semibold text-[#6b6252] uppercase tracking-wide">
              <span className="flex-1">Carta</span>
              <span className="w-20 text-right">Real</span>
              <span className="w-20 text-right">Predito</span>
              <span className="w-20 text-right">Variação</span>
              <span className="w-10 text-right">iCO</span>
              <span className="w-24 text-right">Status</span>
            </div>

            {cards.map((card, i) => (
              <ScoredCardRow key={`${card.nome}-${card.sigla}-${i}`} card={card} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}