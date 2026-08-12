#!/usr/bin/env python
"""
inspecionar_historico.py — junta o histórico semanal com o catálogo local e
mostra cobertura/qualidade (NÃO treina nada).

Uso: python experiments/inspecionar_historico.py
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
EX = REPO / 'experiments' / 'tcgcsv'

def main():
    hist = pd.read_csv(EX / 'historico_en.csv', dtype={'productId': str})
    products = json.loads((EX / 'products_en.json').read_text(encoding='utf-8'))
    cache = json.loads((REPO / 'data' / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))

    print(f'Histórico: {len(hist):,} linhas | {hist["data"].nunique()} semanas | '
          f'{hist["productId"].nunique():,} productIds | '
          f'{hist["data"].min()} → {hist["data"].max()}')

    # semanas: contagem e integridade
    por_semana = hist.groupby('data')['productId'].nunique()
    print('\nSemanas (productIds únicos):')
    for d, n in por_semana.items():
        print(f'  {d}: {n:,}')

    # join com o catálogo: productId → (set_id, number)
    set_norm_para_id = {}
    for c in cache:
        s = c.get('set') or {}
        sid = s.get('id') if isinstance(s, dict) else None
        sname = s.get('name') if isinstance(s, dict) else None
        if sid and sname:
            set_norm_para_id.setdefault(''.join(ch for ch in sname.lower() if ch.isalnum()), sid)
    by_set_num = {}
    for c in cache:
        sid = (c.get('set') or {}).get('id') if isinstance(c.get('set'), dict) else c.get('set')
        by_set_num.setdefault((sid, str(c.get('number', ''))), c.get('id'))

    casados = 0
    meta_ok = 0
    for pid, m in products.items():
        if not m.get('number'):
            continue
        meta_ok += 1
        sid = set_norm_para_id.get(''.join(ch for ch in (m.get('group', '').split(':', 1)[-1].replace('Base Set', '').strip().lower()) if ch.isalnum()))
        if sid and by_set_num.get((sid, m['number'])):
            casados += 1
    print(f'\nJoin produtos→catálogo: {casados:,}/{meta_ok:,} com número '
          f'({casados / max(meta_ok, 1) * 100:.1f}%)')

    # cobertura do histórico sobre os 12.8k singles casados: quantas semanas tem cada um
    pids_com_meta = {pid for pid, m in products.items() if m.get('number')}
    cobertura = hist[hist['productId'].isin(pids_com_meta)].groupby('productId')['data'].nunique()
    print(f'productIds com meta: {len(pids_com_meta):,}')
    print(f'com série no histórico: {len(cobertura):,}')
    if len(cobertura):
        print(f'  com todas as {hist["data"].nunique()} semanas: {(cobertura == hist["data"].nunique()).sum():,}')
        print(f'  mediana de semanas por carta: {cobertura.median():.0f}')

    # exemplo de série (3 cartas mais comuns do cache)
    print('\nExemplo de séries (market_price por semana, top por productId):')
    amostra = hist.groupby('productId')['data'].count().sort_values(ascending=False).head(3).index
    for pid in amostra:
        serie = hist[hist['productId'] == pid].sort_values('data')
        m = products.get(pid, {})
        print(f'\n  {pid} — {m.get("name", "?")[:40]} ({m.get("group", "?")[:30]})')
        for _, r in serie.iterrows():
            print(f'    {r["data"]}  {r["subtype"]:20s} ${r["market_price"]:.2f}')

if __name__ == '__main__':
    main()
