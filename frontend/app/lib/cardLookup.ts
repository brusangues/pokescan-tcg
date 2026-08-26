/**
 * cardLookup.ts — lookup de cartas 100% client-side para o export estático.
 * Réplica da lógica da antiga API /api/card usando os JSONs estáticos
 * gerados por script/build_static_data.py em public/data/.
 *
 * Estratégias (mesma ordem da API):
 *  1. liga_id → set_map[liga] → cards por id (set-num)
 *  2. set + num direto → cards por id
 *  3. nome (+ filtro de set via sigla/setId)
 *  4. nome global (substring) — último recurso
 */
import { getBasePath } from './basePath';

let _cards: any[] | null = null;
let _cardsById: Map<string, any> | null = null;
let _setMap: Record<string, string> | null = null;
let _scored: any[] | null = null;
let _detalheIndex: Record<string, string> | null = null;
let _detalheCache: Record<string, any[]> = {};
let _promises: Record<string, Promise<any>> = {};

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Falha ao carregar ${url}`);
  return res.json() as Promise<T>;
}

function base(url: string) {
  return `${getBasePath()}${url}`;
}

/** Catálogo básico (id, n, s, sn, num, r, p, img) — ~3.4 MB, cacheado. */
export async function loadCards(): Promise<Map<string, any>> {
  if (_cardsById) return _cardsById;
  if (!_promises.cards) {
    _promises.cards = getJson<any[]>(base('/data/cards.json')).then((cards) => {
      _cards = cards;
      _cardsById = new Map(cards.map((c) => [c.id, c]));
      return _cardsById;
    });
  }
  return _promises.cards;
}

/** Mapeamento invertido sigla→set ptcg (214 entradas). */
export async function loadSetMap(): Promise<Record<string, string>> {
  if (_setMap) return _setMap;
  if (!_promises.setMap) {
    _promises.setMap = getJson<Record<string, string>>(base('/data/set_map.json')).then((m) => {
      _setMap = m;
      return m;
    });
  }
  return _promises.setMap;
}

/** Registros escorados mais recentes (hits + snapshot) para o bloco modelo. */
export async function loadScoredLatest(): Promise<any[]> {
  if (_scored) return _scored;
  if (!_promises.scored) {
    _promises.scored = getJson<any[]>(base('/data/scored_latest.json')).then((s) => {
      _scored = s;
      return s;
    });
  }
  return (await _promises.scored) as any[];
}

/** Predição BRL Liga-first p/ TODA carta do catálogo da Liga ({idE}-{num}). */
let _predLiga: Record<string, { pred: number; real: number | null; sigla?: string; iCO?: number }> | null = null;

export async function loadPredLiga() {
  if (_predLiga) return _predLiga;
  if (!_promises.predLiga) {
    _promises.predLiga = getJson<Record<string, { pred: number; real: number | null; sigla?: string; iCO?: number }>>(
      base('/data/pred_liga.json')
    );
  }
  const p = (await _promises.predLiga) as Record<string, { pred: number; real: number | null; sigla?: string; iCO?: number }>;
  _predLiga = p;
  return p;
}

/** Índice id→chunk do detalhe. */
async function loadDetalheIndex(): Promise<Record<string, string>> {
  if (_detalheIndex) return _detalheIndex;
  if (!_promises.detalheIndex) {
    _promises.detalheIndex = getJson<Record<string, string>>(base('/data/carddetail/index.json')).then((idx) => {
      _detalheIndex = idx;
      return idx;
    });
  }
  return _promises.detalheIndex;
}

/** Detalhe completo de uma carta (carrega só o chunk da letra do nome). */
export async function loadCardDetalhe(id: string): Promise<any | null> {
  const idx = await loadDetalheIndex();
  const letra = idx[id];
  if (!letra) return null;
  if (_detalheCache[letra]) {
    return _detalheCache[letra].find((c: any) => c.id === id) || null;
  }
  if (!_promises[`detalhe_${letra}`]) {
    _promises[`detalhe_${letra}`] = getJson<any[]>(base(`/data/carddetail/${letra}.json`)).then(
      (cards) => {
        _detalheCache[letra] = cards;
        return cards;
      }
    );
  }
  const cards = await _promises[`detalhe_${letra}`];
  return cards.find((c: any) => c.id === id) || null;
}

/** Normaliza nome p/ comparação: minúsculas + remove pontuação/hífens/espaços
 *  ('Alolan Exeggutor-V' == 'Alolan Exeggutor V' == 'alolanexeggutorv'). */
export function normNome(n: string): string {
  return (n || '').toLowerCase().replace(/[^a-z0-9]/g, '');
}

/** Monta o objeto `modelo` do fallback Liga-first (mesmo shape do escorado). */
function montarModeloLiga(
  hit: { pred: number; real: number | null; sigla?: string; iCO?: number },
  chave: string,
  upside: number
) {
  return {
    real: hit.real ?? hit.pred,
    pred: hit.pred,
    upside,
    oportunidade:
      upside > 25 ? '🔥 Subvalorizada' : upside > 10 ? '👍 Leve Desconto' : upside < -25 ? '💀 Inflacionada' : '⚖️ Preço Justo',
    iCO: hit.iCO ?? 0,
    moeda: 'R$',
    liga_id: chave,
    card_id: '',
    nEN: '',
    sNumber: '',
    num: chave.split('-')[1] || '',
    sigla: hit.sigla || '',
    setNome: '',
    fonte: 'Modelo PokéScan',
    is_jp: false,
    ligaOk: true,
  };
}

/**
 * Busca a carta pelos mesmos parâmetros da antiga API:
 * { nome?, sigla?, num?, set?, liga_id? } → carta básica + detalhe + modelo.
 * Retorna o MESMO shape do antigo /api/card (CardData no CardDetailContent).
 */
export async function lookupCard(params: {
  nome?: string | null;
  sigla?: string | null;
  num?: string | null;
  set?: string | null;
  liga_id?: string | null;
  card_id?: string | null;
}): Promise<any> {
  const [byId, setMap] = await Promise.all([loadCards(), loadSetMap()]);

  const sigla = (params.sigla || (params.liga_id ? params.liga_id.split('-')[0] : ''))
    ?.toLowerCase() || '';
  let card = null;

  // Estratégia 0 (preferida): card_id canônico '{idE}-{lang}-{num}' — ex: '411-en-4'.
  // setMap['411'] → set ptcg (o edicoes_liga.json entra no set_map como idE→set).
  // SÓ para lang 'en': a numeração JP ≠ EN (ex: PGOJP 72 = Exeggutor-V, mas o
  // pgo-72 EN é o Mewtwo V) — card_id jp resolve pelo fallback scored (nome).
  if (params.card_id) {
    const parts = params.card_id.split('-');
    const eid = parts[0];
    const lang = parts[1];
    const number = parts[2] ?? parts[1];
    const ptcgSet = setMap[eid];
    if (lang !== 'jp' && ptcgSet && number) {
      card = byId.get(`${ptcgSet}-${number}`) || byId.get(`${ptcgSet}-${parseInt(number)}`);
    }
  }

  // Estratégia 1: liga_id legado ('SIGLA-num') — links antigos continuam funcionando
  if (!card && params.liga_id) {
    const number = params.liga_id.split('-')[1];
    const ptcgSet = setMap[sigla];
    if (ptcgSet) {
      card = byId.get(`${ptcgSet}-${number}`) || byId.get(`${ptcgSet}-${parseInt(number)}`);
    }
  }

  // Estratégia 2: set + num direto
  if (!card && params.set && params.num) {
    card = byId.get(`${params.set}-${params.num}`);
  }

  // Estratégia 3: nome com filtro de set
  if (!card && params.nome) {
    const nomeBusca = normNome(params.nome);
    const ptcgSet = sigla ? setMap[sigla] : (params.set || '');
    const cards = [...byId.values()];
    if (ptcgSet) {
      card = cards.find((c) => normNome(c.n) === nomeBusca && c.s === ptcgSet) || null;
    } else {
      card = cards.find((c) => normNome(c.n) === nomeBusca) || null;
    }
    if (!card) {
      // Estratégia 4: nome global com igualdade
      card = cards.find((c) => {
        const n = normNome(c.n || '');
        return n === nomeBusca;
      }) || null;
    }
  }

  // Estratégia 5: card_id de edição SEM set mapeado (ex: '298-en-13' — set antigo
  // sem equivalente no catálogo ptcg): procura o registro escorado pelo card_id
  // e resolve pelo nome+sigla dele.
  if (!card && params.card_id) {
    const scoredCards = await loadScoredLatest();
    const reg = scoredCards.find((s: any) => s.card_id === params.card_id);
    if (reg) {
      // nEN tem o nome EN (ex: 'Alolan Exeggutor-V (#072/071)') — o nome PT não
      // casa com o catálogo (que é EN); normNome ignora hífen/espaço
      const nomeBusca = normNome(String(reg.nEN || reg.nome || '').split('(')[0]);
      const ptcgSet = reg.sigla ? setMap[String(reg.sigla).toLowerCase()] : '';
      const cards = [...byId.values()];
      if (nomeBusca && ptcgSet) {
        card = cards.find((c) => normNome(c.n) === nomeBusca && c.s === ptcgSet) || null;
      }
      if (!card && nomeBusca) {
        card = cards.find((c) => normNome(c.n) === nomeBusca) || null;
      }
    }
  }

  if (!card) {
    throw new Error('Carta não encontrada no catálogo');
  }

  // Detalhe completo (ataques, habilidades, preços detalhados…)
  const detalhe = await loadCardDetalhe(card.id);

  // Registro escorado (modelo) — mesmo critério da API: nome exato (EN via nEN
  // — o nome PT não casa com o catálogo), priorizando sigla igual + registro
  // mais rico (setNome/sNumber/nEN); normNome ignora hífen/espaço.
  // Quando a página veio por card_id, o modelo é o REGISTRO DAQUELE card_id
  // (o mesmo Pokémon pode ter 2 numerações na Liga — ex: PGOJP Exeggutor-V
  // como 005 e 072 — o link da Liga deve usar a do registro clicado).
  const scoredCards = await loadScoredLatest();
  let scored = null;
  if (params.card_id) {
    scored = scoredCards.find((s: any) => s.card_id === params.card_id) || null;
  }
  const nomeCard = normNome(card.n || '');
  const nomeScored = (s: any) =>
    normNome(String(s.nEN || s.nome || '').split('(')[0]);
  if (!scored) {
    // Bônus forte quando o SET do registro bate com o set da página já
    // resolvida (card.s) — ex.: /card?set=me3&num=50 resolve a carta no set
    // ptcg 'me3'; o registro escorado certo tem sigla Liga 'POR' e o setMap
    // (que tem siglas Liga como CHAVE: 'por'->'me3') confirma o par.
    // Sem isso, um hit homônimo de outro set ganhava o desempate e mostrava
    // preço/set errados.
    const setDaPagina = card.s;
    const setDoRegistro = (s: any) => String(setMap[String(s.sigla || '').toLowerCase()] || '');
    scored = scoredCards
      .filter((s: any) => nomeScored(s) === nomeCard)
      .sort((a: any, b: any) => {
        const sigA = a.sigla?.toLowerCase() === sigla ? 1 : 0;
        const sigB = b.sigla?.toLowerCase() === sigla ? 1 : 0;
        const setA = setDoRegistro(a) === setDaPagina ? 1 : 0;
        const setB = setDoRegistro(b) === setDaPagina ? 1 : 0;
        const richA = (a.setNome ? 1 : 0) + (a.sNumber ? 1 : 0) + (a.nEN ? 1 : 0);
        const richB = (b.setNome ? 1 : 0) + (b.sNumber ? 1 : 0) + (b.nEN ? 1 : 0);
        return (sigB - sigA) * 10 + (setB - setA) * 9 + (richB - richA);
      })[0] || null;
    // Guard final: NÃO emprestar preço de homônimo de outro set. Se nenhum
    // candidato é do set da página, o registro "mais rico" seria de outra
    // carta — mostrar seu preço como se fosse desta é pior que não mostrar.
    // (Auditoria: ~7.4k páginas sem cobertura no snapshot caíam aqui.)
    if (scored && setDoRegistro(scored) !== setDaPagina) {
      scored = null;
    }
  }

  const ligaOk = scored?.is_jp
    ? true
    : scored?.sigla
      ? (setMap[String(scored.sigla).toLowerCase()] === (detalhe?.set?.id || card.s) ||
         !setMap[String(scored.sigla).toLowerCase()])
      : false;

  // Liga-only (pt-BR): a carta exibida vem do catálogo da LIGA. Um registro
  // escorado homônimo de OUTRO set (ex. "Rowlet" SM) não é a escoragem desta —
  // não anexar (evita link da Liga errado + preço de outra carta na página).
  if ((card as any).liga_nen && scored &&
      String((scored as any).sigla || '').toLowerCase() !== String(card.s || '').toLowerCase()) {
    scored = null;
  }

  return {
    id: card.id,
    name: (card as any).nPT || detalhe?.name || card.n,
    // Liga-first (P1.33): nome pt-BR (quando tem) + EN p/ tooltip
    nPT: (card as any).nPT || null,
    nEN: (card as any).nEN || null,
    // Liga-first (pt-BR): campos do catálogo da LIGA (link "Ver na Liga" + BRL)
    liga_nen: (card as any).liga_nen || null,
    liga_ico: (card as any).liga_ico ?? null,
    moeda: (card as any).moeda || 'USD',
    preco_brl: typeof (card as any).p === 'number' ? (card as any).p : parseFloat((card as any).p) || null,
    supertype: detalhe?.supertype,
    subtypes: detalhe?.subtypes,
    hp: detalhe?.hp,
    types: detalhe?.types,
    evolvesFrom: detalhe?.evolvesFrom,
    evolvesTo: detalhe?.evolvesTo,
    rarity: detalhe?.rarity || card.r,
    artist: detalhe?.artist,
    number: detalhe?.number || card.num,
    set: detalhe?.set || { id: card.s, name: card.sn },
    images: detalhe?.images || { small: card.img, large: card.img?.replace('small', 'large') },
    tcgplayer: detalhe?.tcgplayer,
    cardmarket: detalhe?.cardmarket,
    previsao_semana: detalhe?.previsao_semana,
    tendencia_pct: detalhe?.tendencia_pct,
    flavorText: detalhe?.flavorText,
    attacks: detalhe?.attacks,
    abilities: detalhe?.abilities,
    weaknesses: detalhe?.weaknesses,
    resistances: detalhe?.resistances,
    retreatCost: detalhe?.retreatCost,
    modelo: scored
      ? {
          real: scored.real,
          pred: scored.pred,
          upside: scored.upside,
          oportunidade: scored.oportunidade,
          iCO: scored.iCO,
          moeda: scored.moeda,
          liga_id: scored.liga_id,
          card_id: scored.card_id || '',
          nEN: scored.nEN,
          sNumber: scored.sNumber,
          num: scored.num,
          sigla: scored.sigla,
          setNome: scored.setNome,
          fonte: scored.fonte,
          is_jp: scored.is_jp || false,
          ligaOk,
        }
      : await (async () => {
          // Fallback PokéScan: sem escoragem do próprio set, usa a predição
          // do modelo BRL treinado no catálogo da Liga ({idE}-{num}) + preço
          // real da Liga quando houver. Resolve pela carta EN ({set_ptcg}-{num},
          // alias gerado no pred_liga.json) — direto, sem depender do setMap.
          const pl = await loadPredLiga() as Record<string, { pred: number; real: number | null; sigla?: string; iCO?: number }> | null;
          if (!pl) return null;
          const numN = parseInt(params.num || card.num || '', 10);
          const chave = isNaN(numN) ? null : `${card.s}-${numN}`;
          const hit = chave ? pl[chave] : null;
          if (!hit) {
            // sem alias EN: tenta a chave canônica {idE}-{num} via setMap
            const eidLiga = Object.entries(setMap).find(([k, v]) => v === card.s && /^\d+$/.test(k))?.[0];
            const k2 = eidLiga ? `${eidLiga}-${numN}` : null;
            if (!k2 || !pl[k2]) return null;
            const h2 = pl[k2];
            const up2 = h2.real ? ((h2.pred - h2.real) / h2.real) * 100 : 0;
            return montarModeloLiga(h2, k2, up2);
          }
          const upside0 = hit.real ? ((hit.pred - hit.real) / hit.real) * 100 : 0;
          return montarModeloLiga(hit, chave!, upside0);
        })(),
  };
}

/** Série de histórico da carta — réplica do /api/historico (client-side). */
export async function lookupHistorico(params: {
  cardId?: string;
  ligaId?: string;
  nome?: string;
  sigla?: string;
}): Promise<{ serie: any[]; total: number; liga_id: string }> {
  if (!_promises.historico) {
    _promises.historico = getJson(base('/data/historico.json'));
  }
  const hist = await _promises.historico;

  let serie: any[] = [];
  if (params.cardId) {
    serie = hist.porLiga[params.cardId] || [];
  } else if (params.ligaId) {
    serie = hist.porLiga[params.ligaId] || [];
  } else if (params.nome) {
    const siglas = hist.porNome[params.nome.toLowerCase()] || {};
    if (params.sigla) {
      serie = siglas[params.sigla] || [];
    } else {
      serie = Object.values(siglas).flat().sort((a: any, b: any) => a.data.localeCompare(b.data));
    }
  }
  if (serie.length > 60) serie = serie.slice(-60);
  return {
    serie,
    total: serie.length,
    liga_id: params.cardId || params.ligaId || (params.sigla ? `${params.sigla}-` : ''),
  };
}
