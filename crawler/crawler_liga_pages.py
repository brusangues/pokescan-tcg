"""
crawler_liga_pages.py
=====================
Crawler multi-página da Liga Pokémon:
  - Alta / Queda / Mais Vistas
  - Cards em queda
  - Busca por edição (set)
"""

LIGA_URLS = {
    'alta': 'https://www.ligapokemon.com.br/?view=cards/variacao&show=alta&formato=&order=2',
    'queda': 'https://www.ligapokemon.com.br/?view=cards/variacao&show=queda&formato=&order=2',
    'mais_vistas': 'https://www.ligapokemon.com.br/?view=cards/cards_mostviewed',
    'mais_vistas_15': 'https://www.ligapokemon.com.br/?view=cards/cards_mostviewed&days=15',
    'novas': 'https://www.ligapokemon.com.br/?view=cards/cards_mostviewed&days=1',
}

def crawl_liga_pages():
    pass
