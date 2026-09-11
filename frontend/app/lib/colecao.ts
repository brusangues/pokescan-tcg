'use client';
/**
 * colecao.ts — coleção pessoal local (P2.37 + P2.43), persistida em localStorage.
 *
 * Chave única da carta = {idE}-{num} da migração do índice único (bac57da).
 * Guardamos { id: { qtd, unidades[] } } + metadados leves (nome/img p/ render
 * sem lookup).
 *
 * P2.43 — cada UNIDADE pode ter condição (`cond`) e, se graduada, a
 * certificadora + escala (`grad`): a mesma carta física pode ter 3 raw (NM/SP)
 * e 1 graduada PSA 10, com valores de mercado diferentes. `qtd` é mantido em
 * sincronia com `unidades.length` (coleções antigas não têm `unidades` — viram
 * `qtd` unidades sem detalhe, sem perder nada).
 *
 * Como o site é estático (GitHub Pages), usamos localStorage (não cookies):
 * ~5-10MB, síncrono, persiste entre sessões no mesmo navegador. A única
 * ressalva é ser por-navegador → página oferece exportar/importar JSON.
 * Só coleção ("tenho") por ora; wishlist fica para depois (P2.37).
 */

import {
  unidadesDe, type Condicao, type Grading, type UnidadeColecao,
} from '@/app/lib/grading';

export type { Condicao, Grading, UnidadeColecao };

export interface ColecaoItem {
  id: string;        // chave canônica {idE}-{num}
  nome: string;      // nome da carta (p/ exibir sem lookup)
  img?: string | null;
  s?: string;        // set (idE)
  num?: string;
  qtd: number;       // quantidade (>=1) — espelho de unidades.length
  unidades?: UnidadeColecao[];  // P2.43: condição/graduação por unidade
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

/** Mantém `qtd` alinhado com o número de unidades. */
function normaliza(it: ColecaoItem): ColecaoItem {
  const unids = unidadesDe(it);
  return { ...it, unidades: unids, qtd: unids.length };
}

/** Aplica um patch preservando o resto do item. */
function aplica(id: string, fn: (it: ColecaoItem) => ColecaoItem | null): ColecaoMap {
  const map = readAll();
  const it = map[id];
  if (!it) return map;
  const novo = fn(normaliza(it));
  if (!novo || (novo.unidades?.length ?? 0) <= 0) delete map[id];
  else map[id] = novo;
  writeAll(map);
  return map;
}

/** Adiciona (ou incrementa qtd). upsert: se já existe, soma 1 unidade. */
export function addCarta(
  item: Omit<ColecaoItem, 'qtd' | 'unidades' | 'addAt'>,
  qtd = 1,
  unidade?: UnidadeColecao
): ColecaoMap {
  const map = readAll();
  const cur = map[item.id];
  if (cur) {
    const unids = unidadesDe(cur);
    for (let i = 0; i < qtd; i++) unids.push(unidade ? { ...unidade } : {});
    map[item.id] = normaliza({ ...cur, unidades: unids });
  } else {
    map[item.id] = normaliza({
      ...item,
      qtd,
      unidades: Array.from({ length: Math.max(1, qtd) }, () => (unidade ? { ...unidade } : {})),
      addAt: Date.now(),
    });
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
    const unids = unidadesDe(map[id]);
    while (unids.length < qtd) unids.push({});
    unids.length = qtd;
    map[id] = normaliza({ ...map[id], unidades: unids });
  }
  writeAll(map);
  return map;
}

/** Edita uma unidade (condição e/ou graduação). idx fora do range é ignorado. */
export function setUnidade(id: string, idx: number, patch: Partial<UnidadeColecao>): ColecaoMap {
  return aplica(id, (it) => {
    const unids = [...(it.unidades || [])];
    if (idx < 0 || idx >= unids.length) return it;
    unids[idx] = { ...unids[idx], ...patch };
    return { ...it, unidades: unids };
  });
}

/** Atalho: define/limpa a graduação de uma unidade. */
export function setGraduacao(id: string, idx: number, grad: Grading | null): ColecaoMap {
  return setUnidade(id, idx, { grad });
}

/** Atalho: define a condição de uma unidade. */
export function setCondicao(id: string, idx: number, cond: Condicao | undefined): ColecaoMap {
  return setUnidade(id, idx, { cond });
}

/** Acrescenta uma unidade ao item (no fim). */
export function addUnidade(id: string, unidade?: UnidadeColecao): ColecaoMap {
  return aplica(id, (it) => ({
    ...it,
    unidades: [...(it.unidades || []), unidade ? { ...unidade } : {}],
  }));
}

/** Remove a unidade `idx` (item vazio sai da coleção). */
export function removeUnidade(id: string, idx: number): ColecaoMap {
  return aplica(id, (it) => {
    const unids = [...(it.unidades || [])];
    if (idx < 0 || idx >= unids.length) return it;
    unids.splice(idx, 1);
    return { ...it, unidades: unids };
  });
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

/** Importa de um JSON (substitui). Aceita o formato antigo (só qtd). */
export function importarColecao(mapa: ColecaoMap): ColecaoMap {
  const norm: ColecaoMap = {};
  for (const [k, v] of Object.entries(mapa || {})) {
    if (!v || typeof v !== 'object') continue;
    norm[k] = normaliza({ ...(v as ColecaoItem), id: (v as ColecaoItem).id || k });
  }
  writeAll(norm);
  return norm;
}

/** Exporta p/ download JSON. */
export function exportarJSON(map: ColecaoMap): string {
  return JSON.stringify(map, null, 2);
}

/** Lista de itens em ordem de inserção. */
export function listarColecao(map: ColecaoMap): ColecaoItem[] {
  return Object.values(map).map(normaliza);
}

export function totalCartas(map: ColecaoMap): number {
  return Object.values(map).reduce((acc, it) => acc + (it.qtd || 1), 0);
}

/** Quantas unidades da coleção estão marcadas como graduadas. */
export function totalGraduadas(map: ColecaoMap): number {
  return listarColecao(map).reduce(
    (acc, it) => acc + unidadesDe(it).filter((u) => !!u.grad?.emp).length,
    0
  );
}

/**
 * Valor da coleção. 'estimado' = preço justo do modelo (pred BRL), 'real' =
 * preço de mercado escorado — ambos só fazem sentido para unidades RAW (o
 * modelo aprendeu preço de anúncio comum, não de carta graduada).
 *
 * Unidades GRADUADAS entram em `realGraduado`, usando a referência de mercado
 * dos ANÚNCIOS GRADUADOS da Liga (min/mediana/max). Sem dado de graduação para
 * aquela empresa, a unidade não é somada e conta em `nSemRefGrad` — nunca
 * inventamos um preço de graduada a partir do raw.
 */
export interface ValorColecao {
  estimado: number;      // soma dos preços justos (BRL) das unidades raw
  real: number;          // soma dos preços reais escorados (BRL) das unidades raw
  realGraduado: number;  // soma da referência de mercado das unidades graduadas
  nGraduadas: number;    // unidades graduadas na coleção
  nSemRefGrad: number;   // unidades graduadas sem referência de mercado
  upsidePct: number;     // (estimado-real)/real × 100 (só raw)
  nComPreco: number;     // unidades raw com preço resolvido
  nTotal: number;        // unidades na coleção
}

/** Constrói o valor a partir de funções de lookup (injetadas p/ testar). */
export function calcularValor(
  itens: ColecaoItem[],
  preco: (id: string) => { real?: number | null; estimado?: number | null } | null,
  gradRef?: (id: string, empresa?: string | null) => number | null
): ValorColecao {
  let estimado = 0, real = 0, realGraduado = 0, nCom = 0, nGrad = 0, nSemRef = 0, nTotal = 0;
  for (const it of itens) {
    const unids = unidadesDe(it);
    const p = preco(it.id);
    for (const u of unids) {
      nTotal++;
      if (u.grad?.emp) {
        nGrad++;
        const ref = gradRef ? gradRef(it.id, u.grad.emp) : null;
        if (ref != null && ref > 0) realGraduado += ref;
        else nSemRef++;
        continue;
      }
      if (p) {
        const r = Number(p.real) || 0;
        const e = Number(p.estimado) || 0;
        real += r;
        estimado += e;
        if (r > 0 || e > 0) nCom++;
      }
    }
  }
  const upsidePct = real > 0 ? ((estimado - real) / real) * 100 : 0;
  return {
    estimado,
    real,
    realGraduado,
    nGraduadas: nGrad,
    nSemRefGrad: nSemRef,
    upsidePct,
    nComPreco: nCom,
    nTotal,
  };
}
