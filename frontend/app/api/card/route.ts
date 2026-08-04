import { NextResponse } from 'next/server';
import { readFileSync } from 'fs';
import { join } from 'path';

export const dynamic = 'force-dynamic';

let _cacheMap: Map<string | number, any> | null = null;

function loadCache() {
  if (_cacheMap) return _cacheMap;
  const cachePath = join(process.cwd(), '..', 'data', 'ptcg_cards_cache.json');
  const raw = readFileSync(cachePath, 'utf-8');
  const cards = JSON.parse(raw);
  _cacheMap = new Map();
  for (const c of cards) {
    // Index by id
    _cacheMap.set(c.id, c);
  }
  return _cacheMap;
}

function loadSetMapping(): Record<string, string> {
  try {
    const path1 = join(process.cwd(), '..', 'data', 'liga', 'liga_set_sigla_ptcg.json');
    return JSON.parse(readFileSync(path1, 'utf-8'));
  } catch {
    try {
      const path2 = join(process.cwd(), '..', 'data', 'liga', 'liga_set_sigla.json');
      return JSON.parse(readFileSync(path2, 'utf-8'));
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

    const cache = loadCache();
    const setMap = loadSetMapping();

    let card = null;

    // Estratégia 1: liga_id
    if (ligaId) {
      const parts = ligaId.split('-');
      const sigla = parts[0].toLowerCase();
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
        // Determina optcgSetId para filtrar pelo set
        const rawSigla = ligaId?.split('-')[0]?.toLowerCase();
        const ptcgSet = rawSigla ? setMap[rawSigla] : (setId || '');
        for (const [key, c] of cache) {
          if (c.name?.toLowerCase() === nomeBusca && (!ptcgSet || key.startsWith(ptcgSet))) {
            card = c;
            break;
          }
        }
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
    });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : 'Erro' }, { status: 500 });
  }
}