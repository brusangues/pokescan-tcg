"""
experiments/download_all_images.py
==================================
Baixa TODAS as imagens das cartas da base (20.479) para data/img_cache.
Usa pokemontcg.io via ptcg_io (já tem os dados) — sem depender do mapeamento TCGdex.

Uso:
  python experiments/download_all_images.py            # incremental (resume)
  python experiments/download_all_images.py --limit 2000
"""

import sys, time, argparse
from pathlib import Path
import json
import requests
from PIL import Image
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
CACHE_DIR = DATA_DIR / 'img_cache'
CACHE_DIR.mkdir(parents=True, exist_ok=True)

IMG_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def download_one(card):
    cid = card['id']
    path = CACHE_DIR / f'{cid}.png'
    if path.exists():
        return cid, 'cache'
    url = card.get('images', {}).get('small')
    if not url:
        return cid, 'no-url'
    try:
        resp = requests.get(url, headers=IMG_HEADERS, timeout=15)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert('RGB')
        img_resized = img.resize((256, 256), Image.LANCZOS)
        img_resized.save(path, 'PNG')
        return cid, 'ok'
    except Exception:
        return cid, 'fail'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0, help='limite de cartas (0 = todas)')
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()

    cards = json.loads((DATA_DIR / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
    if args.limit:
        cards = cards[:args.limit]
    print(f'Cartas a processar: {len(cards)}')

    já = len(list(CACHE_DIR.glob('*.png')))
    print(f'Já em cache: {já}')

    stats = {'ok': 0, 'cache': 0, 'fail': 0, 'no-url': 0}
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(download_one, c): c['id'] for c in cards}
        done = 0
        for fut in as_completed(futures):
            cid, status = fut.result()
            stats[status] += 1
            done += 1
            if done % 200 == 0:
                el = time.time() - t0
                rate = done / el
                print(f'  {done}/{len(cards)} | ok={stats["ok"]} cache={stats["cache"]} fail={stats["fail"]} | {rate:.1f}/s')

    el = time.time() - t0
    print(f'\n✅ Concluído em {el:.0f}s')
    print(f'  ok={stats["ok"]} | cache={stats["cache"]} | fail={stats["fail"]} | no-url={stats["no-url"]}')
    total = len(list(CACHE_DIR.glob('*.png')))
    print(f'  Total em cache: {total}')


if __name__ == '__main__':
    main()
