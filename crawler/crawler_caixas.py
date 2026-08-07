#!/usr/bin/env python
"""
crawler_caixas.py — preços de CAIXAS SELADAS de boosters na Liga Pokémon.

1. Lista os produtos da categoria "Caixas de Boosters" (categ=10)
2. Para cada caixa: preço Menor/Médio/Maior do Marketplace
3. Mapeia o nome do produto para o set_id ptcg e salva data/liga/precos_caixas.json

Uso: python crawler/crawler_caixas.py
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scrapers import get_driver

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / 'data' / 'liga' / 'precos_caixas.json'

LISTA_URL = 'https://www.ligapokemon.com.br/?view=cards/search&card=categ=10&tipo=1'
PROD_URL = 'https://www.ligapokemon.com.br/?view=prod/view&pcode={pcode}'

# nome do produto (lowercase) → set_id
NOME_PARA_SET = {
    'escarlate e violeta 1 - escarlate e violeta': 'sv1',
    'escarlate e violeta 2 - evoluções em paldea': 'sv2',
    'escarlate e violeta 2 - evoluções em paldea ': 'sv2',
    'escarlate e violeta 3 - obsidiana em chamas': 'sv3',
    'escarlate e violeta 3.5 - 151': 'sv3pt5',
    'escarlate e violeta - 151': 'sv3pt5',
    'escarlate e violeta 4 - fenda paradoxal': 'sv4',
    'escarlate e violeta 4.5 - destinos de paldea': 'sv4pt5',
    'escarlate e violeta 5 - forças temporais': 'sv5',
    'escarlate e violeta 6 - máscaras do crepúsculo': 'sv6',
    'escarlate e violeta 6.5 - fábulas sombrias': 'sv6pt5',
    'escarlate e violeta 7 - coroa estelar': 'sv7',
    'escarlate e violeta 8 - fagulhas impetuosas': 'sv8',
    'escarlate e violeta 8.5 - evoluções prismáticas': 'sv8pt5',
    'escarlate e violeta 9 - amigos de jornada': 'sv9',
    'escarlate e violeta 10 - rivais predestinados': 'sv10',
}


def extrai_nome_pcode(html: str):
    """Extrai (pcode, nome) dos links de produto do Marketplace (HTML com &amp;)."""
    out = {}
    for m in re.finditer(r'prod/view&amp;pcode=(\d+)&amp;prod=([^"&]+)', html):
        pcode, prod = m.group(1), m.group(2)
        nome = re.sub(r'^\(PT-BR\)\s*', '', prod.replace('%20', ' ').replace('+', ' '))
        out.setdefault(pcode, nome)
    return out


def extrai_precos(html: str):
    """Extrai (menor, medio, maior) do 'Preço Médio de Venda no Marketplace'."""
    m = re.search(r'Preço Médio de Venda no Marketplace(.*?)(?:Lojas Vendendo|Vendedores|$)', html, re.S)
    if not m:
        return None
    blocos = re.findall(r'R\$\s*([\d.,]+)', m.group(1))
    precos = []
    for b in blocos[:3]:
        try:
            precos.append(round(float(b.replace('.', '').replace(',', '.')), 2))
        except ValueError:
            continue
    if len(precos) >= 2:
        return {'menor': min(precos), 'medio': precos[1] if len(precos) > 1 else precos[0], 'maior': max(precos)}
    return None


def main():
    driver = get_driver()
    pcodes = json.loads((REPO / 'data' / 'liga' / 'caixas_pcodes.json').read_text(encoding='utf-8'))
    print(f'==> {len(pcodes) - 1} produtos selados para coletar')

    caixas = {}
    for set_id, info in sorted(pcodes.items()):
        if set_id.startswith('_'):
            continue
        print(f'==> {set_id} ({info["tipo"]})...')
        driver.get(PROD_URL.format(pcode=info['pcode']))
        time.sleep(4)
        precos = extrai_precos(driver.page_source)
        if precos:
            precos['tipo'] = info['tipo']
            precos['pcode'] = info['pcode']
            caixas[set_id] = precos
            print(f'    → menor R${precos["menor"]} | médio R${precos["medio"]} | maior R${precos["maior"]}')
        else:
            print('    → preços não encontrados')

    out = {'data': time.strftime('%Y-%m-%d'), 'fonte': 'Liga Pokémon (produtos selados PT-BR)', 'caixas': caixas}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'\nSalvo: {OUT} ({len(caixas)} produtos)')


if __name__ == '__main__':
    main()
