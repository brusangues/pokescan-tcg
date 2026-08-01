"""
crawler/crawler_liga_snapshot.py
================================
Roda semanalmente: baixa TODOS os sets da Liga Pokémon
e salva um snapshot consolidado com timestamp.
Uso: python crawler/crawler_liga_snapshot.py [--max-sets 999]
"""

import sys, json, time, re
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
LIGA_DIR = BASE_DIR / 'data' / 'liga'
LIGA_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(BASE_DIR / 'crawler'))
from crawler_liga_bulk import discover_set_ids
from scrapers import selenium_get

SNAPSHOT_DIR = LIGA_DIR / 'snapshots'
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
SET_IDS_PATH = LIGA_DIR / 'liga_set_ids.json'


def run_snapshot(max_sets=999):
    print(f'\n{"="*60}')
    print(f'📸 SNAPSHOT LIGA POKEMON — {datetime.now():%Y-%m-%d %H:%M}')
    print(f'{"="*60}\n')

    # 1. Descobrir IDs (usa o KNOWN_SET_IDS do bulk + varredura)
    if SET_IDS_PATH.exists():
        known = set(json.loads(SET_IDS_PATH.read_text()))
    else:
        known = set()

    try:
        novos = discover_set_ids(max_range=1000, quiet=True)
    except Exception as e:
        print(f'  ⚠️ discover_set_ids falhou ({e}); usando conhecidos')
        novos = set()
    todos_ids = sorted(known | set(novos))
    SET_IDS_PATH.write_text(json.dumps(todos_ids))

    print(f'\n📦 Total de sets: {len(todos_ids)}')
    if max_sets and max_sets < len(todos_ids):
        todos_ids = todos_ids[:max_sets]
        print(f'  Limitado a {max_sets} sets')

    # 2. Baixar cada set (padrão do bulk: selenium_get + cardsjson)
    all_cards = []
    sets_ok = 0
    por_set = {}

    for i, eid in enumerate(todos_ids, 1):
        url = f'https://www.ligapokemon.com.br/?view=cards/search&card=edid={eid}%20ed=POR'
        try:
            resp = selenium_get(url, quiet=True)
            match = re.search(r'var cardsjson = (\[.*?\]);', resp.text, re.DOTALL)
            if match:
                cards = json.loads(match.group(1))
                if cards:
                    all_cards.extend(cards)
                    por_set[eid] = cards
                    sets_ok += 1
                    # Atualiza set_{id}.json para o merge BRL usar dados frescos
                    set_path = LIGA_DIR / f'set_{eid}.json'
                    set_path.write_text(json.dumps(cards, indent=2, ensure_ascii=False, default=str))
        except Exception:
            pass
        if (i + 1) % 50 == 0:
            print(f'  Progresso: {i+1}/{len(todos_ids)} sets, {len(all_cards)} cartas')
        time.sleep(1)

    # 3. Salvar snapshot consolidado
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = SNAPSHOT_DIR / f'liga_snapshot_{ts}.json'
    path.write_text(json.dumps(all_cards, indent=2, ensure_ascii=False))
    print(f'\n✅ Snapshot salvo: {path}')
    print(f'   Sets: {sets_ok}/{len(todos_ids)} | Cartas: {len(all_cards)}')
    return path


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-sets', type=int, default=999)
    args = parser.parse_args()
    run_snapshot(max_sets=args.max_sets)
