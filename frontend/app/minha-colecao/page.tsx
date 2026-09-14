'use client';
/** /minha-colecao — coleção pessoal local (P2.37 + P2.43).
 * Lê localStorage, resolve preços via lookupCard ({idE}-{num}) e mostra
 * valor estimado (preço justo modelo) vs real (mercado escorado) + upside.
 * P2.43: cada UNIDADE tem condição e, se graduada, certificadora + escala —
 * o valor de mercado da unidade graduada vem dos ANÚNCIOS GRADUADOS da Liga
 * (campo `gr` do cards.json), nunca do preço da carta raw.
 * Suporta ajuste de quantidade, remoção, e exportar/importar JSON. */

import { useState, useEffect, useMemo } from 'react';
import {
  Link as LinkIcon, Download, Upload, Trash2, Heart, Package, ChevronDown, ChevronRight, Plus,
} from 'lucide-react';
import Image from 'next/image';

import NavBar from '@/app/components/NavBar';
import { getBasePath } from '@/app/lib/basePath';
import { lookupCard } from '@/app/lib/cardLookup';
import {
  listarColecao, totalCartas, totalGraduadas, setQtd, setUnidade, setCondicao,
  setGraduacao, addUnidade, removeUnidade, removeCarta, limparColecao,
  importarColecao, exportarJSON, calcularValor, type ColecaoMap,
} from '@/app/lib/colecao';
import {
  CONDICOES, EMPRESAS, IDIOMAS, TIPOS, rotuloTipo, unidadesDe, referenciaGraduada,
  referenciaCondicao, type Condicao, type Idioma, type Tipo,
} from '@/app/lib/grading';

interface PrecoItem {
  real?: number | null;
  estimado?: number | null;
  /** Bloco `v3m` da carta: vendas verificadas (v), preço por TIPO (n/f),
   * anúncios graduados (gr) e preço por CONDIÇÃO/TIPO dos anúncios (pc). */
  v3m?: {
    v?: number[];
    n?: number[];
    f?: number[];
    gr?: { n?: number; e?: [string, string, number][] } | null;
    pc?: Record<string, Record<string, number[]>> | null;
  } | null;
}

const brl = (v: number) =>
  'R$ ' + v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function MinhaColecaoPage() {
  const [map, setMap] = useState<ColecaoMap>({});
  const [precos, setPrecos] = useState<Record<string, PrecoItem>>({});
  const [loaded, setLoaded] = useState(false);
  const [carregandoPrecos, setCarregandoPrecos] = useState(false);
  const [aberto, setAberto] = useState<Record<string, boolean>>({});

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

  // resolve preços (batch) + bloco v3m da carta (vendas, por tipo, graduados,
  // preço por condição/tipo)
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
            res[it.id] = { real, estimado, v3m: (card.vendas_3m as PrecoItem['v3m']) || null };
          }
        } catch { /* segue */ }
        if (!ativo) return;
      }
      if (ativo) { setPrecos(res); setCarregandoPrecos(false); }
    })();
    return () => { ativo = false; };
  }, [loaded, itens, map]);

  /**
   * Referência de mercado de uma unidade GRADUADA: anúncios graduados da Liga,
   * priorizando mesma certificadora E mesma escala.
   */
  const gradRefDe = (id: string, empresa?: string | null, escala?: string | null): number | null => {
    const ref = referenciaGraduada(precos[id]?.v3m?.gr?.e, empresa, escala);
    return ref ? ref.mediana : null;
  };

  /**
   * Referência de mercado de uma unidade RAW: preço dos anúncios na MESMA
   * condição/tipo (`pc`); sem esse dado, preço de venda POR TIPO da carta
   * (`n`/`f`); sem nada disso, o mercado geral da carta (fallback do cálculo).
   */
  const condRefDe = (id: string, cond?: string | null, tipo?: string | null): number | null => {
    const v3m = precos[id]?.v3m;
    // Unidade sem condição/tipo declarados (coleção antiga) NÃO entra em balde
    // arbitrário: cai direto no mercado geral da carta.
    if (cond || tipo) {
      const fino = referenciaCondicao(v3m?.pc, cond, tipo);
      if (fino) return fino.mediana;
    }
    const arr = tipo === 'F' ? v3m?.f : tipo === 'N' ? v3m?.n : null;
    if (Array.isArray(arr) && typeof arr[1] === 'number' && arr[1] > 0) return arr[1];
    return null;
  };

  const valor = useMemo(
    () => calcularValor(itens, (id) => precos[id] || null, gradRefDe, condRefDe),
    [itens, precos]
  );

  const nGrad = totalGraduadas(map);

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

  const linkCarta = (it: { s?: string; num?: string; nome: string }) =>
    `${getBasePath()}/card/?set=${encodeURIComponent(it.s || '')}&num=${encodeURIComponent(it.num || '')}&nome=${encodeURIComponent(it.nome)}`;

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
              {totalCartas(map)} carta{totalCartas(map) !== 1 ? 's' : ''} salva{totalCartas(map) !== 1 ? 's' : ''}
              {nGrad > 0 ? ` · ${nGrad} graduada${nGrad !== 1 ? 's' : ''}` : ''}
              {' '}· guardada localmente neste navegador
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
              para ir montando sua coleção. Depois marque a condição e a graduação de cada unidade aqui.
            </p>
          </div>
        ) : (
          <>
            {/* Totais */}
            <section className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
              <div className="bg-[#292318] text-white rounded-2xl p-5 shadow-sm">
                <p className="text-xs uppercase tracking-wide text-[#f3e9d2]/60 mb-1">Valor real (mercado)</p>
                <p className="text-2xl font-black">{brl(valor.real)}</p>
                <p className="text-xs text-[#f3e9d2]/60 mt-1">
                  unidades sem graduação · {valor.nComPreco} de {valor.nTotal - valor.nGraduadas} com preço
                  {valor.nRefFina > 0 && <> · {valor.nRefFina} pela condição/tipo</>}
                </p>
              </div>
              <div className="bg-[#fffdf7] rounded-2xl p-5 border border-[#2b2517]/20 shadow-sm">
                <p className="text-xs uppercase tracking-wide text-[#6b6252] mb-1">Valor estimado (preço justo)</p>
                <p className="text-2xl font-black text-[#a90924]">{brl(valor.estimado)}</p>
                <p className="text-xs text-[#6b6252] mt-1">modelo de preço justo · unidades sem graduação</p>
              </div>
              <div className="bg-[#fffdf7] rounded-2xl p-5 border border-[#2b2517]/20 shadow-sm">
                <p className="text-xs uppercase tracking-wide text-[#6b6252] mb-1">Upside potencial</p>
                <p className={`text-2xl font-black ${valor.upsidePct >= 0 ? 'text-emerald-600' : 'text-[#a90924]'}`}>
                  {valor.upsidePct >= 0 ? '+' : ''}{valor.upsidePct.toFixed(0)}%
                </p>
                <p className="text-xs text-[#6b6252] mt-1">estimado vs real</p>
              </div>
            </section>

            {/* Valor graduado — separado do raw, por decisão de produto (P2.43) */}
            {valor.nGraduadas > 0 && (
              <section className="bg-[#fffdf7] rounded-2xl p-5 border-2 border-[#d40b2e]/25 shadow-sm mb-6">
                <div className="flex items-baseline justify-between flex-wrap gap-2">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-[#6b6252] mb-1">
                      Valor graduado (referência de mercado)
                    </p>
                    <p className="text-2xl font-black text-[#292318]">{brl(valor.realGraduado)}</p>
                  </div>
                  <span className="text-xs font-semibold text-[#292318] bg-[#f3e9d2] px-2.5 py-1 rounded-full">
                    {valor.nGraduadas} unidade{valor.nGraduadas !== 1 ? 's' : ''} graduada{valor.nGraduadas !== 1 ? 's' : ''}
                  </span>
                </div>
                <p className="text-xs text-[#6b6252] mt-2">
                  Mediana dos <b>anúncios de cartas já graduadas</b> na Liga Pokémon (oferta, não venda
                  concretizada), considerando a mesma certificadora e a mesma escala quando existem.
                  {valor.nSemRefGrad > 0 && (
                    <> {valor.nSemRefGrad} unidade{valor.nSemRefGrad !== 1 ? 's' : ''} sem anúncio graduado
                    publicado — não entram na soma.</>
                  )}
                </p>
              </section>
            )}

            {/* Custo declarado x referência de mercado (P2.44) */}
            {valor.nComPago > 0 && (
              <section className="bg-[#fffdf7] rounded-2xl p-5 border border-[#2b2517]/20 shadow-sm mb-6">
                <div className="flex items-baseline justify-between flex-wrap gap-2">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-[#6b6252] mb-1">Lucro sobre o que você pagou</p>
                    <p className={`text-2xl font-black ${valor.lucro >= 0 ? 'text-emerald-600' : 'text-[#a90924]'}`}>
                      {valor.lucro >= 0 ? '+' : ''}{brl(valor.lucro)}
                    </p>
                  </div>
                  <span className="text-xs font-semibold text-[#292318] bg-[#f3e9d2] px-2.5 py-1 rounded-full">
                    pagou {brl(valor.pago)} · {valor.nComPago} unidade{valor.nComPago !== 1 ? 's' : ''}
                  </span>
                </div>
                <p className="text-xs text-[#6b6252] mt-2">
                  Lucro = referência de mercado − o que você declarou ter pago, contando só as unidades
                  com preço <b>e</b> custo informados (unidade sem referência não entra).
                </p>
              </section>
            )}

            {carregandoPrecos && (
              <p className="text-xs text-[#6b6252] mb-3 animate-pulse">Resolvendo preços…</p>
            )}

            {/* Lista */}
            <section className="space-y-2">
              {itens.map((it) => {
                const p = precos[it.id];
                const real = p?.real != null ? p.real : null;
                const est = p?.estimado != null ? p.estimado : null;
                const unids = unidadesDe(it);
                const qtdGrad = unids.filter((u) => !!u.grad?.emp).length;
                const expandido = !!aberto[it.id];
                return (
                  <div key={it.id} className="bg-[#fffdf7] rounded-xl border border-[#2b2517]/15 hover:border-[#d40b2e]/30 transition-colors">
                    <div className="flex items-center gap-4 p-3">
                      <div className="relative w-14 h-20 bg-[#f3e9d2] rounded-lg overflow-hidden shrink-0">
                        {it.img ? <Image src={it.img} alt={it.nome} fill className="object-contain" unoptimized /> : <Package className="w-6 h-6 text-gray-300 absolute inset-0 m-auto" />}
                      </div>
                      <div className="min-w-0 flex-1">
                        <a href={linkCarta(it)} className="font-semibold text-[#292318] hover:text-[#d40b2e] truncate block">
                          {it.nome}
                        </a>
                        <div className="flex flex-wrap gap-3 mt-0.5 text-sm">
                          {real != null && <span className="text-[#292318]">Real <b>{brl(real)}</b></span>}
                          {est != null && <span className="text-[#a90924]">Estimado <b>{brl(est)}</b></span>}
                          {real != null && est != null && (
                            <span className={`text-xs font-semibold ${est >= real ? 'text-emerald-600' : 'text-[#a90924]'}`}>
                              {((est - real) / real * 100).toFixed(0)}%
                            </span>
                          )}
                          {real == null && est == null && <span className="text-xs text-[#998f7c]">sem preço</span>}
                          {qtdGrad > 0 && (
                            <span className="text-xs font-semibold text-[#292318] bg-[#f3e9d2] px-2 py-0.5 rounded-full">
                              {qtdGrad} graduada{qtdGrad !== 1 ? 's' : ''}
                            </span>
                          )}
                        </div>
                        <button
                          onClick={() => setAberto((a) => ({ ...a, [it.id]: !a[it.id] }))}
                          className="inline-flex items-center gap-1 mt-1 text-xs font-semibold text-[#d40b2e] hover:text-[#a90924]"
                        >
                          {expandido ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                          {expandido ? 'Ocultar unidades' : `Unidades e condição (${unids.length})`}
                        </button>
                      </div>
                      {/* quantidade */}
                      <div className="flex items-center gap-1 shrink-0 bg-[#f3e9d2] rounded-lg px-1">
                        <button onClick={() => setMap(setQtd(it.id, (it.qtd || 1) - 1))} className="w-7 h-7 text-[#292318] hover:text-[#d40b2e]">−</button>
                        <span className="w-7 text-center font-bold text-sm">{it.qtd || 1}</span>
                        <button onClick={() => setMap(setQtd(it.id, (it.qtd || 1) + 1))} className="w-7 h-7 text-[#292318] hover:text-[#d40b2e]">+</button>
                      </div>
                      <a href={linkCarta(it)} title="Ver detalhes" className="text-[#d40b2e] hover:text-[#a90924] shrink-0">
                        <LinkIcon className="w-4 h-4" />
                      </a>
                      <button onClick={() => setMap(removeCarta(it.id))} title="Remover" className="text-[#998f7c] hover:text-[#a90924] shrink-0">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>

                    {/* Unidades: condição + graduação */}
                    {expandido && (
                      <div className="px-3 pb-3 pt-2 border-t border-[#2b2517]/10">
                        <div className="space-y-1.5">
                          {unids.map((u, i) => {
                            const grad = !!u.grad?.emp;
                            const refG = grad
                              ? referenciaGraduada(p?.v3m?.gr?.e, u.grad?.emp, u.grad?.esc)
                              : null;
                            const refC = grad ? null : referenciaCondicao(p?.v3m?.pc, u.cond, u.tipo);
                            return (
                              <div key={i} className="flex flex-wrap items-center gap-2 text-xs">
                                <span className="w-8 font-semibold text-[#998f7c]">#{i + 1}</span>
                                <select
                                  value={u.cond || ''}
                                  disabled={grad}
                                  onChange={(e) => setMap(setCondicao(it.id, i, (e.target.value || undefined) as Condicao | undefined))}
                                  className="border border-[#2b2517]/20 rounded-lg px-2 py-1 bg-white text-[#292318] disabled:opacity-40"
                                >
                                  <option value="">condição —</option>
                                  {CONDICOES.map((c) => <option key={c.v} value={c.v}>{c.rotulo}</option>)}
                                </select>
                                <select
                                  value={u.tipo || ''}
                                  disabled={grad}
                                  onChange={(e) => setMap(setUnidade(it.id, i, { tipo: (e.target.value || undefined) as Tipo | undefined }))}
                                  className="border border-[#2b2517]/20 rounded-lg px-2 py-1 bg-white text-[#292318] disabled:opacity-40"
                                >
                                  <option value="">tipo —</option>
                                  {TIPOS.map((t) => <option key={t.v} value={t.v}>{t.rotulo}</option>)}
                                </select>
                                <select
                                  value={u.lang || ''}
                                  disabled={grad}
                                  onChange={(e) => setMap(setUnidade(it.id, i, { lang: (e.target.value || undefined) as Idioma | undefined }))}
                                  className="border border-[#2b2517]/20 rounded-lg px-2 py-1 bg-white text-[#292318] disabled:opacity-40"
                                >
                                  <option value="">idioma —</option>
                                  {IDIOMAS.map((l) => <option key={l} value={l}>{l}</option>)}
                                </select>
                                <label className="inline-flex items-center gap-1 text-[#292318] cursor-pointer">
                                  <input
                                    type="checkbox"
                                    checked={grad}
                                    onChange={(e) => setMap(setGraduacao(it.id, i, e.target.checked ? { emp: 'PSA', esc: '' } : null))}
                                  />
                                  Graduada
                                </label>
                                {grad && (
                                  <>
                                    <select
                                      value={u.grad?.emp || 'PSA'}
                                      onChange={(e) => setMap(setUnidade(it.id, i, { grad: { emp: e.target.value, esc: u.grad?.esc || '' } }))}
                                      className="border border-[#2b2517]/20 rounded-lg px-2 py-1 bg-white text-[#292318]"
                                    >
                                      {EMPRESAS.map((e2) => <option key={e2} value={e2}>{e2}</option>)}
                                    </select>
                                    <input
                                      value={u.grad?.esc || ''}
                                      placeholder="escala (ex: GEM-MT 10)"
                                      onChange={(e) => setMap(setUnidade(it.id, i, { grad: { emp: u.grad?.emp || 'PSA', esc: e.target.value } }))}
                                      className="border border-[#2b2517]/20 rounded-lg px-2 py-1 bg-white text-[#292318] w-44"
                                    />
                                  </>
                                )}
                                <label className="inline-flex items-center gap-1 text-[#6b6252]">
                                  pago R$
                                  <input
                                    type="number"
                                    min="0"
                                    step="0.01"
                                    value={u.pago ?? ''}
                                    placeholder="—"
                                    onChange={(e) => {
                                      const v = e.target.value === '' ? undefined : Number(e.target.value);
                                      setMap(setUnidade(it.id, i, { pago: v != null && isFinite(v) && v >= 0 ? v : undefined }));
                                    }}
                                    className="border border-[#2b2517]/20 rounded-lg px-2 py-1 bg-white text-[#292318] w-24"
                                  />
                                </label>
                                <button
                                  onClick={() => setMap(removeUnidade(it.id, i))}
                                  className="ml-auto text-[#998f7c] hover:text-[#a90924]"
                                >
                                  remover
                                </button>
                                {grad ? (
                                  <p className="w-full text-[11px] text-[#6b6252] pl-10">
                                    {refG
                                      ? <>Referência: <b>{refG.empresa || 'todas as certificadoras'}</b>
                                        {refG.exato && refG.escala
                                          ? <> · mesma escala ({refG.escala})</>
                                          : refG.escala ? <> · escala {refG.escala}</> : <> · qualquer escala</>}
                                        {' '}· {refG.n} anúncio{refG.n !== 1 ? 's' : ''} · {brl(refG.menor)} – {brl(refG.maior)} (mediana {brl(refG.mediana)})</>
                                      : <>Sem anúncio graduado desta carta na Liga — unidade não entra no valor graduado.</>}
                                  </p>
                                ) : (u.cond || u.tipo) ? (
                                  <p className="w-full text-[11px] text-[#6b6252] pl-10">
                                    {refC
                                      ? <>Referência <b>{refC.cond || 'qualquer condição'} · {rotuloTipo(refC.tipo)}</b>
                                        {refC.exato ? ' (mesma condição e tipo)' : ' (aproximada)'}
                                        {' '}· {refC.n} anúncio{refC.n !== 1 ? 's' : ''} · {brl(refC.menor)} – {brl(refC.maior)} (mediana {brl(refC.mediana)})</>
                                      : <>Sem anúncio nesta condição/tipo — unidade entra pelo mercado geral da carta.</>}
                                  </p>
                                ) : null}
                              </div>
                            );
                          })}
                        </div>
                        <div className="flex items-center gap-3 mt-2">
                          <button
                            onClick={() => setMap(addUnidade(it.id))}
                            className="inline-flex items-center gap-1 text-xs font-semibold text-[#d40b2e] hover:text-[#a90924]"
                          >
                            <Plus className="w-3.5 h-3.5" /> unidade
                          </button>
                          {p?.v3m?.gr?.n ? (
                            <span className="text-[11px] text-[#998f7c]">
                              {p.v3m.gr.n} anúncio{p.v3m.gr.n !== 1 ? 's' : ''} graduado{p.v3m.gr.n !== 1 ? 's' : ''} desta carta na Liga
                            </span>
                          ) : null}
                        </div>
                      </div>
                    )}
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
