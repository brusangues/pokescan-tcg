#!/usr/bin/env python
"""
validate_tcgcsv.py — VALIDAÇÃO do TCGCSV Archive (NÃO toca no modelo produtivo).

Valida:
1. Formato do archive diário (preços TCGPlayer por productId)
2. Join productId ↔ nossa chave: group name (set) + extendedData Number
3. Cobertura: quantas das nossas cartas com preço USD casam com o archive
4. Sanity check: preço do archive vs preço embutido do pokemontcg.io (mesma fonte)

Uso: python experiments/validate_tcgcsv.py [--dia 2026-08-01]
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import urllib.request

REPO = Path(__file__).resolve().parent.parent
EX = REPO / 'experiments' / 'tcgcsv'
CACHE = json.loads((REPO / 'data' / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
CAT = '3'


def get(url: str, retries: int = 3) -> dict:
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'pokescan-tcg-validation/0.1'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(1.5 * (i + 1))


def norm(s: str) -> str:
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def set_name_do_grupo(group_name: str) -> str:
    """'SWSH01: Sword & Shield Base Set' → 'Sword & Shield' (limpo)."""
    nome = group_name.split(':', 1)[-1].strip() if ':' in group_name else group_name
    nome = nome.replace('Base Set', '').replace('&amp;', '&').strip()
    return nome


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dia', default='2026-08-01')
    args = ap.parse_args()

    # 0. Catálogo local: set name normalizado → set id; (set id, number) → card id
    set_norm_para_id = {}
    for c in CACHE:
        s = c.get('set') or {}
        sid = s.get('id') if isinstance(s, dict) else None
        sname = s.get('name') if isinstance(s, dict) else None
        if sid and sname:
            set_norm_para_id.setdefault(norm(sname), sid)
    by_set_num = {}
    for c in CACHE:
        sid = (c.get('set') or {}).get('id') if isinstance(c.get('set'), dict) else c.get('set')
        by_set_num.setdefault((sid, str(c.get('number', ''))), c.get('id'))
    # id → card (para o sanity check)
    by_id = {c.get('id'): c for c in CACHE}
    print(f'0) Catálogo local: {len(set_norm_para_id)} sets | {len(by_set_num):,} cartas')

    # 1. Preços do archive (categoria Pokémon)
    prices = {}
    preco_files = sorted((EX / args.dia / CAT).glob('*/prices'))
    for f in preco_files:
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            continue
        for p in data.get('results', []):
            prices.setdefault(p['productId'], []).append(p)
    print(f'1) Archive {args.dia}: {len(preco_files)} grupos | {len(prices):,} productIds com preço')

    # 2. Groups + products (todos os 217 grupos)
    groups = get(f'https://tcgcsv.com/tcgplayer/{CAT}/groups').get('results', [])
    products = {}  # productId -> {set_id, set_nome, number, rarity, name}
    group_ok = 0
    for gi, g in enumerate(groups):
        gid = g['groupId']
        try:
            prods = get(f'https://tcgcsv.com/tcgplayer/{CAT}/{gid}/products')
        except Exception:
            continue
        sname = set_name_do_grupo(g.get('name', ''))
        sid = set_norm_para_id.get(norm(sname))
        if sid:
            group_ok += 1
        for pr in prods.get('results', []):
            ext = {e.get('name'): e.get('value') for e in pr.get('extendedData', [])}
            num_raw = str(ext.get('Number') or '')
            products[pr['productId']] = {
                'set_id': sid, 'set_nome': sname,
                # TCGPlayer: '053/202' → '53' (número/total)
                'number': num_raw.split('/')[0].lstrip('0') if num_raw else '',
                'rarity': ext.get('Rarity'), 'name': pr.get('name', ''),
            }
        if (gi + 1) % 50 == 0:
            print(f'   groups {gi+1}/{len(groups)} processados ({len(products):,} products)')
        time.sleep(0.15)
    print(f'2) Products: {len(products):,} | grupos com set mapeado no catálogo: {group_ok}/{len(groups)}')

    # 3. Join com o catálogo
    casados = 0
    com_num = 0
    exemplos = []
    for pid, meta in products.items():
        if not meta['set_id'] or not meta['number']:
            continue
        com_num += 1
        cid = by_set_num.get((meta['set_id'], meta['number']))
        if cid:
            casados += 1
            if len(exemplos) < 8:
                exemplos.append((pid, meta['set_id'], meta['number'], cid, meta['name'][:40]))
    print(f'3) JOIN: {casados:,}/{com_num:,} singles com (set,num) casaram ({casados / max(com_num, 1) * 100:.1f}%)')
    for pid, s, n, cid, nome in exemplos:
        print(f'   {pid} → {cid:12s} ({s} #{n}: {nome})')

    # 4. Sanity check de preço (archive vs cache — mesma fonte TCGPlayer)
    print('4) Sanity check (marketPrice archive vs tcgplayer do cache):')
    checados = 0
    for pid, meta in products.items():
        if pid not in prices or not meta['set_id'] or not meta['number']:
            continue
        cid = by_set_num.get((meta['set_id'], meta['number']))
        c = by_id.get(cid or '')
        if not c:
            continue
        tp_prices = (c.get('tcgplayer') or {}).get('prices') or {}
        for linha in prices[pid]:
            key = {'Normal': 'normal', 'Holofoil': 'holofoil', 'Reverse Holofoil': 'reverseHolofoil'}.get(linha.get('subTypeName'))
            if not key:
                continue
            cache_market = (tp_prices.get(key) or {}).get('market')
            if cache_market:
                arq = linha.get('marketPrice')
                print(f'   {cid:12s} {linha.get("subTypeName"):18s} archive=${arq} cache=${cache_market:.2f} Δ={ (arq or 0) - cache_market:+.2f}')
                checados += 1
                break
        if checados >= 6:
            break

    print(f'\n=== RESUMO ===')
    print(f'archive {args.dia}: {len(prices):,} productIds | products TCGCSV: {len(products):,} | join: {casados}/{com_num} singles')


if __name__ == '__main__':
    main()
