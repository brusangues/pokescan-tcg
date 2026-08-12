#!/usr/bin/env python
"""
puxar_historico_semanal.py — histórico semanal de preços TCGCSV (cat. 3 = EN).

Baixa o archive diário de UMA data por semana (últimos 6 meses ~ 26 semanas),
extrai só a categoria 3, consolida o marketPrice por productId e salva:
  experiments/tcgcsv/products_en.json   — productId → {group, name, number, rarity}
  experiments/tcgcsv/historico_en.csv   — data, productId, subtype, market_price

NÃO toca no produtivo (tudo em experiments/tcgcsv/, gitignored).

Uso: python experiments/puxar_historico_semanal.py [--semanas 26] [--apenas-mapear]
"""
import argparse
import csv
import json
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EX = REPO / 'experiments' / 'tcgcsv'
UA = {'User-Agent': 'pokescan-tcg-historico/0.1'}


def get_bytes(url: str, retries: int = 3, timeout: int = 90) -> bytes:
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            if i == retries - 1:
                raise
            print(f'   retry {i + 1} ({e})', flush=True)
            time.sleep(2 * (i + 1))


def mapear_products() -> dict:
    """Uma vez: groups + products da cat. 3 → productId → meta (para o join)."""
    groups = json.loads(get_bytes('https://tcgcsv.com/tcgplayer/3/groups').decode()).get('results', [])
    products = {}
    for gi, g in enumerate(groups):
        try:
            prods = json.loads(get_bytes(f'https://tcgcsv.com/tcgplayer/3/{g["groupId"]}/products').decode())
        except Exception as e:
            print(f'   groups {g["groupId"]} falhou: {e}', flush=True)
            continue
        for pr in prods.get('results', []):
            ext = {e.get('name'): e.get('value') for e in pr.get('extendedData', [])}
            num_raw = str(ext.get('Number') or '')
            products[pr['productId']] = {
                'group': g.get('name', ''),
                'name': pr.get('name', ''),
                # TCGPlayer: '053/202' → '53'
                'number': num_raw.split('/')[0].lstrip('0') if num_raw else '',
                'rarity': ext.get('Rarity'),
            }
        if (gi + 1) % 50 == 0:
            print(f'   products: {gi + 1}/{len(groups)} groups | {len(products):,} productIds', flush=True)
        time.sleep(0.15)
    return products


def semana(dia: date) -> list[dict]:
    """Baixa o archive do dia, extrai só a cat. 3, devolve [{productId, subtype, market_price}]."""
    url = f'https://tcgcsv.com/archive/tcgplayer/prices-{dia}.ppmd.7z'
    arq7z = EX / f'prices-{dia}.ppmd.7z'
    out = EX / f'w_{dia}'
    print(f'  baixando {url}...', flush=True)
    arq7z.write_bytes(get_bytes(url))
    if out.exists():
        shutil.rmtree(out)
    r = subprocess.run(['7z', 'x', str(arq7z), f'-o{out}', f'{dia}/3/*', '-y'],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f'  7z falhou: {r.stderr[-300:]}', flush=True)
        raise SystemExit(1)
    arq7z.unlink()
    precos = []
    for f in (out / str(dia) / '3').glob('*/prices'):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            continue
        for linha in data.get('results', []):
            preco = linha.get('marketPrice')
            if preco is None:
                continue
            precos.append({
                'productId': linha['productId'],
                'subtype': linha.get('subTypeName') or '',
                'market_price': preco,
            })
    shutil.rmtree(out)
    return precos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--semanas', type=int, default=26)
    ap.add_argument('--apenas-mapear', action='store_true')
    args = ap.parse_args()

    EX.mkdir(exist_ok=True)

    if args.apenas_mapear or not (EX / 'products_en.json').exists():
        print('Mapeando products (cat. 3)...', flush=True)
        products = mapear_products()
        (EX / 'products_en.json').write_text(json.dumps(products, ensure_ascii=False), encoding='utf-8')
        print(f'  {len(products):,} productIds salvos em products_en.json', flush=True)
        if args.apenas_mapear:
            return
    else:
        products = json.loads((EX / 'products_en.json').read_text(encoding='utf-8'))
        print(f'products_en.json já existe ({len(products):,} productIds)', flush=True)

    dias = [(date.today() - timedelta(days=1) - timedelta(weeks=i)) for i in range(args.semanas)]
    print(f'Baixando {len(dias)} semanas: {dias[-1]} → {dias[0]}', flush=True)

    csv_path = EX / 'historico_en.csv'
    ja_tem = set()
    if csv_path.exists():
        with open(csv_path, encoding='utf-8') as fh:
            ja_tem = {r[0] for r in csv.reader(fh) if r and r[0] != 'data'}
        print(f'  retomando: {len(ja_tem)} semanas já baixadas', flush=True)

    with open(csv_path, 'a', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        if not ja_tem:
            w.writerow(['data', 'productId', 'subtype', 'market_price'])
        for dia in dias:
            if str(dia) in ja_tem:
                print(f'{dia} já baixado — pulando', flush=True)
                continue
            try:
                precos = semana(dia)
            except Exception as e:
                print(f'  {dia} FALHOU: {e} — continuando', flush=True)
                continue
            w.writerows([str(dia), p['productId'], p['subtype'], p['market_price']] for p in precos)
            fh.flush()
            print(f'{dia}: {len(precos):,} linhas de preço ({len(set(p["productId"] for p in precos)):,} productIds)', flush=True)

    print('\n=== RESUMO ===')
    total = sum(1 for _ in open(csv_path, encoding='utf-8')) - 1
    print(f'historico_en.csv: {total:,} linhas ({len(ja_tem) + args.semanas} semanas)')


if __name__ == '__main__':
    main()
