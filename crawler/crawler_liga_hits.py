"""
crawler/crawler_liga_hits.py
============================
Raspa cartas em alta/queda da Liga Pokémon.
Períodos: dia, semana, mês.
Ordenações: maior alta, maior queda.
"""

import sys, json, time, re
from pathlib import Path
from datetime import datetime
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data' / 'liga'
DATA_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = 'https://www.ligapokemon.com.br'

def scrape_hits(periodo='week', order=1, headless=True):
    """
    Raspa a página de cards hits.
    
    Args:
        periodo: 'day', 'week', 'month'
        order: 1=maior alta, 2=maior queda
        headless: roda sem janela
    """
    period_map = {'day': 1, 'week': 7, 'month': 30}
    url = f'{BASE_URL}/?view=cards/hits&formato=&order={order}&period={period_map.get(periodo, 7)}'
    print(f'🌐 Acessando: {url}')
    
    options = uc.ChromeOptions()
    if headless:
        options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1400,900')
    options.add_argument(f'user-data-dir=C:\\Users\\Bruno\\AppData\\Local\\Google\\Chrome\\User Data')
    options.add_argument('--profile-directory=Default')
    
    driver = uc.Chrome(options=options, version_main=126)
    
    try:
        driver.get(url)
        time.sleep(5)
        
        # Aceitar cookies se aparecer
        try:
            btn = driver.find_element(By.XPATH, "//button[contains(text(), 'PERMITIR')]")
            btn.click()
            time.sleep(1)
        except:
            pass
        
        cards = []
        rows = driver.find_elements(By.CSS_SELECTOR, '.linha-hits, .table-hits tr, [class*=\"linha\"], [class*=\"hit\"]')
        
        if not rows:
            # Fallback: procurar qualquer tabela/grid
            rows = driver.find_elements(By.CSS_SELECTOR, 'table tr')
        
        print(f'  Linhas encontradas: {len(rows)}')
        
        for row in rows[:100]:
            try:
                cols = row.find_elements(By.TAG_NAME, 'td')
                if len(cols) >= 4:
                    card = {
                        'posicao': cols[0].text.strip(),
                        'nome': cols[1].text.strip(),
                        'edicao': cols[2].text.strip() if len(cols) > 2 else '',
                        'preco': cols[-2].text.strip() if len(cols) > 2 else '',
                        'variacao': cols[-1].text.strip() if len(cols) > 1 else '',
                    }
                    # Extrair link
                    links = cols[1].find_elements(By.TAG_NAME, 'a')
                    if links:
                        card['url'] = links[0].get_attribute('href')
                    cards.append(card)
            except:
                continue
        
        if not cards:
            # Salvar HTML pra debug
            html_path = DATA_DIR / f'hits_debug_{periodo}_{order}.html'
            html_path.write_text(driver.page_source, encoding='utf-8')
            print(f'  HTML salvo em {html_path}')
        
        filename = f'hits_{periodo}_{"alta" if order==1 else "queda"}_{datetime.now():%Y%m%d_%H%M%S}.json'
        path = DATA_DIR / filename
        path.write_text(json.dumps(cards, indent=2, ensure_ascii=False))
        print(f'✅ Salvo: {path} ({len(cards)} cartas)')
        return cards
    
    finally:
        driver.quit()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--periodo', default='week', choices=['day', 'week', 'month'])
    parser.add_argument('--order', type=int, default=1, choices=[1, 2])
    parser.add_argument('--no-headless', action='store_true')
    args = parser.parse_args()
    
    scrape_hits(periodo=args.periodo, order=args.order, headless=not args.no_headless)