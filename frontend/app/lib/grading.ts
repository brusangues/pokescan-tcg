/**
 * grading.ts — condição por unidade e graduação (P2.43).
 *
 * Duas coisas vivem aqui:
 *  1. o vocabulário de CONDICAO (o mesmo `qualid` que a Liga usa nos anúncios:
 *     1=M, 2=NM, 3=SP, 4=MP, 5=HP, 6=D) para a coleção pessoal;
 *  2. a leitura dos ANÚNCIOS GRADUADOS coletados na página da carta da Liga
 *     (`gr` no cards.json: {n, e:[[empresa, escala, preco], ...]}) — base da
 *     referência de mercado de uma unidade graduada.
 *
 * Regra de honestidade: anúncio graduado é ANÚNCIO (oferta), não venda
 * concretizada. O rótulo diz isso; nunca apresentar como preço de venda.
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

export const EMPRESAS = ['PSA', 'CGC', 'BGS', 'AGS', 'Outra'] as const;
export type Empresa = (typeof EMPRESAS)[number];

export interface Grading {
  emp: string;   // PSA / CGC / BGS / AGS / Outra
  esc?: string;  // escala informada pela certificadora (ex: 'GEM-MT 10')
}

export interface UnidadeColecao {
  cond?: Condicao;
  grad?: Grading | null;
}

export interface GradedRef {
  empresa: string | null;   // null = todas as empresas
  n: number;
  menor: number;
  mediana: number;
  maior: number;
}

/** Agrupa amostras [[empresa, escala, preco]] por empresa (maior n primeiro). */
export function agrupaGraduadas(
  amostras: [string, string, number][] | undefined | null
): Map<string, GradedRef> {
  const m = new Map<string, GradedRef & { precos: number[] }>();
  for (const a of amostras || []) {
    const preco = Number(a?.[2]);
    if (!isFinite(preco) || preco <= 0) continue;
    const emp = (a[0] || 'Outra').toUpperCase();
    const cur = m.get(emp) || { empresa: emp, n: 0, menor: Infinity, mediana: 0, maior: 0, precos: [] };
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
    saida.set(emp, { empresa: v.empresa, n: v.n, menor: v.menor, mediana: v.mediana, maior: v.maior });
  }
  return saida;
}

/**
 * Referência de mercado para uma unidade graduada. Prioriza os anúncios da
 * MESMA empresa; se não houver, cai para o conjunto todo (empresa=null) —
 * o rótulo na UI deve refletir qual dos dois foi usado.
 */
export function referenciaGraduada(
  amostras: [string, string, number][] | undefined | null,
  empresa?: string | null
): GradedRef | null {
  const g = agrupaGraduadas(amostras);
  if (g.size === 0) return null;
  const alvo = (empresa || '').toUpperCase();
  if (alvo && g.has(alvo)) return g.get(alvo)!;
  const todos: number[] = [];
  let n = 0, menor = Infinity, maior = 0;
  for (const a of amostras || []) {
    const p = Number(a?.[2]);
    if (!isFinite(p) || p <= 0) continue;
    n += 1; menor = Math.min(menor, p); maior = Math.max(maior, p); todos.push(p);
  }
  if (!n) return null;
  todos.sort((a, b) => a - b);
  return {
    empresa: null,
    n,
    menor,
    mediana: todos[Math.floor((todos.length - 1) / 2)],
    maior,
  };
}

/** Rótulo curto de uma unidade da coleção: 'PSA GEM-MT 10' | 'NM' | '—'. */
export function rotuloUnidade(u?: UnidadeColecao | null): string {
  if (!u) return '—';
  if (u.grad?.emp) return [u.grad.emp, u.grad.esc].filter(Boolean).join(' ');
  if (u.cond) return u.cond;
  return '—';
}

/** Unidades de um item: 'unidades' quando existir, senão qtd unidades vazias. */
export function unidadesDe(item: { qtd?: number; unidades?: UnidadeColecao[] }): UnidadeColecao[] {
  if (Array.isArray(item.unidades) && item.unidades.length > 0) return item.unidades;
  const n = Math.max(0, Number(item.qtd) || 0);
  return Array.from({ length: n }, () => ({}));
}
