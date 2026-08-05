import { NextResponse } from 'next/server';
import { readFileSync, readdirSync, statSync } from 'fs';
import { parseScoredCSV } from '@/app/lib/scored';
import { PTCG_CACHE_PATH, SCORED_DIR, LIGA_DIR, SET_MAPPING_PATH, SET_MAPPING_FALLBACK_PATH } from '@/app/lib/paths';

export const dynamic = 'force-dynamic';

// Cache com invalidação por mtime: recarrega quando o arquivo mudar no
// disco (cron de hits das 07:00, refresh semanal do cache ptcg, etc.).
// Evita cache stale em servidor long-running.
let _cacheMap: Map<string, any> | null = null;
let _cacheMtime = 0;

function loadCache(): Map<string, any> {
  let mtime = 0;
  try {
    mtime = statSync(PTCG_CACHE_PATH).mtimeMs;
  } catch {
    /* arquivo sumiu — força recarga */
  }
  if (_cacheMap && _cacheMtime === mtime) return _cacheMap;

  const raw = readFileSync(PTCG_CACHE_PATH, 'utf-8');
  const cards = JSON.parse(raw);
  _cacheMap = new Map();
  for (const c of cards) {
    _cacheMap.set(String(c.id), c);
  }
  _cacheMtime = mtime;
  return _cacheMap;
}

// Carrega o CSV escorado mais recente (hits e snapshot) para cruzar
// com o modelo (pred_usd, pred_brl, upside, oportunidade, iCO).
let _scoredLatest: any[] | null = null;
let _scoredKey = '';

function _latestScoredKey(): string {
  try {
    const files = readdirSync(SCORED_DIR)
      .filter(f => /^scored_(hits|snapshot)_\d{8}_\d{6}\.csv$/.test(f))
      .sort()
      .reverse();
    if (files.length === 0) return '';
    const hits = files.find(f => f.startsWith('scored_hits_')) || files[0];
    const snap = files.find(f => f.startsWith('scored_snapshot_')) || '';
    // Key = nomes + mtimes dos 2 arquivos mais recentes
    const parts = [hits];
    if (snap && snap !== hits) parts.push(snap);
    return parts.map(f => `${f}:${statSync(`${SCORED_DIR}/${f}`).mtimeMs}`).join('|');
  } catch {
    return '';
  }
}

function loadScoredLatest(): any[] {
  const key = _latestScoredKey();
  if (_scoredLatest && _scoredKey === key) return _scoredLatest;

  const files = readdirSync(SCORED_DIR)
    .filter(f => /^scored_(hits|snapshot)_\d{8}_\d{6}\.csv$/.test(f))
    .sort()
    .reverse();
  const hits = files.find(f => f.startsWith('scored_hits_'));
  const snap = files.find(f => f.startsWith('scored_snapshot_'));

  const all: any[] = [];
  for (const f of [hits, snap]) {
    if (!f) continue;
    try {
      all.push(...parseScoredCSV(`${SCORED_DIR}/${f}`));
    } catch { /* ignora arquivo corrompido */ }
  }
  _scoredLatest = all;
  _scoredKey = key;
  return _scoredLatest;
}

function loadSetMapping(): Record<string, string> {
  // Arquivo mapeia set_id ptcg → sigla Liga (ex: "sv3pt5" → "MEW")
  // Precisamos do INVERSO (sigla Liga → set ptcg) para buscar no cache.
  try {
    const raw = JSON.parse(readFileSync(SET_MAPPING_PATH, 'utf-8'));
    const inv: Record<string, string> = {};
    for (const [ptcg, liga] of Object.entries(raw)) {
      inv[String(liga).toLowerCase()] = ptcg;
    }
    return inv;
  } catch {
    try {
      const raw = JSON.parse(readFileSync(SET_MAPPING_FALLBACK_PATH, 'utf-8'));
      const inv: Record<string, string> = {};
      for (const [ptcg, liga] of Object.entries(raw)) {
        inv[String(liga).toLowerCase()] = ptcg;
      }
      return inv;
    } catch {
      return {};
    }
  }
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const ligaId = searchParams.get('liga_id') || '';
    const setId = searchParams.get('set');
    const num = searchParams.get('num');
    const sigla = searchParams.get('sigla')?.toLowerCase() || (ligaId ? ligaId.split('-')[0].toLowerCase() : '');

    const cache = loadCache();
    const setMap = loadSetMapping();

    let card = null;

    // Estratégia 1: liga_id
    if (ligaId) {
      const parts = ligaId.split('-');
      const number = parts[1];
      const ptcgSet = setMap[sigla];
      if (ptcgSet) {
        card = cache.get(`${ptcgSet}-${number}`);
        if (!card) card = cache.get(`${ptcgSet}-${parseInt(number)}`);
      }
    }

    // Estratégia 2: set + num direto
    if (!card && setId && num) {
      card = cache.get(`${setId}-${num}`);
    }

    // Estratégia 3: busca por nome (para sem mapping)
    if (!card) {
      const nomeBusca = searchParams.get('nome')?.toLowerCase();
      if (nomeBusca) {
        // Determina ptcgSetId para filtrar pelo set.
        // Prioridade: sigla (query) → liga_id → setId
        const rawSigla = sigla || ligaId?.split('-')[0]?.toLowerCase() || '';
        const ptcgSet = rawSigla ? setMap[rawSigla] : (setId || '');
        for (const [key, c] of cache) {
          if (c.name?.toLowerCase() === nomeBusca && (!ptcgSet || String(key).startsWith(ptcgSet))) {
            card = c;
            break;
          }
        }
        // Se achou com filtro, ótimo. Senão tenta sem filtro (último recurso)
        // mas SEMPRE priorizando set com match de nome exato.
      }
    }

    if (!card) {
      const nomeBusca = searchParams.get('nome')?.toLowerCase();
      if (nomeBusca) {
        // Fallback global: busca por nome sem filtro de set
        for (const [key, c] of cache) {
          const n = c.name?.toLowerCase();
          const subt = c.subtitle?.toLowerCase() || '';
          if ((n.startsWith(nomeBusca) || n.endsWith(nomeBusca) || n.includes(nomeBusca)) && n === nomeBusca) {
            card = c;
            break;
          }
        }
      }
    }

    if (!card) {
      return NextResponse.json({ error: 'Carta não encontrada no cache', details: { ligaId, setId, num } }, { status: 404 });
    }

    // Cruza com o CSV escorado (modelo + dados Liga) por nome/sigla
    const scoredCards = loadScoredLatest();
    const nomeCard = (card.name || '').toLowerCase();
    // Prioriza registro com mais dados (setNome + sNumber) e sigla igual
    const scored = scoredCards
      .filter((s: any) => s.nome && s.nome.toLowerCase() === nomeCard)
      .sort((a: any, b: any) => {
        const sigA = a.sigla.toLowerCase() === sigla ? 1 : 0;
        const sigB = b.sigla.toLowerCase() === sigla ? 1 : 0;
        const richA = (a.setNome ? 1 : 0) + (a.sNumber ? 1 : 0) + (a.nEN ? 1 : 0);
        const richB = (b.setNome ? 1 : 0) + (b.sNumber ? 1 : 0) + (b.nEN ? 1 : 0);
        return (sigB - sigA) * 10 + (richB - richA);
      })[0];

    return NextResponse.json({
      id: card.id,
      name: card.name,
      supertype: card.supertype,
      subtypes: card.subtypes,
      hp: card.hp,
      types: card.types,
      evolvesFrom: card.evolvesFrom,
      evolvesTo: card.evolvesTo,
      rarity: card.rarity,
      artist: card.artist,
      number: card.number,
      set: {
        id: card.set.id,
        name: card.set.name,
        series: card.set.series,
        releaseDate: card.set.releaseDate,
        printedTotal: card.set.printedTotal,
      },
      images: card.images,
      tcgplayer: card.tcgplayer,
      cardmarket: card.cardmarket,
      flavorText: card.flavorText,
      attacks: card.attacks?.slice(0, 8),
      abilities: card.abilities,
      weaknesses: card.weaknesses,
      resistances: card.resistances,
      retreatCost: card.retreatCost,
      // Dados do modelo (do CSV escorado mais recente)
      modelo: scored ? {
        real: scored.real,
        pred: scored.pred,
        upside: scored.upside,
        oportunidade: scored.oportunidade,
        iCO: scored.iCO,
        moeda: scored.moeda,
        liga_id: scored.liga_id,
        nEN: scored.nEN,
        sNumber: scored.sNumber,
        num: scored.num,
        sigla: scored.sigla,
        setNome: scored.setNome,
        fonte: scored.fonte,
        is_jp: scored.is_jp || false,
        // Só mostra link da Liga se a sigla do modelo corresponde ao set
        // da carta exibida (evita link errado: ex. Mew ex Celebrations
        // casando com MEW-151 por nome). Cartas JP (is_jp) SEMPRE têm link:
        // a sigla é real da Liga (ex. SV4M-84) e o link funciona direto.
        ligaOk: scored.is_jp ? true
          : scored.sigla
            ? (setMap[String(scored.sigla).toLowerCase()] === card.set.id || !setMap[String(scored.sigla).toLowerCase()] ? true : false)
            : false,
      } : null,
    });
  } catch (error) {
    return NextResponse.json({
      error: error instanceof Error ? error.message : 'Erro ao buscar carta'
    }, { status: 500 });
  }
}
