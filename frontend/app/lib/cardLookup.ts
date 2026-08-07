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
  return _promises.scored;
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
  if (params.card_id) {
    const parts = params.card_id.split('-');
    const eid = parts[0];
    const number = parts[2] ?? parts[1];
    const ptcgSet = setMap[eid];
    if (ptcgSet && number) {
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
    const nomeBusca = params.nome.toLowerCase();
    const ptcgSet = sigla ? setMap[sigla] : (params.set || '');
    const cards = [...byId.values()];
    if (ptcgSet) {
      card = cards.find((c) => c.n?.toLowerCase() === nomeBusca && c.s === ptcgSet) || null;
    } else {
      card = cards.find((c) => c.n?.toLowerCase() === nomeBusca) || null;
    }
    if (!card) {
      // Estratégia 4: nome global com igualdade
      card = cards.find((c) => {
        const n = c.n?.toLowerCase() || '';
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
      const nomeBusca = String(reg.nome || reg.nEN || '').toLowerCase().split('(')[0].trim();
      const ptcgSet = reg.sigla ? setMap[String(reg.sigla).toLowerCase()] : '';
      const cards = [...byId.values()];
      if (nomeBusca && ptcgSet) {
        card = cards.find((c) => c.n?.toLowerCase() === nomeBusca && c.s === ptcgSet) || null;
      }
      if (!card && nomeBusca) {
        card = cards.find((c) => c.n?.toLowerCase() === nomeBusca) || null;
      }
    }
  }

  if (!card) {
    throw new Error('Carta não encontrada no catálogo');
  }

  // Detalhe completo (ataques, habilidades, preços detalhados…)
  const detalhe = await loadCardDetalhe(card.id);

  // Registro escorado (modelo) — mesmo critério da API: nome exato,
  // priorizando sigla igual + registro mais rico (setNome/sNumber/nEN)
  const scoredCards = await loadScoredLatest();
  const nomeCard = (card.n || '').toLowerCase();
  const scored = scoredCards
    .filter((s: any) => s.nome && s.nome.toLowerCase() === nomeCard)
    .sort((a: any, b: any) => {
      const sigA = a.sigla?.toLowerCase() === sigla ? 1 : 0;
      const sigB = b.sigla?.toLowerCase() === sigla ? 1 : 0;
      const richA = (a.setNome ? 1 : 0) + (a.sNumber ? 1 : 0) + (a.nEN ? 1 : 0);
      const richB = (b.setNome ? 1 : 0) + (b.sNumber ? 1 : 0) + (b.nEN ? 1 : 0);
      return (sigB - sigA) * 10 + (richB - richA);
    })[0] || null;

  const ligaOk = scored?.is_jp
    ? true
    : scored?.sigla
      ? (setMap[String(scored.sigla).toLowerCase()] === (detalhe?.set?.id || card.s) ||
         !setMap[String(scored.sigla).toLowerCase()])
      : false;

  return {
    id: card.id,
    name: detalhe?.name || card.n,
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
      : null,
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
