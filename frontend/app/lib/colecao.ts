'use client';
/**
 * colecao.ts — coleção pessoal local (P2.37), persistida em localStorage.
 *
 * Chave única da carta = {idE}-{num} da migração do índice único (bac57da).
 * Guardamos { id: quantidade } + metadados leves (nome/img p/ render sem lookup).
 *
 * Como o site é estático (GitHub Pages), usamos localStorage (não cookies):
 * ~5-10MB, síncrono, persiste entre sessões no mesmo navegador. A única
 * ressalva é ser por-navegador → página oferece exportar/importar JSON.
 * Só coleção ("tenho") por ora; wishlist fica para depois (P2.37).
 */

export interface ColecaoItem {
  id: string;        // chave canônica {idE}-{num}
  nome: string;      // nome da carta (p/ exibir sem lookup)
  img?: string | null;
  s?: string;        // set (idE)
  num?: string;
  qtd: number;       // quantidade (>=1)
  addAt: number;     // timestamp
}

export type ColecaoMap = Record<string, ColecaoItem>;

const KEY = 'pokescan.colecao';
const KEY_TOC = 'pokescan.colecao.toc'; // lista de ids (ordem)

function readAll(): ColecaoMap {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return {};
    return JSON.parse(raw) as ColecaoMap;
  } catch {
    return {};
  }
}

function writeAll(map: ColecaoMap): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(map));
  } catch {
    // quota excedida / desabilitado — ignora silenciosamente
  }
}

/** Adiciona (ou incrementa qtd). upsert: se já existe, soma 1. */
export function addCarta(item: Omit<ColecaoItem, 'qtd' | 'addAt'>, qtd = 1): ColecaoMap {
  const map = readAll();
  const cur = map[item.id];
  if (cur) {
    map[item.id] = { ...cur, qtd: cur.qtd + qtd };
  } else {
    map[item.id] = { ...item, qtd, addAt: Date.now() };
  }
  writeAll(map);
  return map;
}

/** Define a quantidade exata (>=1). qtd<=0 remove. */
export function setQtd(id: string, qtd: number): ColecaoMap {
  const map = readAll();
  if (!map[id]) return map;
  if (qtd <= 0) {
    delete map[id];
  } else {
    map[id] = { ...map[id], qtd };
  }
  writeAll(map);
  return map;
}

/** Remove da coleção. */
export function removeCarta(id: string): ColecaoMap {
  const map = readAll();
  delete map[id];
  writeAll(map);
  return map;
}

/** Limpa tudo. */
export function limparColecao(): ColecaoMap {
  writeAll({});
  return {};
}

/** Importa de um JSON (substitui). */
export function importarColecao(mapa: ColecaoMap): ColecaoMap {
  writeAll(mapa);
  return mapa;
}

/** Exporta p/ download JSON. */
export function exportarJSON(map: ColecaoMap): string {
  return JSON.stringify(map, null, 2);
}

/** Lista de itens em ordem de inserção. */
export function listarColecao(map: ColecaoMap): ColecaoItem[] {
  return Object.values(map);
}

export function totalCartas(map: ColecaoMap): number {
  return Object.values(map).reduce((acc, it) => acc + (it.qtd || 1), 0);
}

/**
 * Valor da coleção. 'estimado' = preço justo do modelo (pred BRL), 'real' =
 * preço de mercado escorado. Usamos o lookupCard por {idE}-{num} p/ resolver
 * preço (real = modelo.real, estimado = preco_brl/preco_justo). Se não houver
 * preço, trata como 0 e conta % de cobertura.
 */
export interface ValorColecao {
  estimado: number;      // soma dos preços justos (BRL) × qtd
  real: number;          // soma dos preços reais escorados (BRL) × qtd
  upsidePct: number;     // (estimado-real)/real × 100 (0 se sem base)
  nComPreco: number;     // cartas com preço resolvido
  nTotal: number;        // cartas na coleção
}

/** Constrói o valor a partir de uma função de lookup (injeta p/ testar). */
export function calcularValor(
  itens: ColecaoItem[],
  preco: (id: string) => { real?: number | null; estimado?: number | null } | null
): ValorColecao {
  let estimado = 0, real = 0, nCom = 0;
  for (const it of itens) {
    const p = preco(it.id);
    const q = it.qtd || 1;
    if (p) {
      const r = Number(p.real) || 0;
      const e = Number(p.estimado) || 0;
      real += r * q;
      estimado += e * q;
      if (r > 0 || e > 0) nCom++;
    }
  }
  const upsidePct = real > 0 ? ((estimado - real) / real) * 100 : 0;
  return {
    estimado,
    real,
    upsidePct,
    nComPreco: nCom,
    nTotal: itens.length,
  };
}