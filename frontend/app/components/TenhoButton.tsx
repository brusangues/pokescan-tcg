'use client';
/** TenhoButton — marca/desmarca a carta na coleção local (P2.37).
 * Aparece no /card, no scanner (resultado de scan) e na busca textual.
 * Recebe só o essencial p/ montar o Item (id canônico + nome p/ exibir). */

import { useEffect, useState } from 'react';
import { Heart, HeartOff, Plus, Minus } from 'lucide-react';
import { addCarta, removeCarta, setQtd, type ColecaoMap } from '@/app/lib/colecao';

interface Props {
  id: string;                 // chave canônica {idE}-{num}
  nome: string;
  img?: string | null;
  s?: string;
  num?: string;
  /** estilo: 'card' (ficha, maior) | 'row' (compacto, listas) */
  variante?: 'card' | 'row';
}

export default function TenhoButton({ id, nome, img, s, num, variante = 'card' }: Props) {
  const [map, setMap] = useState<ColecaoMap>({});
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    try {
      if (typeof window !== 'undefined') {
        const raw = window.localStorage.getItem('pokescan.colecao');
        setMap(raw ? JSON.parse(raw) : {});
      }
    } catch { /* ignore */ }
    setLoaded(true);
  }, []);

  const item = map[id];
  const tenho = !!item;

  const onAdd = (e: React.MouseEvent) => {
    e.preventDefault(); e.stopPropagation();
    setMap(addCarta({ id, nome, img, s, num }));
  };
  const onRemove = (e: React.MouseEvent) => {
    e.preventDefault(); e.stopPropagation();
    setMap(removeCarta(id));
  };
  const onDelta = (e: React.MouseEvent, d: number) => {
    e.preventDefault(); e.stopPropagation();
    const nova = (item?.qtd || 1) + d;
    setMap(setQtd(id, nova));
  };

  if (!loaded) return null;

  if (variante === 'row') {
    return tenho ? (
      <div className="inline-flex items-center gap-1 bg-[#d40b2e]/10 text-[#a90924] border border-[#d40b2e]/30 rounded-full px-2 py-0.5 text-xs font-semibold">
        <button onClick={e => onRemove(e)} title="Remover" className="hover:text-[#d40b2e]">
          <HeartOff className="w-3.5 h-3.5" />
        </button>
        <span className="font-bold">{item!.qtd}</span>
        <button onClick={e => onDelta(e, -1)} title="-1" className="hover:text-[#d40b2e]"><Minus className="w-3 h-3" /></button>
        <button onClick={e => onDelta(e, +1)} title="+1" className="hover:text-[#d40b2e]"><Plus className="w-3 h-3" /></button>
      </div>
    ) : (
      <button
        onClick={onAdd}
        className="inline-flex items-center gap-1 text-xs font-semibold text-[#6b6252] hover:text-[#d40b2e] border border-[#d40b2e]/30 hover:border-[#d40b2e] rounded-full px-2 py-0.5 transition-colors"
        title="Adicionar à minha coleção"
      >
        <Heart className="w-3.5 h-3.5" /> Tenho
      </button>
    );
  }

  // variante 'card'
  return tenho ? (
    <div className="inline-flex items-center gap-2 bg-[#d40b2e]/10 text-[#a90924] border border-[#d40b2e]/40 rounded-xl px-3 py-1.5 font-semibold text-sm">
      <button onClick={e => onRemove(e)} title="Remover da coleção" className="hover:text-[#d40b2e]">
        <HeartOff className="w-4 h-4" />
      </button>
      <span className="font-black">{item!.qtd}</span>
      <button onClick={e => onDelta(e, -1)} className="hover:text-[#d40b2e]" title="diminuir"><Minus className="w-4 h-4" /></button>
      <button onClick={e => onDelta(e, +1)} className="hover:text-[#d40b2e]" title="aumentar"><Plus className="w-4 h-4" /></button>
      <span className="text-xs text-[#a90924] ml-1">na coleção</span>
    </div>
  ) : (
    <button
      onClick={onAdd}
      className="inline-flex items-center gap-1.5 bg-[#d40b2e] text-white font-semibold text-sm px-4 py-2 rounded-xl border-2 border-[#2b2517] shadow-[0_2px_0_0_rgba(43,37,23,0.8)] hover:bg-[#b50927] transition-colors"
      title="Adicionar à minha coleção"
    >
      <Heart className="w-4 h-4" /> Tenho esta carta
    </button>
  );
}