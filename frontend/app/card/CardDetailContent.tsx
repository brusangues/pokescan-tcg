'use client';

import { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import Image from 'next/image';
import {
  Loader, AlertCircle, TrendingUp, TrendingDown, ArrowLeft,
  DollarSign, Palette, Hash, Shield, Layers, Languages,
} from 'lucide-react';
import PriceHistory from '@/app/components/PriceHistory';
import { lookupCard, normNome } from '@/app/lib/cardLookup';
import { getBasePath } from '@/app/lib/basePath';

/** Cache de módulo do índice de idiomas (uma busca por sessão). */
let _idiomasCache: Record<string, any> | null = null;

interface CardData {
  id: string;
  name: string;
  supertype: string;
  subtypes: string[];
  hp?: string;
  types?: string[];
  evolvesFrom?: string;
  evolvesTo?: string;
  rarity?: string;
  artist?: string;
  number: string;
  set: {
    id: string;
    name: string;
    series: string;
    releaseDate: string;
    printedTotal: number;
  };
  images: { small: string; large: string };
  tcgplayer?: {
    updatedAt: string;
    prices: Record<string, { market?: number; low?: number; mid?: number; high?: number }>;
  };
  cardmarket?: {
    updatedAt: string;
    prices: {
      averageSellPrice?: number;
      lowPrice?: number;
      trendPrice?: number;
      avg1?: number;
      avg7?: number;
      avg30?: number;
    };
  };
  previsao_semana?: number;
  tendencia_pct?: number;
  // Liga-first (pt-BR): campos direto do catálogo da Liga (cartas sem registro escorado)
  liga_nen?: string | null;
  liga_ico?: number | null;
  moeda?: string;
  preco_brl?: number | null;
  flavorText?: string;
  attacks?: { name: string; cost?: string[]; damage?: string; text?: string }[];
  abilities?: { name: string; text: string }[];
  weaknesses?: { type: string; value: string }[];
  resistances?: { type: string; value: string }[];
  retreatCost?: string[];
  modelo?: {
    real: number;
    pred: number;
    upside: number;
    oportunidade: string;
    iCO: number;
    moeda: string;
    liga_id: string;
    card_id?: string;
    nEN: string;
    sNumber: string;
    num: string;
    sigla: string;
    setNome: string;
    fonte: string;
    is_jp?: boolean;
    ligaOk?: boolean;
    buscaLiga?: string;
  } | null;
  error?: string;
  // Liga-first (P1.33): nome pt-BR + EN original (p/ tooltip)
  nPT?: string | null;
  nEN?: string | null;
  }

/** Seção 'Mesma carta em outros idiomas' — agrupa por idioma (PT/EN/JP). */
function IdiomasSection({ dados, atual }: {
  dados: { liga: any[]; en: any[] };
  atual: { card_id?: string; setId?: string; num?: string };
}) {
  const LANGS: Record<string, { label: string; flag: string }> = {
    pt: { label: 'Português', flag: '🇧🇷' },
    en: { label: 'Inglês', flag: '🇬🇧' },
    jp: { label: 'Japonês', flag: '🇯🇵' },
  };
  const LIMITE = 5;

  const grupos = (['pt', 'en', 'jp'] as const)
    .map(lang => ({
      lang,
      liga: (dados.liga || []).filter(x => x.lang === lang),
    }))
    .filter(g => g.liga.length > 0);

  const enItens = (dados.en || []) as any[];

  if (grupos.length === 0 && enItens.length === 0) return null;

  return (
    <div className="bg-[#fffdf7] rounded-2xl p-4 border border-[#2b2517]/20 shadow-sm">
      <h3 className="text-xs font-semibold text-[#6b6252] uppercase mb-3 flex items-center gap-1.5">
        <Languages className="w-3.5 h-3.5" />
        Mesma carta em outros idiomas
      </h3>

      <div className="space-y-3">
        {/* Liga Pokémon (PT/EN/JP vendidos pela Liga) */}
        {grupos.map(g => {
          const meta = LANGS[g.lang];
          const visiveis = g.liga.slice(0, LIMITE);
          const resto = g.liga.length - visiveis.length;
          return (
            <div key={g.lang}>
              <p className="text-[10px] font-semibold text-[#998f7c] uppercase tracking-wide mb-1.5">
                {meta.flag} {meta.label}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {visiveis.map(x => {
                  const atualLiga = x.cid === atual.card_id;
                  const href = `${getBasePath()}/card?card_id=${encodeURIComponent(x.cid)}`;
                  return (
                    <a
                      key={x.cid}
                      href={atualLiga ? undefined : href}
                      aria-disabled={atualLiga}
                      className={`text-[11px] px-2 py-1 rounded-lg border font-mono transition-colors ${
                        atualLiga
                          ? 'bg-[#f3e9d2] border-[#2b2517]/25 text-[#a90924] cursor-default'
                          : 'bg-[#fffdf7] border-[#2b2517]/20 text-[#292318] hover:border-[#2b2517]/30 hover:text-[#d40b2e]'
                      }`}
                    >
                      {x.sigla} #{x.sNumber || x.num}
                    </a>
                  );
                })}
                {resto > 0 && (
                  <span className="text-[11px] text-[#998f7c] px-1 py-1">+{resto}</span>
                )}
              </div>
            </div>
          );
        })}

        {/* Catálogo TCGAPI (inglês) */}
        {enItens.length > 0 && (
          <div>
            <p className="text-[10px] font-semibold text-[#998f7c] uppercase tracking-wide mb-1.5">
              🇬🇧 Inglês (TCGAPI)
            </p>
            <div className="flex flex-wrap gap-1.5">
              {enItens.slice(0, LIMITE).map(x => {
                const atualEn = x.s === atual.setId && String(x.num) === String(atual.num);
                const href = `${getBasePath()}/card?set=${encodeURIComponent(x.s)}&num=${encodeURIComponent(x.num)}&nome=${encodeURIComponent(x.nome)}`;
                return (
                  <a
                    key={x.id}
                    href={atualEn ? undefined : href}
                    aria-disabled={atualEn}
                    className={`text-[11px] px-2 py-1 rounded-lg border font-mono transition-colors ${
                      atualEn
                        ? 'bg-[#f3e9d2] border-[#2b2517]/25 text-[#a90924] cursor-default'
                        : 'bg-[#fffdf7] border-[#2b2517]/20 text-[#292318] hover:border-[#2b2517]/30 hover:text-[#d40b2e]'
                    }`}
                  >
                    {x.s} #{x.num}
                  </a>
                );
              })}
              {enItens.length > LIMITE && (
                <span className="text-[11px] text-[#998f7c] px-1 py-1">+{enItens.length - LIMITE}</span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

  export default function CardDetailContent() {
  const searchParams = useSearchParams();
  const nome = searchParams?.get('nome');
  const sigla = searchParams?.get('sigla');
  const num = searchParams?.get('num');
  const set = searchParams?.get('set');
  const card_id = searchParams?.get('card_id');
  const liga_id = searchParams?.get('liga_id');

  const displayId = card_id || liga_id || nome || `${sigla}-${num}`;

  const [card, setCard] = useState<CardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [idiomas, setIdiomas] = useState<Record<string, any> | null>(null);

  // Índice 'mesma carta em outros idiomas' (lazy, cacheado por sessão)
  useEffect(() => {
    (async () => {
      try {
        if (!_idiomasCache) {
          const res = await fetch(`${getBasePath()}/data/card_idiomas.json`);
          _idiomasCache = await res.json();
        }
        setIdiomas(_idiomasCache);
      } catch (e) {
        console.warn('card_idiomas.json indisponível:', e);
      }
    })();
  }, []);

  useEffect(() => {
    if (!nome && !sigla && !num && !card_id && !liga_id) { setError('Nenhum parâmetro de busca'); setLoading(false); return; }

    (async () => {
      try {
        const cardData = await lookupCard({
          nome,
          sigla,
          num,
          set,
          card_id,
          liga_id,
        });
        setCard(cardData);
      } catch (e: any) {
        setError(e.message || 'Carta não encontrada');
      } finally {
        setLoading(false);
      }
    })();
  }, [nome, sigla, num, set, card_id, liga_id]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#fbf4e6] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader className="w-8 h-8 animate-spin text-[#d40b2e]" />
          <p className="text-sm text-[#6b6252]">Buscando carta...</p>
        </div>
      </div>
    );
  }

  if (error || !card) {
    return (
      <div className="min-h-screen bg-[#fbf4e6] flex items-center justify-center">
        <div className="bg-[#fffdf7] p-8 rounded-2xl shadow-lg max-w-md text-center space-y-4">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto">
            <AlertCircle className="w-8 h-8 text-red-500" />
          </div>
          <h2 className="text-lg font-bold text-[#292318]">Carta não encontrada</h2>
          <p className="text-sm text-[#6b6252]">{error || card?.error}</p>
          <a href={`${getBasePath()}/`} className="inline-flex items-center gap-2 px-4 py-2 bg-[#d40b2e] text-white rounded-lg hover:bg-[#a90924] text-sm">
            <ArrowLeft className="w-4 h-4" /> Voltar
          </a>
        </div>
      </div>
    );
  }

  const price = card.tcgplayer?.prices?.holofoil?.market
    || card.tcgplayer?.prices?.normal?.market
    || card.cardmarket?.prices?.averageSellPrice;

  return (
    <div className="min-h-screen bg-[#fbf4e6] pb-12">
      {/* Header */}
      <div className="bg-[#292318] text-white py-6">
        <div className="max-w-5xl mx-auto px-4">
          <a href={`${getBasePath()}/`} className="inline-flex items-center gap-2 text-[#f3e9d2] text-sm hover:text-white transition-colors mb-4">
            <ArrowLeft className="w-4 h-4" /> Voltar
          </a>
          <h1 className="text-3xl font-bold tracking-tight">{card.name}</h1>
          {card.nPT && card.nEN && card.nEN !== card.name && (
            <p className="text-[#f3e9d2]/70 text-base mt-0.5">{card.nEN}</p>
          )}
          <p className="text-[#f3e9d2] text-sm mt-1">{card.set.name} — #{card.number}/{card.set.printedTotal}</p>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-6">
        <div className="grid md:grid-cols-[320px_1fr] gap-8">
          {/* Imagem da carta */}
          <div className="space-y-4">
            <div className="bg-[#fffdf7] rounded-2xl shadow-sm border border-[#2b2517]/20 p-4">
              <div className="relative aspect-[2.5/3.5] w-full bg-[#f3e9d2] rounded-xl overflow-hidden">
                <Image
                  src={card.images.large}
                  alt={card.name}
                  fill
                  className="object-contain"
                  sizes="320px"
                  unoptimized
                />
              </div>
            </div>

            {/* Link para a Liga Pokémon — só quando a carta exibida
                corresponde ao registro escorado (ligaOk) */}
            {card.modelo && card.modelo.nEN && card.modelo.ligaOk && (
              <a
                href={`https://www.ligapokemon.com.br/?view=cards/card&card=${encodeURIComponent(card.modelo.nEN)}&ed=${encodeURIComponent(card.modelo.sigla)}&num=${encodeURIComponent(card.modelo.num || card.modelo.sNumber || '')}`}
                target="_blank"
                rel="noopener noreferrer"
                className="block bg-[#fffdf7] rounded-2xl p-4 border border-[#2b2517]/20 shadow-sm hover:border-[#2b2517]/30 hover:shadow-md transition-all group"
              >
                <h3 className="text-xs font-semibold text-[#6b6252] uppercase mb-1">Referência externa</h3>
                <p className="text-sm font-medium text-[#d40b2e] group-hover:underline flex items-center gap-1">
                  {card.modelo.sigla} #{card.modelo.sNumber || card.modelo.num}
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                </p>
              </a>
            )}
            {/* Liga-first (pt-BR): cartas do catálogo da LIGA sem registro escorado
                (ex. MEP/MEPR) — link direto pelo nEN no formato da Liga */}
            {!card.modelo && card.liga_nen && (
              <a
                href={`https://www.ligapokemon.com.br/?view=cards/card&card=${encodeURIComponent(card.liga_nen)}&ed=${encodeURIComponent((card.set?.id || '').toUpperCase())}&num=${encodeURIComponent(card.number || '')}`}
                target="_blank"
                rel="noopener noreferrer"
                className="block bg-[#fffdf7] rounded-2xl p-4 border border-[#2b2517]/20 shadow-sm hover:border-[#2b2517]/30 hover:shadow-md transition-all group"
              >
                <h3 className="text-xs font-semibold text-[#6b6252] uppercase mb-1">Referência externa</h3>
                <p className="text-sm font-medium text-[#d40b2e] group-hover:underline flex items-center gap-1">
                  {(card.set?.id || '').toUpperCase()} #{card.number}
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                </p>
              </a>
            )}

            {/* Fallback EN-only (P2.41): sem edição direta na Liga — link de BUSCA
                pelo nome (a Liga localiza por nome; não há card_id/sigla certo) */}
            {card.modelo && !card.modelo.ligaOk && card.modelo.buscaLiga && (
              <a
                href={`https://www.ligapokemon.com.br/?view=cards/card&card=${encodeURIComponent(card.modelo.buscaLiga)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="block bg-[#fffdf7] rounded-2xl p-4 border border-[#2b2517]/20 shadow-sm hover:border-[#2b2517]/30 hover:shadow-md transition-all group"
              >
                <h3 className="text-xs font-semibold text-[#6b6252] uppercase mb-1">Referência externa</h3>
                <p className="text-sm font-medium text-[#d40b2e] group-hover:underline flex items-center gap-1">
                  Buscar "{card.modelo.buscaLiga}" na Liga
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                </p>
              </a>
            )}

            {/* Mesma carta em outros idiomas (JP/PT/EN) */}
            {(() => {
              const chave = normNome(String(card.modelo?.nEN || card.name || '').split('(')[0]);
              const dados = (idiomas && chave && idiomas[chave]) || null;
              if (!dados) return null;
              return (
                <IdiomasSection
                  dados={dados}
                  atual={{ card_id: card.modelo?.card_id, setId: card.set?.id, num: card.number }}
                />
              );
            })()}
          </div>

          {/* Detalhes */}
          <div className="space-y-6">
            {/* Info básica */}
            <div className="bg-[#fffdf7] rounded-2xl shadow-sm border border-[#2b2517]/20 p-6">
              <h2 className="text-lg font-bold text-[#292318] mb-4 border-b pb-3">Detalhes da Carta</h2>
              <div className="grid grid-cols-2 gap-4 text-sm">
                {card.hp && (
                  <div className="flex items-center gap-2">
                    <Shield className="w-4 h-4 text-red-500" />
                    <span className="text-[#6b6252]">HP</span>
                    <span className="font-bold text-[#292318]">{card.hp}</span>
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <Hash className="w-4 h-4 text-[#d40b2e]" />
                  <span className="text-[#6b6252]">Raridade</span>
                  <span className="font-medium text-[#292318]">{card.rarity || 'Common'}</span>
                </div>
                {card.artist && (
                  <div className="flex items-center gap-2 col-span-1">
                    <Palette className="w-4 h-4 text-pink-500" />
                    <span className="text-[#6b6252]">Artista</span>
                    <span className="font-medium text-[#292318]">{card.artist}</span>
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <Layers className="w-4 h-4 text-blue-500" />
                  <span className="text-[#6b6252]">Tipo</span>
                  <span className="font-medium text-[#292318]">{card.supertype}{card.subtypes?.length ? ' — ' + card.subtypes.join(', ') : ''}</span>
                </div>
              </div>
            </div>

            {/* Previsão do Modelo (do CSV escorado) */}
            {card.modelo && (
              <div className="bg-[#fffdf7] rounded-2xl shadow-sm border border-[#2b2517]/20 p-6">
                <h2 className="text-lg font-bold text-[#292318] mb-4 border-b pb-3">Previsão do Modelo</h2>
                {card.modelo.is_jp && (
                  <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2.5 mb-4">
                    <svg className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <p className="text-xs text-amber-800 leading-relaxed">
                      <span className="font-semibold">Carta japonesa.</span> Não há preço de mercado brasileiro
                      global (TCGPlayer/Cardmarket) para cartas JP — a previsão usa o equivalente EN
                      (mesma arte/raridade) como referência de preço justo.
                    </p>
                  </div>
                )}
                {/* Histórico de preços (hits diários + snapshots) */}
                <PriceHistory
                  ligaId={card.modelo.card_id || card.modelo.liga_id || undefined}
                  nome={card.modelo.nEN ? card.modelo.nEN.split('(')[0].trim() : undefined}
                  sigla={card.modelo.sigla || undefined}
                  moeda={card.modelo.moeda}
                />
                <div className="space-y-3">
                  {price !== undefined && (
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-[#6b6252]">Mercado global (USD)</span>
                      <span className="font-bold text-[#292318]">${price.toFixed(2)}</span>
                    </div>
                  )}
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-[#6b6252]">Preço real (R$)</span>
                    <span className="font-bold text-[#292318]">{card.modelo.moeda}{card.modelo.real.toFixed(2)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-[#6b6252]">Preço justo (modelo)</span>
                    <span className="font-bold text-[#a90924]">{card.modelo.moeda}{card.modelo.pred.toFixed(2)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-[#6b6252]">Upside</span>
                    <span className={`inline-flex items-center gap-1 text-sm font-bold px-2.5 py-1 rounded-full ${
                      card.modelo.upside > 0 ? 'text-green-700 bg-green-100' : 'text-red-700 bg-red-100'
                    }`}>
                      {card.modelo.upside > 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                      {card.modelo.upside > 0 ? '+' : ''}{card.modelo.upside.toFixed(0)}%
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-[#6b6252]">Classificação</span>
                    <span className="text-sm font-semibold text-[#292318]">{card.modelo.oportunidade}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-[#6b6252]">Vendedores (iCO)</span>
                    <span className="text-sm font-semibold text-[#292318]">
                      {card.modelo.iCO > 0 ? card.modelo.iCO : '—'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-[#6b6252]">Coleção</span>
                    <span className="text-sm font-semibold text-[#292318]">
                      {card.modelo.sigla}{card.modelo.setNome ? ` — ${card.modelo.setNome}` : ''}
                    </span>
                  </div>
                  {card.modelo.fonte && (
                    <p className="text-[10px] text-[#998f7c] pt-2 border-t border-[#2b2517]/15">
                      Fonte: {card.modelo.fonte}
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Mercado detalhado */}
            <div className="bg-[#fffdf7] rounded-2xl shadow-sm border border-[#2b2517]/20 p-6">
              <h2 className="text-lg font-bold text-[#292318] mb-4 border-b pb-3">Preços</h2>

              {/* Liga-first (pt-BR): preço BRL direto do catálogo da Liga */}
              {card.moeda === 'BRL' && card.preco_brl != null && (
                <div className="mb-4">
                  <h3 className="text-sm font-semibold text-[#6b6252] mb-2">Preço no Brasil (R$)</h3>
                  <div className="flex justify-between text-sm">
                    <span className="text-[#6b6252]">Preço mercado</span>
                    <span className="font-medium text-[#292318]">R$ {card.preco_brl.toFixed(2)}</span>
                  </div>
                </div>
              )}

              {/* TCGPlayer */}
              {card.tcgplayer?.prices && (
                <div className="mb-4">
                  <h3 className="text-sm font-semibold text-[#6b6252] mb-2">TCGPlayer</h3>
                  {Object.entries(card.tcgplayer.prices).map(([variant, p]) => {
                    if (!p || !p.market) return null;
                    return (
                      <div key={variant} className="flex justify-between text-sm py-.5">
                        <span className="text-[#6b6252] capitalize">{variant.replace(/([-H])/g, ' $1')}</span>
                        <span className="font-medium text-[#292318]">
                          ${p.market.toFixed(2)}
                          {p.high ? <span className="text-xs text-[#998f7c] ml-1">(Low${p.low?.toFixed(2)} — High ${p.high.toFixed(2)})</span> : ''}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Cardmarket */}
              {card.cardmarket?.prices && (
                <div>
                  <h3 className="text-sm font-semibold text-[#6b6252] mb-2">Cardmarket (EU)</h3>
                  <div className="space-y-1">
                    {card.cardmarket.prices.averageSellPrice != null && (
                      <div className="flex justify-between text-sm">
                        <span className="text-[#6b6252]">Médio 30d</span>
                        <span className="font-medium text-[#292318]">€{card.cardmarket.prices.avg30?.toFixed(2)}</span>
                      </div>
                    )}
                    {card.cardmarket.prices.trendPrice != null && (
                      <div className="flex justify-between text-sm">
                        <span className="text-[#6b6252]">Tendência</span>
                        <span className="font-medium text-[#292318]">€{card.cardmarket.prices.trendPrice.toFixed(2)}</span>
                      </div>
                    )}
                    {card.cardmarket.prices.lowPrice != null && (
                      <div className="flex justify-between text-sm">
                        <span className="text-[#6b6252]">Menor (EU)</span>
                        <span className="font-medium text-[#292318]">€{card.cardmarket.prices.lowPrice.toFixed(2)}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Previsão da próxima semana (P1.29) */}
              {card.previsao_semana != null && card.tendencia_pct != null && (
                <div className="mt-4 pt-4 border-t border-[#2b2517]/15">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-[#6b6252]">Previsão — próxima semana</h3>
                      <p className="text-xs text-[#998f7c] mt-0.5">
                        Estimativa do modelo com base no histórico de preços (TCGCSV)
                      </p>
                    </div>
                    <div className="text-right">
                      <span className="text-lg font-bold text-[#292318]">${card.previsao_semana.toFixed(2)}</span>
                      <div>
                        <span
                          className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full ${
                            card.tendencia_pct >= 0
                              ? 'bg-emerald-100 text-emerald-700'
                              : 'bg-red-100 text-red-700'
                          }`}
                        >
                          {card.tendencia_pct >= 0 ? '▲' : '▼'}{' '}
                          {Math.abs(card.tendencia_pct).toFixed(1)}%
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Ataques / Habilidades */}
            {((card.attacks?.length || 0) > 0 || (card.abilities?.length || 0) > 0) && (
              <div className="bg-[#fffdf7] rounded-2xl shadow-sm border border-[#2b2517]/20 p-6">
                <h2 className="text-lg font-bold text-[#292318] mb-4 border-b pb-3">Ataques e Habilidades</h2>

                {card.abilities?.map((ability, i) => (
                  <div key={`abi-${i}`} className="mb-3 bg-blue-50 rounded-lg p-3">
                    <p className="font-semibold text-blue-900 text-sm">{ability.name}</p>
                    {ability.text && <p className="text-xs text-blue-700 mt-1">{ability.text}</p>}
                  </div>
                ))}

                {card.attacks?.map((attack, i) => (
                  <div key={`atk-${i}`} className="flex items-start justify-between py-2 text-sm border-t border-[#2b2517]/20 first:border-0">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <p className="font-semibold text-[#292318]">{attack.name}</p>
                        {attack.damage && (
                          <span className="text-xs font-bold text-red-600 bg-red-100 px-1.5 py-0.5 rounded">
                            {attack.damage}
                          </span>
                        )}
                      </div>
                      {attack.text && <p className="text-xs text-[#6b6252] mt-1">{attack.text}</p>}
                    </div>
                    {attack.cost && (
                      <div className="flex gap-1">
                        {attack.cost.map((type, j) => (
                          <div key={j} className="w-5 h-5 rounded-full bg-gray-200 flex items-center justify-center text-[10px] font-bold" title={type}>
                            {type === 'Grass' ? '🍃' : type === 'Fire' ? '🔥' : type === 'Water' ? '💧' : type === 'Lightning' ? '⚡' : type === 'Psychic' ? '🔮' : type === 'Fighting' ? '👊' : type === 'Darkness' ? '🌑' : type === 'Metal' ? '⚙️' : type === 'Fairy' ? '✨' : type === 'Dragon' ? '🐉' : type === 'Colorless' ? '⚪' : type[0]}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Weaknesses/Resistances/Retreat */}
            {(card.weaknesses?.length === 0 || card.resistances?.length === 0 || card.retreatCost != null) && (
              <div className="bg-[#fffdf7] rounded-2xl shadow-sm border border-[#2b2517]/20 p-6">
                <h2 className="text-lg font-bold text-[#292318] mb-4 border-b pb-3">Combate</h2>
                <div className="grid grid-cols-3 gap-4 text-sm">
                  {card.weaknesses?.map((w, i) => (
                    <div key={`weak-${i}`} className="bg-red-50 rounded-lg p-3 text-center">
                      <p className="text-xs text-red-500">Fraqueza</p>
                      <p className="font-bold text-red-700">{w.type} ×{w.value}</p>
                    </div>
                  ))}
                  {card.resistances?.map((r, i) => (
                    <div key={`res-${i}`} className="bg-green-50 rounded-lg p-3 text-center">
                      <p className="text-xs text-green-500">Resistência</p>
                      <p className="font-bold text-green-700">{r.type} −{r.value}</p>
                    </div>
                  ))}
                  {card.retreatCost != null && (
                    <div className="bg-[#f3e9d2] rounded-lg p-3 text-center">
                      <p className="text-xs text-[#6b6252]">Recuo</p>
                      <p className="font-bold text-[#292318]">{'⚪'.repeat(card.retreatCost.length)}</p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Flavor Text */}
        {card.flavorText && (
          <div className="bg-[#fffdf7] rounded-2xl shadow-sm border border-[#2b2517]/20 p-6 mt-6 text-center">
            <p className="italic text-[#6b6252] text-sm">"{card.flavorText}"</p>
          </div>
        )}

        {/* Footer metadata */}
        <div className="flex gap-4 text-xs text-[#998f7c] pt-6 justify-center">
          <span>{card.set.releaseDate}</span>
          <span>#{card.number}</span>
          <span>{card.set.series}</span>
        </div>
      </div>
    </div>
  );
}