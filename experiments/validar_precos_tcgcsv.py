#!/usr/bin/env python
"""
validar_precos_tcgcsv.py — SANITY: preços TCGCSV vs cache atual (pokemontcg.io).

Compara o marketPrice do TCGCSV (última semana do histórico + amostra da API
ao vivo) com o tcgplayer.prices do cache, para os singles casados (pid_to_card).
Objetivo: confirmar que o TCGCSV É a mesma fonte TCGPlayer antes de integrar.

Uso: python experiments/validar_precos_tcgcsv.py [--ao-vivo]
"""
import argparse
import json
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
EX = REPO / 'experiments' / 'tcgcsv'
UA = {'User-Agent': 'pokescan-tcg-sanity/0.1'}


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ao-vivo', action='store_true', help='também puxa a API ao vivo (amostra)')
    args = ap.parse_args()

    cache = json.loads((REPO / 'data' / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
    pid2card = json.loads((EX / 'pid_to_card.json').read_text(encoding='utf-8'))

    hist = pd.read_csv(EX / 'historico_en.csv', dtype={'productId': str})
    ultima = sorted(hist['data'].unique())[-1]
    h = hist[hist['data'] == ultima]
    tcgcsv_last = {}
    for pid, g in h.groupby('productId'):
        vals = {}
        for _, r in g.iterrows():
            if r['market_price'] > 0:
                vals.setdefault(r['subtype'], r['market_price'])
        tcgcsv_last[pid] = vals
    print(f'TCGCSV última semana ({ultima}): {len(tcgcsv_last):,} pids com preço')

    cache_preco = {}
    for c in cache:
        tp = (c.get('tcgplayer') or {}).get('prices') or {}
        for variant in ('holofoil', 'normal', 'reverseHolofoil'):
            v = tp.get(variant)
            if v and v.get('market'):
                cache_preco[c['id']] = (variant, v['market'])
                break

    sub_map = {'holofoil': 'Holofoil', 'normal': 'Normal', 'reverseHolofoil': 'Reverse Holofoil'}
    linhas = []
    for pid, cid in pid2card.items():
        if cid not in cache_preco:
            continue
        vals = tcgcsv_last.get(pid)
        if not vals:
            continue
        var_cache, p_cache = cache_preco[cid]
        subt = next((s for s in ('Holofoil', 'Normal', 'Reverse Holofoil') if s in vals), None)
        if subt is None:
            continue
        linhas.append({'pid': pid, 'card': cid, 'subtype': subt,
                       'tcgcsv': vals[subt], 'cache': p_cache, 'cache_variant': var_cache,
                       'tcgcsv_mesma_var': vals.get(sub_map[var_cache])})
    df = pd.DataFrame(linhas)
    df['delta'] = df['tcgcsv'] - df['cache']
    df['delta_rel'] = df['delta'] / df['cache'].replace(0, np.nan)

    print(f'join: {len(df):,} singles | TCGCSV vs cache')
    print(f'  correlação (log): {np.corrcoef(np.log(df["tcgcsv"]), np.log(df["cache"]))[0,1]:.4f}')
    print(f'  delta: média={df["delta"].mean():+.4f} | mediana={df["delta"].median():+.4f} | '
          f'p95 abs={np.percentile(df["delta"].abs(), 95):.4f}')
    print(f'  delta_rel: mediana={df["delta_rel"].median()*100:+.2f}% | '
          f'|rel|>10%: {(df["delta_rel"].abs() > 0.10).mean()*100:.1f}% das cartas')
    print(f'  mesma variante escolhida (holo/normal/reverse): {(df["subtype"].str.lower() == df["cache_variant"]).mean()*100:.1f}%')

    mm = df[df['tcgcsv_mesma_var'].notna()].copy()
    mm['delta_mm'] = mm['tcgcsv_mesma_var'] - mm['cache']
    mm['delta_mm_rel'] = mm['delta_mm'] / mm['cache'].replace(0, np.nan)
    print(f'\nMESMA VARIANTE ({len(mm):,} cards — TCGCSV também tem a variante do cache):')
    print(f'  delta: mediana={mm["delta_mm"].median():+.4f} | média={mm["delta_mm"].mean():+.4f} | '
          f'|rel|>5%: {(mm["delta_mm_rel"].abs() > 0.05).mean()*100:.1f}% | '
          f'|rel|>20%: {(mm["delta_mm_rel"].abs() > 0.20).mean()*100:.1f}%')
    print(f'  correlação (log): {np.corrcoef(np.log(mm["tcgcsv_mesma_var"]), np.log(mm["cache"]))[0,1]:.4f}')

    sem = df[df['tcgcsv_mesma_var'].isna() & (df['cache_variant'] == 'normal')]
    print(f'\nCobertura de variantes no cache: {df["cache_variant"].value_counts().to_dict()}')
    print(f'  TCGCSV com outra variante (ex: Holofoil) onde o cache só tinha normal: {len(sem):,} cards '
          f'— o TCGCSV revela preço de variante que o cache não tem')

    print('\nexemplos (maiores |delta_rel|, mesma variante):')
    mm_sorted = mm.reindex(mm['delta_mm_rel'].abs().sort_values(ascending=False).index)
    for _, r in mm_sorted.head(6).iterrows():
        print(f'  {r["card"]:14s} {r["cache_variant"]:18s} tcgcsv=${r["tcgcsv_mesma_var"]:.2f} '
              f'cache=${r["cache"]:.2f} Δrel={r["delta_mm_rel"]*100:+.0f}%')

    if args.ao_vivo:
        print('\nAPI ao vivo (amostra de 10 grupos)...')
        groups = get_json('https://tcgcsv.com/tcgplayer/3/groups').get('results', [])
        ao_vivo = {}
        for g in groups[:10]:
            try:
                pr = get_json(f'https://tcgcsv.com/tcgplayer/3/{g["groupId"]}/prices')
            except Exception:
                continue
            for p in pr.get('results', []):
                ao_vivo.setdefault(str(p['productId']), {})
                ao_vivo[str(p['productId'])][p.get('subTypeName')] = p.get('marketPrice')
            time.sleep(0.2)
        casados = 0
        diff_total = 0.0
        for pid, cid in pid2card.items():
            if cid not in cache_preco or pid not in ao_vivo:
                continue
            vals = ao_vivo[pid]
            subt = next((s for s in ('Holofoil', 'Normal', 'Reverse Holofoil') if s in vals), None)
            if subt is None:
                continue
            casados += 1
            diff_total += abs(vals[subt] - cache_preco[cid][1])
        print(f'  ao vivo vs cache: {casados} casados | MAD={diff_total / max(casados, 1):.4f} USD')


if __name__ == '__main__':
    main()