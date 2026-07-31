"""
crawler/crawler_liga_hits.py
============================
Raspa cartas em alta/queda da Liga Pokémon usando URLs do crawler_liga_pages.
"""

import sys, json, time, re
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data' / 'liga'
DATA_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(BASE_DIR / 'crawler'))
from scrapers import get_driver

URLS = {
    'week_alta': 'https://www.ligapokemon.com.br/?view=cards/variacao&show=alta&formato=&order=2',
    'week_queda': 'https://www.ligapokemon.com.br/?view=cards/variacao&show=queda&formato=&order=2',
    'mais_vistas': 'https://www.ligapokemon.com.br/?view=cards/cards_mostviewed',
    'mais_vistas_15': 'https://www.ligapokemon.com.br/?view=cards/cards_mostviewed&days=15',
    'novas': 'https://www.ligapokemon.com.br/?view=cards/cards_mostviewed&days=1',
}

def scrape(nome, url):
    print(f'🌐 {nome}: {url}')
    driver = get_driver()
    driver.get(url)
    time.sleep(3)

    for _ in range(60):
        time.sleep(1)
        src = driver.page_source
        if 'cardsjson' in src or 'nPT' in src:
            break

    src = driver.page_source
    if '_cf_chl_opt' in src:
        print(f'  ❌ Cloudflare')
        return

    cards = []
    if 'cardsjson' in src:
        m = re.search(r'cardsjson\s*=\s*(\[.*?\])\s*;', src, re.DOTALL)
        if m:
            try:
                cards = json.loads(m.group(1))
            except:
                pass

    if not cards:
        from selenium.webdriver.common.by import By
        for sel in ['.linha', '[class*="linha"]', 'table tr', 'tr']:
            rows = driver.find_elements(By.CSS_SELECTOR, sel)
            for row in rows:
                tds = row.find_elements(By.TAG_NAME, 'td')
                if len(tds) >= 3:
                    try:
                        nome_c = tds[1].text.strip()
                        if nome_c and any(c.isalpha() for c in nome_c):
                            cards.append({
                                'nome': nome_c,
                                'posicao': tds[0].text.strip() if len(tds) > 0 else '',
                                'edicao': tds[2].text.strip() if len(tds) > 2 else '',
                                'preco': tds[-2].text.strip() if len(tds) > 3 else '',
                                'variacao': tds[-1].text.strip() if len(tds) > 1 else '',
                            })
                    except:
                        continue
            if cards:
                break

    fname = f'{nome}_{datetime.now():%Y%m%d_%H%M%S}.json'
    path = DATA_DIR / fname
    path.write_text(json.dumps(cards, indent=2, ensure_ascii=False))
    print(f'  ✅ {len(cards)} cartas → {fname}')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--tipo', default='all',
                        choices=['all', 'week_alta', 'week_queda', 'mais_vistas', 'mais_vistas_15', 'novas'])
    args = parser.parse_args()

    if args.tipo == 'all':
        for nome, url in URLS.items():
            scrape(nome, url)
            time.sleep(3)
    else:
        scrape(args.tipo, URLS[args.tipo])