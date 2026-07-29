"""
crawler_liga_bulk.py
====================
Crawleia o máximo possível de sets da Liga Pokémon.

Uso:
  python crawler_liga_bulk.py                     # crawleia tudo
  python crawler_liga_bulk.py --max-sets 20       # só 20 sets
  python crawler_liga_bulk.py --discover-only     # só descobre novos IDs
"""

import re, json, time, sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scrapers import selenium_get

BASE_DIR = Path(__file__).parent.parent
LIGA_DIR = BASE_DIR / 'data' / 'liga'
LIGA_DIR.mkdir(parents=True, exist_ok=True)

SETS_KNOWN_PATH = LIGA_DIR / 'liga_set_ids.json'

# IDs já descobertos das páginas tops + busca manual
KNOWN_SET_IDS = sorted({
    22, 26, 27, 28, 53, 54, 59, 62, 77, 162, 163, 245, 264, 265, 266,
    307, 316, 325, 329, 331, 332, 342, 362, 368, 391, 421, 450, 454,
    483, 534, 555, 639, 658, 673, 719, 740,
    769,  # sv01
})


def discover_set_ids(max_range=1000):
    """Tenta descobrir novos IDs de sets varrendo ranges."""
    known = set(KNOWN_SET_IDS)
    discovered = set()
    
    print(f'🔎 Descobrindo sets (já temos {len(known)})...')
    
    # Varre ranges ao redor dos IDs conhecidos
    ranges = []
    for kid in known:
        ranges.append(range(max(1, kid - 5), kid + 6))
    
    # Adiciona faixas conhecidas de sets populares
    ranges.append(range(760, 780))   # sv sets
    
    to_test = set()
    for r in ranges:
        to_test.update(r)
    to_test -= known  # só testa os que não temos
    
    print(f'  Testando {len(to_test)} possíveis IDs...')
    
    for eid in sorted(to_test):
        if eid in discovered:
            continue
        url = f'https://www.ligapokemon.com.br/?view=cards/search&card=edid={eid}%20ed=POR'
        try:
            resp = selenium_get(url)
            match = re.search(r'var cardsjson = (\[.*?\]);', resp.text, re.DOTALL)
            if match:
                cards = json.loads(match.group(1))
                if cards:
                    discovered.add(eid)
                    nome = cards[0].get('ed_sNomePortugues') or cards[0].get('edicao', '?')
                    qtd = len(cards)
                    print(f'  ✅ ID {eid}: {nome} ({qtd} cartas)')
        except Exception as e:
            pass  # 403 ou sem cardsjson = set inexistente
        time.sleep(1)
    
    # Salva descobertos
    all_ids = sorted(known | discovered)
    SETS_KNOWN_PATH.write_text(json.dumps(all_ids, indent=2))
    print(f'\n📦 Total de sets: {len(all_ids)} (novos: {len(discovered)})')
    return all_ids


def crawl_sets(set_ids, max_sets=None):
    """Crawleia sets específicos."""
    if max_sets:
        set_ids = set_ids[:max_sets]
    
    total_cards = 0
    for i, eid in enumerate(set_ids, 1):
        path = LIGA_DIR / f'set_{eid}.json'
        if path.exists():
            with open(path) as f:
                cards = json.load(f)
            total_cards += len(cards)
            print(f'  [{i}/{len(set_ids)}] ID {eid}: já existe ({len(cards)} cartas)')
            continue
        
        url = f'https://www.ligapokemon.com.br/?view=cards/search&card=edid={eid}%20ed=POR'
        print(f'  [{i}/{len(set_ids)}] ID {eid}...', end=' ', flush=True)
        
        try:
            resp = selenium_get(url)
            match = re.search(r'var cardsjson = (\[.*?\]);', resp.text, re.DOTALL)
            if match:
                cards = json.loads(match.group(1))
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(cards, f, indent=2, default=str)
                total_cards += len(cards)
                print(f'{len(cards)} cartas')
            else:
                print('sem cardsjson')
        except Exception as e:
            print(f'ERRO: {e}')
        
        time.sleep(2)  # backoff pra não tomar rate limit
    
    print(f'\n✅ Total: {total_cards} cartas em {len(set_ids)} sets')
    return total_cards


def consolidate():
    """Consolida todos os sets num CSV único."""
    import pandas as pd
    import csv
    
    all_cards = []
    for f in sorted(LIGA_DIR.glob('set_*.json')):
        with open(f) as fh:
            cards = json.load(fh)
            for c in cards:
                p_medio = c.get('p1b')
                if p_medio is not None and p_medio not in ('', '-'):
                    p_medio = float(p_medio)
                else:
                    p_medio = 0.0
                all_cards.append({
                    'id_liga': c.get('id'),
                    'nome_pt': c.get('nPT', c.get('sNomePortugues', '')),
                    'nome_en': c.get('nEN', c.get('sNomeIngles', '')),
                    'sigla_set': c.get('sSigla', ''),
                    'preco_min_brl': float(c.get('p1a') or 0),
                    'preco_medio_brl': p_medio,
                    'preco_max_brl': float(c.get('p1c') or 0),
                    'raridade': c.get('raridade', ''),
                    'tipo': c.get('sT', ''),
                })
    
    com_preco = [c for c in all_cards if c['preco_medio_brl'] > 0]
    media = sum(c['preco_medio_brl'] for c in com_preco) / len(com_preco) if com_preco else 0
    
    path = LIGA_DIR / 'liga_all_cards.csv'
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=all_cards[0].keys())
        w.writeheader()
        w.writerows(all_cards)
    
    print(f'\n📊 Consolidado: {len(all_cards)} cartas, {len(com_preco)} com preço, média R${media:.2f}')
    return all_cards


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-sets', type=int, help='Limite de sets pra crawlear')
    parser.add_argument('--discover-only', action='store_true', help='Só descobre IDs')
    parser.add_argument('--consolidate-only', action='store_true', help='Só consolida existentes')
    args = parser.parse_args()
    
    if args.consolidate_only:
        consolidate()
        sys.exit(0)
    
    # Descobre e carrega IDs
    if SETS_KNOWN_PATH.exists() and not args.discover_only:
        set_ids = json.loads(SETS_KNOWN_PATH.read_text())
        print(f'📦 {len(set_ids)} sets conhecidos carregados')
    else:
        set_ids = discover_set_ids()
    
    if args.discover_only:
        sys.exit(0)
    
    # Crawleia
    total = crawl_sets(set_ids, max_sets=args.max_sets)
    
    # Consolida
    consolidate()
