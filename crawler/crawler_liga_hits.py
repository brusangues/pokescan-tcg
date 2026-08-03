"""
crawler/crawler_liga_hits.py
============================
Raspa cartas em alta/queda da Liga Pokémon.
6 combinacoes: {day, week, month} x {alta, queda}

Melhoria: para cada carta na página de hits, entra na página individual
(?view=cards/card) e enriquece com:
  - iCO_real: número de anúncios de vendedores (página de hits traz iCO=0)
  - raridade_detalhada, artista, tipo
  - preco_menor/medio/maior_anuncio (p/m/g dos anúncios)

Uso:
  python crawler/crawler_liga_hits.py --tipo all           # raspa + enriquece
  python crawler/crawler_liga_hits.py --tipo all --no-enrich  # só raspa
"""

import sys, json, time, re
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data' / 'liga'
DATA_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(BASE_DIR / 'crawler'))
from scrapers import get_driver

PERIOD_MAP = {'day': 1, 'week': 7, 'month': 30}
ORDER_MAP = {'alta': 2, 'queda': 1}


def url_carta(nEN, sSigla, num):
    """URL da página individual da carta (padrão ?view=cards/card)."""
    card_param = quote(str(nEN))
    return f'https://www.ligapokemon.com.br/?view=cards/card&card={card_param}&ed={sSigla}&num={num}'


def parse_pagina_carta(src):
    """Extrai dados da página individual: iCO real, raridade, artista, preços."""
    dados = {}

    # cards_editions: raridade, artista, tipo, preços p/m/g
    m = re.search(r'var\s+cards_editions\s*=\s*(\[.*?\]);', src, re.DOTALL)
    if m:
        try:
            eds = json.loads(m.group(1))
            if eds:
                e = eds[0]
                rar = e.get('rarid') or {}
                dados['raridade_detalhada'] = rar.get('label', '')
                dados['artista'] = e.get('artist', '')
                dados['tipo_carta'] = e.get('type', '')
                pr = e.get('price') or {}
                p0 = pr.get('0') or {}
                if isinstance(p0, dict):
                    dados['preco_menor_anuncio'] = p0.get('p')
                    dados['preco_medio_anuncio'] = p0.get('m')
                    dados['preco_maior_anuncio'] = p0.get('g')
        except Exception:
            pass

    # cards_stock: anúncios → iCO real
    m = re.search(r'var\s+cards_stock\s*=\s*(\[.*?\]);', src, re.DOTALL)
    if m:
        try:
            stock = json.loads(m.group(1))
            dados['iCO_real'] = len(stock)
            # Condições dos anúncios (qualid → label aproximado)
            qtd_qual = {}
            for a in stock:
                q = a.get('qualid')
                qtd_qual[q] = qtd_qual.get(q, 0) + 1
            dados['anuncios_por_qualidade'] = qtd_qual
        except Exception:
            pass

    return dados


def enrich_carta(driver, carta):
    """Entra na página individual da carta e enriquece com os dados faltantes."""
    nEN = carta.get('nEN', '')
    sSigla = carta.get('sSigla', '')
    sNumber = carta.get('sNumber', '')
    if not nEN or not sSigla:
        return carta

    # Extrai número puro do sNumber (ex: '020' → '20', '151JP' → '151')
    m = re.match(r'(\d+)', str(sNumber))
    num = m.group(1).lstrip('0') if m else sNumber
    if not num:
        return carta

    url = url_carta(nEN, sSigla, num)
    try:
        driver.get(url)
        src = ''
        for _ in range(30):
            time.sleep(1)
            src = driver.page_source
            if 'cards_stock' in src and 'cards_editions' in src:
                break

        if '_cf_chl_opt' in src:
            carta['erro_enrich'] = 'cloudflare'
            return carta

        dados = parse_pagina_carta(src)
        if dados.get('iCO_real') is not None:
            carta.update(dados)
        else:
            carta['erro_enrich'] = 'sem_dados'
    except Exception as e:
        carta['erro_enrich'] = str(e)[:80]

    return carta


def scrape(periodo, tipo, enrich=True, enrich_max=None):
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
            except Exception:
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
                    except Exception:
                        continue
            if cards:
                break

    # ── Enriquecimento: entra em cada carta para pegar iCO real etc. ──
    if enrich and cards:
        alvo = cards[:enrich_max] if enrich_max else cards
        print(f'  🔍 Enriquecendo {len(alvo)} cartas (iCO real, raridade, artista)...')
        for i, carta in enumerate(alvo, 1):
            carta = enrich_carta(driver, carta)
            cards[i - 1] = carta
            if i % 10 == 0:
                print(f'    {i}/{len(alvo)}...')
            time.sleep(0.5)

    fname = f'{nome}_{datetime.now():%Y%m%d_%H%M%S}.json'
    path = DATA_DIR / fname
    path.write_text(json.dumps(cards, indent=2, ensure_ascii=False))
    n_ico = sum(1 for c in cards if c.get('iCO_real', 0) > 0)
    print(f'  ✅ {len(cards)} cartas → {fname} (com iCO real: {n_ico})')
    return len(cards)


def scrape_all(enrich=True, enrich_max=None):
    for periodo in ['day', 'week', 'month']:
        for tipo in ['alta', 'queda']:
            try:
                scrape(periodo, tipo, enrich=enrich, enrich_max=enrich_max)
            except Exception as e:
                print(f'  ❌ Erro: {e}')
            time.sleep(3)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--tipo', default='all', choices=['all', 'day', 'week', 'month'])
    parser.add_argument('--no-enrich', action='store_true', help='Não enriquecer (só raspar)')
    parser.add_argument('--enrich-max', type=int, default=None, help='Limite de cartas a enriquecer por página')
    args = parser.parse_args()

    if args.tipo == 'all':
        scrape_all(enrich=not args.no_enrich, enrich_max=args.enrich_max)
    else:
        for t in ['alta', 'queda']:
            scrape(args.tipo, t, enrich=not args.no_enrich, enrich_max=args.enrich_max)
            time.sleep(3)
