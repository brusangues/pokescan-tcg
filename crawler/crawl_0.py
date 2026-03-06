import re
import json
import time
from scrapers import cloudscraper_get, selenium_get


PERIODOS = {
    "dia": 1,
    "semana": 2,
    "mes": 3,
}
VARIACOES = {
    "alta",
    "queda"
}


def parse_cards_json(text):
    print("parse_cards_json...")
    match = re.search(r'var cardsjson = (\[.*?\]);', text, re.DOTALL)
    if not match:
        print("Could not find cardsjson variable in the HTML!")
        return []
    try:
        cards_json = json.loads(match.group(1))
    except Exception as e:
        print(f"Failed to parse cardsjson: {e}")
        return []

    with open('debug_cards_json.json', 'w', encoding='utf-8') as f:
        json.dump(cards_json, f, indent=4, default=str)
    return cards_json


def crawl_pokemon_variations(variacao="alta", periodo="semana") -> list:
    assert periodo in PERIODOS, "Invalid period!"
    assert variacao in VARIACOES, "Invalid variacao!"

    periodo_num = PERIODOS[periodo]
    url = f"https://www.ligapokemon.com.br/?view=cards/variacao&show={variacao}&formato=&order={periodo_num}"

    response = cloudscraper_get(url)

    cards_json = parse_cards_json(response.text)
    
    time.sleep(2)  # Delay before next request

    return cards_json


def crawl_pokemon_set(url = "https://www.ligapokemon.com.br/?view=cards/search&card=edid=738%20ed=PFL") -> list:
    response = selenium_get(url)

    cards_json = parse_cards_json(response.text)
    
    time.sleep(2)  # Delay before next request

    return cards_json
