#!/usr/bin/env python
"""
crawler_pull_rates.py — pull rates (estudos EN) por set, do ThePriceDex.

Fonte: https://www.thepricedex.com/set/{code}/{slug}/pull-rates
Os dados EN são referência de estudos (TCGPlayer Authentication Center + comunidade).
O ajuste para o booster PT-BR (6 cartas vs 11 no EN) é aplicado NA HORA DO CÁLCULO
(fator 0.5 por padrão — ver valor_esperado_booster.py).

Saída: data/liga/pull_rates_en.json
  { set_id: { nome, code, slug, ev_booster_usd, ev_box_usd, packs_box, cards_pack,
              pull_rates: { Rarity: {1em, por_caixa, especifica} },
              ev_breakdown: { Rarity: {total, priced, avg_usd, ev_usd} } } }
"""
import json
import re
import sys
import time
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / 'data' / 'liga' / 'pull_rates_en.json'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'

SETS = [
    ('sv1', 'scarlet-violet'),
    ('sv2', 'paldea-evolved'),
    ('sv3', 'obsidian-flames'),
    ('sv3pt5', '151'),
    ('sv4', 'paradox-rift'),
    ('sv4pt5', 'paldean-fates'),
    ('sv5', 'temporal-forces'),
    ('sv6', 'twilight-masquerade'),
    ('sv6pt5', 'shrouded-fable'),
    ('sv7', 'stellar-crown'),
    ('sv8', 'surging-sparks'),
    ('sv8pt5', 'prismatic-evolutions'),
    ('sv9', 'journey-together'),
    ('sv10', 'destined-rivals'),
]

NUM = re.compile(r'([\d,.]+)')


def parse_num(s: str) -> float:
    return float(s.replace(',', '')) if s else 0.0


CELL = r'<t[dh][^>]*>(?:<style>.*?</style>)?(?:<p[^>]*>)?([^<]*?)(?:</p>)?</t[dh]>'


def _todas_celulas(html: str) -> list[str]:
    return [c.strip() for c in re.findall(CELL, html)]


def parse_pull_rates(html: str) -> dict:
    """Tabela 'Pull Rates': sequências de 3 ou 4 células por linha (o 151 não tem coluna Per Booster Box)."""
    cel = _todas_celulas(html)
    out = {}
    i = 0
    n = len(cel)
    while i < n - 3:
        c = cel[i]
        # linha: [Rarity, '1 in X packs', ('Y cards'?), '1 in Z packs']
        if re.match(r'^1 in [\d,.]+ packs$', cel[i + 1]):
            # verifica se a célula atual é uma raridade (não cabeçalho/número)
            if c and not c[0].isdigit() and c not in ('Pull Rate', 'Per Booster Box', 'Specific Card Odds'):
                pr = cel[i + 1]
                j = i + 2
                pc = None
                if j < n and re.match(r'^[\d.]+ cards$', cel[j]):
                    pc = cel[j]
                    j += 1
                if j < n and re.match(r'^1 in [\d,.]+ packs$', cel[j]):
                    esp = cel[j]
                    out[c] = {
                        '1em': round(parse_num(pr.replace('1 in ', '').replace(' packs', '')), 1),
                        'por_caixa': round(parse_num(pc.replace(' cards', '')), 1) if pc else None,
                        'especifica': round(parse_num(esp.replace('1 in ', '').replace(' packs', '')), 1),
                    }
                    i = j + 1
                    continue
        i += 1
    return out


def parse_ev_breakdown(html: str) -> dict:
    """Tabela 'Expected Value Breakdown': sequências de 5 células [Rarity, Total, Priced, $avg, $ev]."""
    cel = _todas_celulas(html)
    out = {}
    for i in range(len(cel) - 4):
        rar, total, priced, avg, ev = (cel[i], cel[i + 1], cel[i + 2], cel[i + 3], cel[i + 4])
        if not total.isdigit() or rar == 'Total' or not rar or rar[0].isdigit():
            continue
        if not (avg.startswith('$') or avg == '—') or not (ev.startswith('$') or ev == '—'):
            continue
        out[rar] = {
            'total': int(total),
            'priced': priced,
            'avg_usd': None if avg == '—' else parse_num(avg.replace('$', '')),
            'ev_usd': None if ev == '—' else parse_num(ev.replace('$', '')),
        }
    return out


def main():
    sess = requests.Session()
    sess.headers.update({'User-Agent': UA})
    dados = {}
    for set_id, slug in SETS:
        url = f'https://www.thepricedex.com/set/{set_id}/{slug}/pull-rates'
        print(f'==> {set_id} ({slug})...')
        try:
            r = sess.get(url, timeout=30)
            r.raise_for_status()
        except Exception as e:
            print(f'    ERRO: {e}')
            continue
        html = r.text
        # nome do set (h1) + código (Set Code)
        m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        nome = m.group(1).strip() if m else slug
        m = re.search(r'Set Code:\s*</[^>]+>\s*([A-Z0-9]+)', html) or re.search(r'Set Code: ([A-Z0-9]+)', html)
        code = m.group(1) if m else ''
        # EV do booster: h5 em sequência — [set_value, set_value, booster_ev, box_ev, packs, cards]
        h5s = re.findall(r'<h5[^>]*>([^<]*)</h5>', html)
        valores = [parse_num(x.replace('$', '').replace(' ', '')) for x in h5s if re.match(r'^[\d,.$ ]+$', x.strip())]
        ev_booster = valores[2] if len(valores) > 2 else None
        ev_box = valores[3] if len(valores) > 3 else None
        packs_box = int(valores[4]) if len(valores) > 4 else None
        cards_pack = int(valores[5]) if len(valores) > 5 else None
        dados[set_id] = {
            'nome': nome,
            'code': code,
            'slug': slug,
            'ev_booster_usd': ev_booster,
            'ev_box_usd': ev_box,
            'packs_box': packs_box,
            'cards_pack': cards_pack,
            'pull_rates': parse_pull_rates(html),
            'ev_breakdown': parse_ev_breakdown(html),
        }
        pr = dados[set_id]['pull_rates']
        print(f'    {nome} ({code}) — EV ${ev_booster}/booster, {cards_pack} cartas/pacote, {len(pr)} raridades')
        time.sleep(1)

    OUT.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'\nSalvo: {OUT} ({len(dados)} sets)')


if __name__ == '__main__':
    main()
