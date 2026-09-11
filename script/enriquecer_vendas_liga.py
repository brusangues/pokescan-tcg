#!/usr/bin/env python
"""enriquecer_vendas_liga.py — Vendas verificadas (3 meses) + preco por tipo (N/F).

Visita a pagina individual da carta (?view=cards/card) e extrai do JSON
`cards_editions[0]` embutido no HTML:

  - price['0'] (Normal) e price['2'] (Foil) -> menor/media/maior de ANUNCIO
  - ls -> "Vendas nos Ultimos 3 meses" (vendas concretizadas/verificadas)

Cache incremental retomavel em data/liga/vendas_3m.json:

  {"<idE>-<num>": {"idE":.., "num":.., "sigla":.., "nEN":..,
                   "normal": {"p":..,"m":..,"g":..},
                   "foil":   {"p":..,"m":..,"g":..},
                   "vendas": {"q":..,"p":..,"m":..,"g":..},
                   "n_anuncios": N, "ts": "YYYY-MM-DD"}}

Fila: data/catalogo_liga.json ordenado por iCO desc (cartas mais anunciadas
primeiro). Entradas com ts mais novo que --dias-refresh sao puladas, logo
rodadas diarias caminham pelo catalogo e depois reciclam do comeco.

Uso:
  python script/enriquecer_vendas_liga.py --limite 200
  python script/enriquecer_vendas_liga.py --limite 50 --sleep 0.3
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'crawler'))

from crawler_liga_hits import get_driver, parse_pagina_carta, url_carta  # noqa: E402

CATALOGO = RAIZ / 'data' / 'catalogo_liga.json'
SAIDA = RAIZ / 'data' / 'liga' / 'vendas_3m.json'


def carrega_estado() -> dict:
    if SAIDA.exists():
        try:
            return json.loads(SAIDA.read_text(encoding='utf-8'))
        except Exception:
            print(f'!! estado ilegivel ({SAIDA.name}) - recomecando vazio')
    return {}


def grava_estado(estado: dict) -> None:
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    tmp = SAIDA.with_suffix('.tmp')
    tmp.write_text(json.dumps(estado, ensure_ascii=False, separators=(',', ':')),
                   encoding='utf-8')
    tmp.replace(SAIDA)


def monta_fila(estado: dict, dias_refresh: int) -> list:
    cat = json.loads(CATALOGO.read_text(encoding='utf-8'))
    corte = date.today().toordinal() - dias_refresh
    itens = []
    for c in cat:
        idE, num = c.get('idE'), c.get('num')
        if idE is None or not num:
            continue
        k = f'{idE}-{num}'
        reg = estado.get(k)
        if reg and reg.get('ts'):
            try:
                if date.fromisoformat(reg['ts']).toordinal() > corte:
                    continue
            except ValueError:
                pass
        itens.append((-int(c.get('iCO') or 0), k, c))
    itens.sort(key=lambda t: (t[0], t[1]))
    return [(k, c) for _, k, c in itens]


def num_url(carta: dict) -> str:
    m = re.match(r'(\d+)', str(carta.get('num') or ''))
    if m:
        return m.group(1).lstrip('0') or '0'
    return str(carta.get('num') or '')


def registra(dados: dict, carta: dict, hoje: str) -> dict | None:
    """Converte os campos do parser no registro persistido."""
    normal = {}
    if dados.get('preco_medio_anuncio') is not None:
        normal = {'p': dados.get('preco_menor_anuncio'),
                  'm': dados.get('preco_medio_anuncio'),
                  'g': dados.get('preco_maior_anuncio')}
    foil = {}
    if dados.get('preco_foil_medio') is not None:
        foil = {'p': dados.get('preco_foil_menor'),
                'm': dados.get('preco_foil_medio'),
                'g': dados.get('preco_foil_maior')}
    vendas = {}
    if dados.get('vendas_medio') is not None:
        vendas = {'q': dados.get('vendas_q'),
                  'p': dados.get('vendas_menor'),
                  'm': dados.get('vendas_medio'),
                  'g': dados.get('vendas_maior')}
    if not (normal or foil or vendas):
        return None
    return {'idE': carta['idE'], 'num': carta['num'], 'sigla': carta.get('sigla'),
            'nEN': carta.get('nEN'), 'normal': normal, 'foil': foil,
            'vendas': vendas, 'n_anuncios': dados.get('iCO_real'), 'ts': hoje}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--limite', type=int, default=400, help='cartas por rodada')
    ap.add_argument('--dias-refresh', type=int, default=7, help='idade maxima do dado')
    ap.add_argument('--sleep', type=float, default=0.4, help='pausa entre cartas (s)')
    args = ap.parse_args()

    hoje = date.today().isoformat()
    estado = carrega_estado()
    itens = monta_fila(estado, args.dias_refresh)
    total = min(args.limite, len(itens))
    print(f'fila: {len(itens)} cartas a atualizar | cache atual: {len(estado)} | rodada: {total}')
    if not itens:
        return 0

    driver = get_driver()
    ok = sem_dados = erros = 0
    t0 = time.time()
    for i, (k, carta) in enumerate(itens[:args.limite], 1):
        if not carta.get('nEN') or not carta.get('sigla'):
            continue
        try:
            driver.get(url_carta(carta['nEN'], carta['sigla'], num_url(carta)))
            src = ''
            for _ in range(20):
                time.sleep(0.7)
                src = driver.page_source
                if 'cards_editions' in src:
                    break
            if '_cf_chl_opt' in src:
                print('!! cloudflare na pagina da carta - abortando rodada')
                break
            reg = registra(parse_pagina_carta(src), carta, hoje)
            if reg:
                estado[k] = reg
                ok += 1
            else:
                sem_dados += 1
        except Exception as e:  # nao interrompe a rodada
            erros += 1
            print(f'  erro {k}: {str(e)[:70]}')
        if i % 25 == 0 or i == total:
            grava_estado(estado)
            print(f'{i}/{total} | ok {ok} | sem dados {sem_dados} | erros {erros} '
                  f'| {(time.time() - t0) / i:.1f}s/carta')
        time.sleep(args.sleep)

    grava_estado(estado)
    print(f'FIM: {len(estado)} registros em {SAIDA}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
