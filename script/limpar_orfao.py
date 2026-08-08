#!/usr/bin/env python
"""
limpar_orfao.py — remove ids órfãos dos dados de produção (P2.14).

Órfãos = cartas que SAÍRAM do ptcg_cards_cache (ids renomeados/removidos pela
TCGAPI, ex: sm3.5-*) mas continuam nos arquivos de embeddings e no img_cache.

Limpa:
  1. data/pokemon_embeddings_base32.csv  (produção — usado pelo modelo)
  2. data/img_cache/*  (imagens baixadas)

NÃO mexe nos legados de experimento (16d.csv, .npy, exp_embeddings/) nem no
índice do scanner (build_search_index.py regenera do cache).

Uso: python script/limpar_orfao.py
"""
import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / 'data' / 'ptcg_cards_cache.json'
EMBED = REPO / 'data' / 'pokemon_embeddings_base32.csv'
IMG_DIR = REPO / 'data' / 'img_cache'


def main():
    cache = json.loads(CACHE.read_text(encoding='utf-8'))
    ids = {c['id'] for c in cache}
    print(f'cache: {len(ids)} cartas')

    # 1. embeddings base32
    if EMBED.exists():
        linhas = list(csv.DictReader(open(EMBED, encoding='utf-8')))
        antes = len(linhas)
        mantidas = [r for r in linhas if (r.get('id') or '') in ids]
        with open(EMBED, 'w', encoding='utf-8', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=linhas[0].keys())
            w.writeheader()
            w.writerows(mantidas)
        print(f'embeddings: {antes} → {len(mantidas)} (removidos {antes - len(mantidas)})')

    # 2. imagens órfãs
    if IMG_DIR.exists():
        removidas = 0
        for f in IMG_DIR.iterdir():
            if f.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp') and f.stem not in ids:
                f.unlink()
                removidas += 1
        print(f'imagens: removidas {removidas} órfãs de {IMG_DIR.name}')

    print('feito.')


if __name__ == '__main__':
    main()
