'use client';
/** /minha-colecao — coleção pessoal local (P2.37).
 * Lê localStorage, resolve preços via lookupCard ({idE}-{num}) e mostra
 * valor estimado (preço justo modelo) vs real (mercado escorado) + upside.
 * Suporta ajuste de quantidade, remoção, e exportar/importar JSON. */

import { useState, useEffect, useMemo } from 'react';
import { Link as LinkIcon, Download, Upload, Trash2, Heart, Package, AlertTriangle } from 'lucide-react';
import Image from 'next/image';

import NavBar from '@/app/components/NavBar';
import { getBasePath } from '@/app/lib/basePath';
import { lookupCard } from '@/app/lib/cardLookup';
import {
  listarColecao, totalCartas, setQtd, removeCarta, limparColecao,
  importarColecao, exportarJSON, calcularValor, type ColecaoMap,
} from '@/app/lib/colecao';

interface PrecoItem { real?: number | null; estimado?: number | null }

export default function MinhaColecaoPage() {
  const [map, setMap] = useState<ColecaoMap>({});
  const [precos, setPrecos] = useState<Record<string, PrecoItem>>({});
  const [loaded, setLoaded] = useState(false);
  const [carregandoPrecos, setCarregandoPrecos] = useState(false);

  // carrega a coleção do localStorage
  useEffect(() => {
    try {
      if (typeof window !== 'undefined') {
        const raw = window.localStorage.getItem('pokescan.colecao');
        setMap(raw ? JSON.parse(raw) : {});
      }
    } catch { /* ignore */ }
    setLoaded(true);
  }, []);

  const itens = useMemo(() => listarColecao(map), [map]);

  // resolve preços (batch)
  useEffect(() => {
    if (!loaded || itens.length === 0) return;
    let ativo = true;
    setCarregandoPrecos(true);
    (async () => {
      const res: Record<string, PrecoItem> = {};
      for (const it of itens) {
        try {
          // Resolve pelo id real {s}-{num} (chave do cards.json) — funciona p/
          // EN (sv3pt5-4) e liga_only (246-14). card_id é redundante/ambíguo p/ EN.
          const card = await lookupCard({ set: it.s, num: it.num });
          if (card) {
            const real = card.modelo?.real ?? null;
            const estimado = card.modelo?.pred ?? (card.preco_brl as number) ?? null;
            res[it.id] = { real, estimado };
          }
        } catch { /* segue */ }
        if (!ativo) return;
      }
      if (ativo) { setPrecos(res); setCarregandoPrecos(false); }
    })();
    return () => { ativo = false; };
  }, [loaded, itens, map]);

  const valor = useMemo(() => calcularValor(itens, (id) => precos[id] || null), [itens, precos]);

  // exportar / importar
  const onExport = () => {
    const blob = new Blob([exportarJSON(map)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'pokescan-colecao.json'; a.click();
    URL.revokeObjectURL(url);
  };
  const onImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const parsed = JSON.parse(String(reader.result));
        setMap(importarColecao(parsed));
        setPrecos({});
      } catch { alert('JSON inválido'); }
    };
    reader.readAsText(f);
  };

  if (!loaded) {
    return <div className="min-h-screen bg-[#fbf4e6]"><NavBar /><div className="max-w-5xl mx-auto p-6 text-[#6b6252]">Carregando…</div></div>;
  }

  return (
    <div className="min-h-screen bg-[#fbf4e6]">
      <NavBar />
      <main className="max-w-5xl mx-auto px-4 py-8">
        <header className="flex items-center justify-between flex-wrap gap-3 mb-6">
          <div>
            <h1 className="text-3xl font-bold text-[#292318] flex items-center gap-2">
              <Heart className="text-[#d40b2e]" /> Minha coleção
            </h1>
            <p className="text-[#6b6252] mt-1">
              {totalCartas(map)} carta{totalCartas(map) !== 1 ? 's' : ''} salva{totalCartas(map) !== 1 ? 's' : ''} · guardada localmente neste navegador
            </p>
          </div>
          <div className="flex gap-2">
            <button onClick={onExport} className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-2 rounded-lg border-2 border-[#2b2517]/20 bg-[#fffdf7] text-[#292318] hover:border-[#d40b2e]/40 transition-colors">
              <Download className="w-3.5 h-3.5" /> Exportar
            </button>
            <label className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-2 rounded-lg border-2 border-[#2b2517]/20 bg-[#fffdf7] text-[#292318] hover:border-[#d40b2e]/40 transition-colors cursor-pointer">
              <Upload className="w-3.5 h-3.5" /> Importar
              <input type="file" accept="application/json" className="hidden" onChange={onImport} />
            </label>
            {itens.length > 0 && (
              <button onClick={() => setMap(limparColecao())} className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-2 rounded-lg border-2 border-[#d40b2e]/30 text-[#a90924] hover:bg-[#d40b2e]/10 transition-colors">
                <Trash2 className="w-3.5 h-3.5" /> Limpar
              </button>
            )}
          </div>
        </header>

        {itens.length === 0 ? (
          <div className="flex flex-col items-center justify-center min-h-[300px] border border-[#2b2517]/15 rounded-2xl bg-[#fffdf7] text-center p-8">
            <Package className="w-12 h-12 text-[#d40b2e]/40 mb-4" />
            <h2 className="text-lg font-semibold text-[#292318]">Sua coleção está vazia</h2>
            <p className="text-[#6b6252] mt-1 max-w-md">
              Use <span className="font-semibold text-[#d40b2e]">Tenho esta carta</span> na página de qualquer carta ou no scanner
              para ir montando sua coleção. O valor estimado vs real aparece aqui.
            </p>
          </div>
        ) : (
          <>
            {/* Totais */}
            <section className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
              <div className="bg-[#292318] text-white rounded-2xl p-5 shadow-sm">
                <p className="text-xs uppercase tracking-wide text-[#f3e9d2]/60 mb-1">Valor real (mercado)</p>
                <p className="text-2xl font-black">R$ {valor.real.toFixed(2)}</p>
                <p className="text-xs text-[#f3e9d2]/60 mt-1">{valor.nComPreco} de {valor.nTotal} cartas com preço</p>
              </div>
              <div className="bg-[#fffdf7] rounded-2xl p-5 border border-[#2b2517]/20 shadow-sm">
                <p className="text-xs uppercase tracking-wide text-[#6b6252] mb-1">Valor estimado (preço justo)</p>
                <p className="text-2xl font-black text-[#a90924]">R$ {valor.estimado.toFixed(2)}</p>
                <p className="text-xs text-[#6b6252] mt-1">modelo de preço justo</p>
              </div>
              <div className="bg-[#fffdf7] rounded-2xl p-5 border border-[#2b2517]/20 shadow-sm">
                <p className="text-xs uppercase tracking-wide text-[#6b6252] mb-1">Upside potencial</p>
                <p className={`text-2xl font-black ${valor.upsidePct >= 0 ? 'text-emerald-600' : 'text-[#a90924]'}`}>
                  {valor.upsidePct >= 0 ? '+' : ''}{valor.upsidePct.toFixed(0)}%
                </p>
                <p className="text-xs text-[#6b6252] mt-1">estimado vs real</p>
              </div>
            </section>

            {carregandoPrecos && (
              <p className="text-xs text-[#6b6252] mb-3 animate-pulse">Resolvendo preços…</p>
            )}

            {/* Lista */}
            <section className="space-y-2">
              {itens.map((it) => {
                const p = precos[it.id];
                const real = p?.real != null ? p.real : null;
                const est = p?.estimado != null ? p.estimado : null;
                return (
                  <div key={it.id} className="flex items-center gap-4 bg-[#fffdf7] rounded-xl p-3 border border-[#2b2517]/15 hover:border-[#d40b2e]/30 transition-colors">
                    <div className="relative w-14 h-20 bg-[#f3e9d2] rounded-lg overflow-hidden shrink-0">
                      {it.img ? <Image src={it.img} alt={it.nome} fill className="object-contain" unoptimized /> : <Package className="w-6 h-6 text-gray-300 absolute inset-0 m-auto" />}
                    </div>
                    <div className="min-w-0 flex-1">
                      <a href={`${getBasePath()}/card/?set=${encodeURIComponent(it.s || '')}&num=${encodeURIComponent(it.num || '')}&nome=${encodeURIComponent(it.nome)}`} className="font-semibold text-[#292318] hover:text-[#d40b2e] truncate block">
                        {it.nome}
                      </a>
                      <div className="flex flex-wrap gap-3 mt-0.5 text-sm">
                        {real != null && <span className="text-[#292318]">Real <b>R$ {real.toFixed(2)}</b></span>}
                        {est != null && <span className="text-[#a90924]">Estimado <b>R$ {est.toFixed(2)}</b></span>}
                        {real != null && est != null && (
                          <span className={`text-xs font-semibold ${est >= real ? 'text-emerald-600' : 'text-[#a90924]'}`}>
                            {((est - real) / real * 100).toFixed(0)}%
                          </span>
                        )}
                        {real == null && est == null && <span className="text-xs text-[#998f7c]">sem preço</span>}
                      </div>
                    </div>
                    {/* quantidade */}
                    <div className="flex items-center gap-1 shrink-0 bg-[#f3e9d2] rounded-lg px-1">
                      <button onClick={() => setMap(setQtd(it.id, (it.qtd || 1) - 1))} className="w-7 h-7 text-[#292318] hover:text-[#d40b2e]">−</button>
                      <span className="w-7 text-center font-bold text-sm">{it.qtd || 1}</span>
                      <button onClick={() => setMap(setQtd(it.id, (it.qtd || 1) + 1))} className="w-7 h-7 text-[#292318] hover:text-[#d40b2e]">+</button>
                    </div>
                    <a href={`${getBasePath()}/card/?set=${encodeURIComponent(it.s || '')}&num=${encodeURIComponent(it.num || '')}&nome=${encodeURIComponent(it.nome)}`} title="Ver detalhes" className="text-[#d40b2e] hover:text-[#a90924] shrink-0">
                      <LinkIcon className="w-4 h-4" />
                    </a>
                    <button onClick={() => setMap(removeCarta(it.id))} title="Remover" className="text-[#998f7c] hover:text-[#a90924] shrink-0">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                );
              })}
            </section>
          </>
        )}
      </main>
    </div>
  );
}