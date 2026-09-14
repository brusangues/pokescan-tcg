/**
 * grading.ts — condição, tipo, idioma e graduação por unidade da coleção (P2.43/P2.44).
 *
 * Vocabulário compartilhado com a Liga:
 *  - CONDICAO = `qualid` dos anúncios (1=M, 2=NM, 3=SP, 4=MP, 5=HP, 6=D, 0=graduada);
 *  - TIPO = `extras` dos anúncios (0=Normal, 2=Foil/Holo, resto=especiais como
 *    reverse/1st ed.) — casa com o preço por tipo do `v3m` (`n`/`f`) e com o
 *    preço por condição (`v3m.pc`);
 *  - IDIOMA — a mesma carta em PT/EN/JP são UNIDADES diferentes (a chave da
 *    coleção é a carta, não a carta+idioma).
 *
 * Regra de honestidade: anúncio é OFERTA, não venda concretizada. Todo rótulo
 * derivado daqui diz "anúncio".
 */

export type Condicao = 'M' | 'NM' | 'SP' | 'MP' | 'HP' | 'D';

export const CONDICOES: { v: Condicao; rotulo: string }[] = [
  { v: 'M', rotulo: 'M — Mint (perfeita)' },
  { v: 'NM', rotulo: 'NM — Near Mint (quase perfeita)' },
  { v: 'SP', rotulo: 'SP — leves sinais de uso' },
  { v: 'MP', rotulo: 'MP — sinais moderados' },
  { v: 'HP', rotulo: 'HP — muito desgastada' },
  { v: 'D', rotulo: 'D — danificada' },
];

export const TIPOS = [
  { v: 'N', rotulo: 'Normal' },
  { v: 'F', rotulo: 'Foil/Holo' },
  { v: 'O', rotulo: 'Especial (reverse, 1st ed…)' },
] as const;
export type Tipo = (typeof TIPOS)[number]['v'];

export const IDIOMAS = ['PT', 'EN', 'JP'] as const;
export type Idioma = (typeof IDIOMAS)[number];

export const EMPRESAS = ['PSA', 'CGC', 'BGS', 'AGS', 'Outra'] as const;
export type Empresa = (typeof EMPRESAS)[number];

export interface Grading {
  emp: string;   // PSA / CGC / BGS / AGS / Outra
  esc?: string;  // escala informada pela certificadora (ex: 'GEM-MT 10')
}

export interface UnidadeColecao {
  cond?: Condicao;
  tipo?: Tipo;         // Normal / Foil / especial
  lang?: Idioma;       // PT / EN / JP (unidades distintas da mesma carta)
  pago?: number;       // quanto o dono pagou nesta unidade (R$) — base do lucro
  grad?: Grading | null;
}

export interface GradedRef {
  empresa: string | null;   // null = todas as empresas
  escala: string | null;    // escala casada (quando houve)
  n: number;
  menor: number;
  mediana: number;
  maior: number;
  exato: boolean;           // true = mesma empresa E mesma escala
}

/** Referência de preço dos anúncios POR CONDICAO/TIPO (`v3m.pc`). */
export interface CondRef {
  cond: string | null;      // condição da referência (null = qualquer)
  tipo: string | null;      // tipo da referência (null = qualquer)
  n: number;
  menor: number;
  mediana: number;
  maior: number;
  exato: boolean;           // true = casou a condição E o tipo pedidos
}

type Amostras = [string, string, number][] | undefined | null;
type Pc = Record<string, Record<string, number[]>> | undefined | null;

export function rotuloTipo(t?: string | null): string {
  return TIPOS.find((x) => x.v === t)?.rotulo || (t || '');
}

/** Agrupa amostras [[empresa, escala, preco]] por empresa (maior n primeiro). */
export function agrupaGraduadas(amostras: Amostras): Map<string, GradedRef> {
  const m = new Map<string, GradedRef & { precos: number[] }>();
  for (const a of amostras || []) {
    const preco = Number(a?.[2]);
    if (!isFinite(preco) || preco <= 0) continue;
    const emp = (a[0] || 'Outra').toUpperCase();
    const cur = m.get(emp) ||
      { empresa: emp, escala: null, n: 0, menor: Infinity, mediana: 0, maior: 0, exato: false, precos: [] };
    cur.n += 1;
    cur.menor = Math.min(cur.menor, preco);
    cur.maior = Math.max(cur.maior, preco);
    cur.precos.push(preco);
    m.set(emp, cur);
  }
  const saida = new Map<string, GradedRef>();
  for (const [emp, v] of m) {
    v.precos.sort((a, b) => a - b);
    v.mediana = v.precos[Math.floor((v.precos.length - 1) / 2)];
    saida.set(emp, {
      empresa: v.empresa, escala: null, n: v.n, menor: v.menor,
      mediana: v.mediana, maior: v.maior, exato: false,
    });
  }
  return saida;
}

/**
 * Referência de mercado de uma unidade graduada:
 *  1. mesma certificadora E mesma escala (exato);
 *  2. mesma certificadora (qualquer escala);
 *  3. todas as certificadoras.
 * O rótulo na UI precisa dizer qual dos três foi usado.
 */
export function referenciaGraduada(
  amostras: Amostras,
  empresa?: string | null,
  escala?: string | null
): GradedRef | null {
  const validas = (amostras || []).filter((a) => {
    const p = Number(a?.[2]);
    return isFinite(p) && p > 0;
  });
  if (validas.length === 0) return null;
  const agrega = (arr: typeof validas, emp: string | null, esc: string | null, exato: boolean): GradedRef => {
    const precos = arr.map((a) => Number(a[2])).sort((x, y) => x - y);
    return {
      empresa: emp,
      escala: esc,
      n: precos.length,
      menor: precos[0],
      mediana: precos[Math.floor((precos.length - 1) / 2)],
      maior: precos[precos.length - 1],
      exato,
    };
  };
  const alvo = (empresa || '').toUpperCase();
  const escAlvo = (escala || '').trim().toLowerCase();
  if (alvo) {
    const daEmp = validas.filter((a) => ((a[0] || 'Outra').toUpperCase() === alvo));
    if (daEmp.length) {
      if (escAlvo) {
        const daEsc = daEmp.filter((a) => (a[1] || '').trim().toLowerCase() === escAlvo);
        if (daEsc.length) return agrega(daEsc, alvo, escala!.trim(), true);
      }
      return agrega(daEmp, alvo, null, false);
    }
  }
  return agrega(validas, null, null, false);
}

/**
 * Referência de preço para uma unidade NÃO graduada, a partir do `pc`
 * (preço dos anúncios por condição × tipo). Cadeia de fallback explícita:
 *  1. mesma condição + mesmo tipo (exato);
 *  2. mesma condição, qualquer tipo (N → F → O);
 *  3. mesmo tipo, qualquer condição (na ordem da escala);
 *  4. o balde com mais anúncios.
 * Nunca devolve número sem dizer de onde veio (cond/tipo/exato).
 */
export function referenciaCondicao(
  pc: Pc,
  cond?: string | null,
  tipo?: string | null
): CondRef | null {
  const val = (c?: string | null, t?: string | null): number[] | null => {
    if (!pc || !c || !t) return null;
    const v = pc[c]?.[t];
    if (!Array.isArray(v) || v.length < 4) return null;
    return isFinite(Number(v[2])) && Number(v[2]) > 0 ? v : null;
  };
  const mk = (v: number[], c: string | null, t: string | null, exato: boolean): CondRef => ({
    cond: c, tipo: t, n: Number(v[0]) || 0, menor: Number(v[1]),
    mediana: Number(v[2]), maior: Number(v[3]), exato,
  });
  const C = (cond || '').toUpperCase() || null;
  const T = (tipo || '').toUpperCase() || null;
  let v = val(C, T);
  if (v) return mk(v, C, T, true);
  if (C) {
    for (const t of ['N', 'F', 'O']) {
      v = val(C, t);
      if (v) return mk(v, C, t, false);
    }
  }
  if (T) {
    for (const c of CONDICOES.map((x) => x.v)) {
      v = val(c, T);
      if (v) return mk(v, c, T, false);
    }
  }
  let melhor: { v: number[]; c: string; t: string; n: number } | null = null;
  for (const [c, ts] of Object.entries(pc || {})) {
    for (const [t, arr] of Object.entries(ts || {})) {
      if (!Array.isArray(arr) || arr.length < 4) continue;
      const n = Number(arr[0]) || 0;
      if (!melhor || n > melhor.n) melhor = { v: arr, c, t, n };
    }
  }
  return melhor ? mk(melhor.v, melhor.c, melhor.t, false) : null;
}

/** Rótulo curto de uma unidade: 'PSA GEM-MT 10' | 'NM · Foil · EN' | '—'. */
export function rotuloUnidade(u?: UnidadeColecao | null): string {
  if (!u) return '—';
  if (u.grad?.emp) return [u.grad.emp, u.grad.esc].filter(Boolean).join(' ');
  const partes = [
    u.cond,
    u.tipo ? (u.tipo === 'N' ? 'Normal' : u.tipo === 'F' ? 'Foil' : 'Especial') : null,
    u.lang,
  ].filter(Boolean);
  return partes.length ? partes.join(' · ') : '—';
}

/** Unidades de um item: 'unidades' quando existir, senão qtd unidades vazias. */
export function unidadesDe(item: { qtd?: number; unidades?: UnidadeColecao[] }): UnidadeColecao[] {
  if (Array.isArray(item.unidades) && item.unidades.length > 0) return item.unidades;
  const n = Math.max(0, Number(item.qtd) || 0);
  return Array.from({ length: n }, () => ({}));
}
