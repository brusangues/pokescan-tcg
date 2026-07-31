"""
crawler/crawler_liga_snapshot.py
================================
Roda semanalmente: baixa TODOS os sets da Liga Pokémon
e salva um snapshot consolidado com timestamp.
Uso: python crawler/crawler_liga_snapshot.py [--max-sets 999]
"""

import sys, json, time
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
LIGA_DIR = BASE_DIR / 'data' / 'liga'
LIGA_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(BASE_DIR / 'crawler'))
from crawler_liga_bulk import discover_set_ids, crawl_set
from scrapers import get_driver

SNAPSHOT_DIR = LIGA_DIR / 'snapshots'
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
SET_IDS_PATH = LIGA_DIR / 'liga_set_ids.json'


def run_snapshot(max_sets=999):
    print(f'\n{"="*60}')
    print(f'📸 SNAPSHOT LIGA POKEMON — {datetime.now():%Y-%m-%d %H:%M}')
    print(f'{"="*60}\n')

    # 1. Descobrir IDs
    if SET_IDS_PATH.exists():
        known = set(json.loads(SET_IDS_PATH.read_text()))
    else:
        known = set()

    novos = discover_set_ids(max_range=1000)
    todos_ids = sorted(known | novos)
    SET_IDS_PATH.write_text(json.dumps(todos_ids))

    print(f'\n📦 Total de sets: {len(todos_ids)}')
    if max_sets and max_sets < len(todos_ids):
        todos_ids = todos_ids[:max_sets]
        print(f'  Limitado a {max_sets} sets')

    # 2. Crawlear cada set
    driver = get_driver()
    all_cards = []
    sets_ok = 0

    for i, sid in enumerate(todos_ids):
        try:
            cards = crawl_set(driver, sid)
            if cards:
                all_cards.extend(cards)
                sets_ok += 1
            if (i + 1) % 20 == 0:
                print(f'  Progresso: {i+1}/{len(todos_ids)} sets, {len(all_cards)} cartas')
        except Exception as e:
            print(f'  Erro set {sid}: {e}')
        time.sleep(1)

    driver.quit()

    # 3. Salvar snapshot
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = SNAPSHOT_DIR / f'liga_snapshot_{ts}.json'
    path.write_text(json.dumps(all_cards, indent=2, ensure_ascii=False))
    print(f'\n✅ Snapshot salvo: {path}')
    print(f'   Sets: {sets_ok}/{len(todos_ids)} | Cartas: {len(all_cards)}')

    # 4. Consolidar também no liga_all_cards.csv
    import pandas as pd
    df = pd.DataFrame(all_cards)
    csv_path = LIGA_DIR / f'liga_snapshot_{ts}.csv'
    df.to_csv(csv_path, index=False)
    print(f'   CSV: {csv_path}')

    return all_cards


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-sets', type=int, default=999)
    args = parser.parse_args()
    run_snapshot(max_sets=args.max_sets)