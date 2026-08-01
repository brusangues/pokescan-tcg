"""
crawler/crawler_liga_hits.py
============================
Raspa cartas em alta/queda da Liga Pokémon.
6 combinacoes: {day, week, month} x {alta, queda}
"""

import sys, json, time, re
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data' / 'liga'
DATA_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(BASE_DIR / 'crawler'))
from scrapers import get_driver

PERIOD_MAP = {'day': 1, 'week': 7, 'month': 30}
ORDER_MAP = {'alta': 2, 'queda': 1}

def scrape(periodo, tipo):
    p = PERIOD_MAP[periodo]
    order = ORDER_MAP[tipo]
    url = f'https://www.ligapokemon.com.br/?view=cards/variacao&formato=&period={p}&order={order}'
    nome = f'{periodo}_{tipo}'
    print(f'🌐 {nome}')

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
        return 0

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
                            cards.append({'nome': nome_c, 'preco': tds[-2].text.strip(), 'variacao': tds[-1].text.strip()})
                    except:
                        continue
            if cards:
                break

    fname = f'{nome}_{datetime.now():%Y%m%d_%H%M%S}.json'
    path = DATA_DIR / fname
    path.write_text(json.dumps(cards, indent=2, ensure_ascii=False))
    print(f'  ✅ {len(cards)} cartas → {fname}')
    return len(cards)


def scrape_all():
    for periodo in ['day', 'week', 'month']:
        for tipo in ['alta', 'queda']:
            try:
                scrape(periodo, tipo)
            except Exception as e:
                print(f'  ❌ Erro: {e}')
            time.sleep(3)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--tipo', default='all', choices=['all', 'day', 'week', 'month'])
    args = parser.parse_args()

    if args.tipo == 'all':
        scrape_all()
    else:
        for t in ['alta', 'queda']:
            scrape(args.tipo, t)
            time.sleep(3)