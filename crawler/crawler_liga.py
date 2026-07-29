"""
crawler_liga.py
===============
Crawler da Liga Pokémon para preços brasileiros (BRL).

Modos:
  1. Automático: tenta cloudscraper + selenium
  2. Manual: salva URL pra vc abrir no Chrome, eu extraio via computer_use
"""

import re, json, time, os, sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'
LIGA_DIR = DATA_DIR / 'liga'
LIGA_DIR.mkdir(parents=True, exist_ok=True)

URL_TOPS = 'https://www.ligapokemon.com.br/?view=cards/variacao&show=alta&formato=&order=2'


def parse_cardsjson(html):
    """Extrai var cardsjson do HTML."""
    match = re.search(r'var cardsjson = (\[.*?\]);', html, re.DOTALL)
    if not match:
        return None
    return json.loads(match.group(1))


def crawl_via_cloudscraper():
    """Tenta cloudscraper (pode falhar por Cloudflare)."""
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True},
            delay=10,
        )
        resp = scraper.get(URL_TOPS, timeout=30)
        if resp.status_code == 200:
            cards = parse_cardsjson(resp.text)
            if cards:
                return cards
        print(f'  cloudscraper: status {resp.status_code}')
    except Exception as e:
        print(f'  cloudscraper: {e}')
    return None


def crawl_via_selenium():
    """Tenta selenium com undetected_chromedriver."""
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from scrapers import selenium_get
        resp = selenium_get(URL_TOPS)
        cards = parse_cardsjson(resp.text)
        return cards
    except Exception as e:
        print(f'  selenium: {e}')
    return None


def crawl_via_playwright():
    """Tenta Playwright headless."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(URL_TOPS, timeout=30000)
            page.wait_for_timeout(5000)
            content = page.content()
            browser.close()
            return parse_cardsjson(content)
    except Exception as e:
        print(f'  playwright: {e}')
    return None


def crawl_all_modes():
    """Tenta todos os modos automáticos em sequência."""
    for name, fn in [
        ('cloudscraper', crawl_via_cloudscraper),
        ('selenium', crawl_via_selenium),
        ('playwright', crawl_via_playwright),
    ]:
        print(f'  ▶ {name}...')
        cards = fn()
        if cards:
            print(f'  ✅ {name}: {len(cards)} cartas')
            return cards
    return None


def save_cards(cards, source='auto'):
    """Salva cards em JSON + CSV."""
    ts = time.strftime('%Y%m%d_%H%M%S')
    path_json = LIGA_DIR / f'liga_tops_{ts}.json'
    with open(path_json, 'w', encoding='utf-8') as f:
        json.dump(cards, f, indent=2, default=str)
    
    # CSV resumido
    import csv
    path_csv = LIGA_DIR / f'liga_tops_{ts}.csv'
    with open(path_csv, 'w', encoding='utf-8', newline='') as f:
        if cards:
            writer = csv.DictWriter(f, fieldnames=cards[0].keys())
            writer.writeheader()
            writer.writerows(cards)
    
    print(f'  JSON: {path_json} ({len(cards)} cartas)')
    print(f'  CSV:  {path_csv}')
    return path_json


def show_sample(cards):
    """Mostra amostra das cartas."""
    print(f'\n📊 Amostra ({min(5, len(cards))} de {len(cards)}):')
    for c in cards[:5]:
        nome = c.get('nPT', c.get('nEN', '?'))
        p_min = c.get('p1a', '?')
        p_med = c.get('p1b', '?')
        p_max = c.get('p1c', '?')
        print(f'  {nome:35s} R$ {str(p_med):>8} (min R$ {str(p_min):>8} | max R$ {str(p_max):>8})')


if __name__ == '__main__':
    print('🔍 Crawler Liga Pokémon (BRL)')
    print(f'URL: {URL_TOPS}')
    
    cards = crawl_all_modes()
    
    if cards:
        save_cards(cards)
        show_sample(cards)
    else:
        print('\n⚠️  Modo automático falhou. Abra o Chrome nesta URL:')
        print(f'   {URL_TOPS}')
        print('   Depois execute: python crawler_liga.py --manual')
        sys.exit(1)
