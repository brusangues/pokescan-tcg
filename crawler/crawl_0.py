import cloudscraper
from bs4 import BeautifulSoup
import csv
import pandas as pd

PERIODOS = {
    "dia": 1,
    "semana": 2,
    "mes": 3,
}
VARIACOES = {
    "alta",
    "queda"
}

def crawl_pokemon_variations(variacao="alta", periodo="semana"):
    assert periodo in PERIODOS, "Invalid period!"
    assert variacao in VARIACOES, "Invalid variacao!"

    periodo_num = PERIODOS[periodo]
    url = f"https://www.ligapokemon.com.br/?view=cards/variacao&show={variacao}&formato=&order={periodo_num}"
    
    print("Bypassing Cloudflare and fetching data...")
    # Create a scraper instance that mimics a real browser
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    
    # Use the scraper just like you would use 'requests'
    response = scraper.get(url)
    
    if response.status_code != 200:
        print(f"Failed! Cloudflare might still be blocking it. Status: {response.status_code}")
        return
    
    with open('debug_response.html', 'w', encoding='utf-8') as f:
        f.write(response.text)

    import re
    import json
    cards_data = []
    # Extract the cardsjson variable from the HTML using regex
    match = re.search(r'var cardsjson = (\[.*?\]);', response.text, re.DOTALL)
    if not match:
        print("Could not find cardsjson variable in the HTML!")
        return
    try:
        cardsjson = json.loads(match.group(1))
    except Exception as e:
        print(f"Failed to parse cardsjson: {e}")
        return

    for card in cardsjson:
        card_name = card.get('sNomePortugues') or card.get('sNomeIngles') or card.get('nPT') or card.get('nEN') or ''
        edition = card.get('edicao') or card.get('ed_sNomePortugues') or card.get('ed_sNome') or ''
        variation = card.get('variancia') or card.get('varianciaSemFormat') or ''
        price = card.get('preco') or card.get('precoMenor') or card.get('precoMedio') or ''
        if card_name and (variation or price):
            cards_data.append([card_name, edition, variation, price])

    csv_filename = 'pokemon_cards_highest_valuation.csv'
    with open(csv_filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Card Name', 'Edition/Number', 'Variation Value', 'Current Price'])
        for data in cards_data:
            writer.writerow(data)
            
    print(f"Success! {len(cards_data)} cards saved to {csv_filename}.")
    return cards_data

if __name__ == "__main__":
    crawl_pokemon_variations()