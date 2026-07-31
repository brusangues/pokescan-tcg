"""
ptcg_io.py
==========
Fonte de dados principal: pokemontcg.io API (até 2026).
Substitui a TCGdex como fonte de features, preços USD e Cardmarket.

Campos extraídos por carta:
  - id (ex: sv8-1), name, hp, supertype, subtypes, types, rarity
  - set: id, name, series, printedTotal, releaseDate
  - nationalPokedexNumbers
  - tcgplayer: market price USD (por variante: normal/holofoil/reverseHolofoil)
  - cardmarket: avg1/avg7/avg30/trendPrice/lowPrice (EUR, médias móveis)

Interface compatível com pokemon_price_monitor.py:
  - fetch_all_cards(max_sets) -> list[dict] com chave '_set'
  - parse_card(c) -> dict com mesmas chaves do parse_card TCGdex
  - fetch_card_pricing(card_id) -> dict com mesmas chaves
"""

import json, re, time, requests
from datetime import datetime

API = 'https://api.pokemontcg.io/v2'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/126.0.0.0 Safari/537.36',
    'Accept': 'application/json',
}
TIMEOUT = 30
MAX_PAGE = 250  # limite da API por página


def fetch_json(url, params=None, retries=4):
    """GET com retry e backoff (API tem rate limit)."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429 or resp.status_code == 500:
                time.sleep(3 * (attempt + 1))
                continue
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
    return None


def fetch_all_sets():
    """Lista todos os sets (com releaseDate)."""
    data = fetch_json(f'{API}/sets')
    if not data:
        return []
    return data.get('data', [])


def fetch_set_cards(set_id, set_info_extra=None):
    """Todas as cartas de um set (paginado)."""
    all_cards = []
    page = 1
    while True:
        params = {'q': f'set.id:{set_id}', 'page': page, 'pageSize': MAX_PAGE}
        data = fetch_json(f'{API}/cards', params=params)
        if not data:
            break
        cards = data.get('data', [])
        if not cards:
            break
        all_cards.extend(cards)
        total = data.get('totalCount', 0)
        if len(all_cards) >= total or len(cards) < MAX_PAGE:
            break
        page += 1
        time.sleep(0.35)
    return all_cards


def fetch_all_cards(max_sets=50, min_release_year=None):
    """Coleta cartas dos N sets mais recentes (ou os primeiros por id).

    max_sets: quantos sets baixar.
    min_release_year: se definido, baixa apenas sets >= ano (prioriza novos).
    """
    sets = fetch_all_sets()
    if not sets:
        return []

    # Ordena por releaseDate (mais recentes primeiro)
    com_data = [s for s in sets if s.get('releaseDate')]
    sem_data = [s for s in sets if not s.get('releaseDate')]

    def parse_ano(d):
        try:
            return int(str(d).split('/')[0])
        except Exception:
            return 0

    com_data.sort(key=lambda s: parse_ano(s.get('releaseDate', '')), reverse=True)

    if min_release_year:
        com_data = [s for s in com_data if parse_ano(s.get('releaseDate')) >= min_release_year]
        if not com_data:
            print(f'  Nenhum set >= {min_release_year}. Usando todos.')
            com_data = sorted(sets, key=lambda s: s.get('id'))[:max_sets]
            sem_data = []
    else:
        # Sem filtro: ordem crescente por id (sets antigos primeiro)
        com_data = [s for s in sets if s.get('releaseDate')]
        sem_data = [s for s in sets if not s.get('releaseDate')]
        com_data.sort(key=lambda s: s.get('id'))

    todos = com_data + sem_data
    print(f'  Sets disponíveis: {len(todos)}')

    all_cards = []
    n = min(max_sets, len(todos))
    for i, s in enumerate(todos[:n]):
        sid = s.get('id')
        set_name = s.get('name', sid)
        cards = fetch_set_cards(sid)
        set_info = {
            'set_id': sid,
            'set_name': set_name,
            'set_series': s.get('series', ''),
            'set_release_date': s.get('releaseDate', ''),
            'set_printed_total': s.get('printedTotal', 0) or s.get('total', 0) or len(cards),
        }
        for c in cards:
            c['_set'] = set_info
        all_cards.extend(cards)
        print(f'  Set {i+1}/{n}: {set_name} ({len(cards)} cartas, total: {len(all_cards)})')
        time.sleep(0.35)

    return all_cards


def parse_card(c):
    """Extrai features de uma carta pokemontcg.io (mesmas chaves do TCGdex)."""
    set_info = c.get('_set', {})
    rel_date = set_info.get('set_release_date', '')
    rel_year = None
    if rel_date:
        try:
            rel_year = int(str(rel_date).split('/')[0])
        except Exception:
            pass

    types = c.get('types', []) or []
    dex_ids = c.get('nationalPokedexNumbers', []) or []
    hp_str = c.get('hp')
    try:
        hp = float(hp_str) if hp_str else None
    except (TypeError, ValueError):
        hp = None

    # Supertype + stage
    supertype = c.get('supertype', 'Pokémon')
    subtypes = c.get('subtypes', []) or []
    stage = 'Basic'
    for st in subtypes:
        if st in ('Stage 1', 'Stage 2', 'Basic', 'VMAX', 'VSTAR', 'ex', 'Tera'):
            stage = st
            break
    # VMAX/VSTAR/ex são estágios especiais — mantém como estão

    return {
        'id': c.get('id', ''),
        'name': c.get('name', ''),           # EN (pokemontcg.io só tem EN)
        'name_en': c.get('name', ''),
        'hp': hp,
        'supertype': supertype,
        'subtypes_count': len(subtypes),
        'primary_type': types[0] if types else 'Colorless',
        'rarity': c.get('rarity', 'Unknown'),
        'stage': stage,
        'set_id': set_info.get('set_id', ''),
        'set_name': set_info.get('set_name', ''),
        'set_series': set_info.get('set_series', ''),
        'set_printed_total': set_info.get('set_printed_total', 0),
        'release_year': rel_year,
        'card_age_years': (datetime.now().year - rel_year) if rel_year else None,
        'pokedex_number': dex_ids[0] if dex_ids else None,
        'image': (c.get('images') or {}).get('large') or (c.get('images') or {}).get('small'),
    }


def fetch_card_pricing(card):
    """Extrai pricing USD + EUR (médias móveis) de uma carta.

    Aceita dict da API (preferível — já vem com tcgplayer/cardmarket)
    ou id string (faz fetch individual).
    """
    if isinstance(card, str):
        data = fetch_json(f'{API}/cards/{card}')
        if not data:
            return {}
        data = data.get('data', data)
    else:
        data = card

    tcg = data.get('tcgplayer', {}) or {}
    prices = tcg.get('prices', {}) or {}
    cm = data.get('cardmarket', {}) or {}
    cm_prices = cm.get('prices', {}) or {}

    # Preço USD: prioriza holofoil, depois normal, depois reverse
    target_usd = None
    price_type = None
    for variant in ('holofoil', 'normal', 'reverseHolofoil'):
        v = prices.get(variant)
        if v and v.get('market'):
            target_usd = v['market']
            price_type = variant
            break

    # Variantes de arte
    is_holo = 'holofoil' in prices
    is_reverse = 'reverseHolofoil' in prices
    is_normal = 'normal' in prices

    # Nome + ilustrador
    name_en = data.get('name', '')
    illustrator = (data.get('tcgplayer') or {}).get('url', '')
    # pokemontcg.io NAO tem illustrator — deixamos vazio
    # (pode ser extraído do cardmarket ou da imagem depois)
    illustrator = ''

    shiny_name = 'shiny' in name_en.lower()

    # Gênero do treinador (reusa função do monitor via import tardio)
    trainer_gender = 'neutral'
    if data.get('supertype') == 'Trainer':
        from pokemon_price_monitor import infer_trainer_gender
        trainer_gender = infer_trainer_gender(name_en)

    return {
        'target_price_usd': target_usd,
        'price_type': price_type,
        'rarity_tcg': data.get('rarity', 'Unknown'),
        'is_holo': int(is_holo),
        'is_reverse': int(is_reverse),
        'is_normal': int(is_normal),
        'name_en': name_en,
        'illustrator': illustrator,
        'is_shiny': int(shiny_name),
        'trainer_gender': trainer_gender,
        # Precos historicos Cardmarket (EUR) — medias moveis
        'cardmarket_avg': cm_prices.get('averageSellPrice'),
        'cardmarket_avg1': cm_prices.get('avg1'),
        'cardmarket_avg7': cm_prices.get('avg7'),
        'cardmarket_avg30': cm_prices.get('avg30'),
        'cardmarket_trend': cm_prices.get('trendPrice'),
        'cardmarket_low': cm_prices.get('lowPrice'),
        'cardmarket_updated': cm.get('updatedAt'),
    }
