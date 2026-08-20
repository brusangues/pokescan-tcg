#!/usr/bin/env python
"""
revisar_setmap.py — ferramenta de decisão p/ o P1.31: revisar o set_map de
todas as edições (especialmente as grandes e as suspeitas).

A numeração das edições latinas/PT difere da EN, então o match por número
falha. A ferramenta identifica o set EN correto por NOMES DISTINTIVOS:
nomes que aparecem em poucos sets do catálogo valem mais (ex. um Trainer
único, um ex raro) — isso elimina o ruído dos Pokémon comuns (Caterpie,
Pikachu...) que existem em dezenas de sets.

Saída: por edição (com --min-n e --suspeitos), o set mapeado + top candidatos
por pontuação distintiva + amostra dos nomes distintivos que casam.

Uso:
  python experiments/revisar_setmap.py                 # todas as edições com set
  python experiments/revisar_setmap.py --suspeitos     # só n_overlap baixo
  python experiments/revisar_setmap.py --min-n 50      # só edições grandes
"""
import argparse
import json
import os
from collections import defaultdict, Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ED = os.path.join(BASE, 'data', 'liga', 'edicoes_liga.json')
CACHE = os.path.join(BASE, 'data', 'ptcg_cards_cache.json')

cache = json.load(open(CACHE, encoding='utf-8'))
# nome -> set de ids onde aparece
nome_sets = defaultdict(set)
for c in cache:
    nome_sets[c['name'].lower()].add(c['set']['id'])
# qtde de sets por nome (raridade do nome)
nome_raridade = {nm: len(s) for nm, s in nome_sets.items()}

ed = json.load(open(ED, encoding='utf-8'))


def nomes_edicao(ide):
    f = os.path.join(BASE, 'data', 'liga', f'set_{ide}.json')
    if not os.path.exists(f):
        return None, None
    d = json.load(open(f, encoding='utf-8'))
    nomes = set(r['nEN'].split('(')[0].strip().lower() for r in d)
    nens = [(r['nEN'], r.get('sN')) for r in d]
    return nomes, nens


def pontuar(nomes_ed):
    """pontua cada set do catálogo pela soma de (1/raridade) dos nomes que casam."""
    score = defaultdict(float)
    contagem = defaultdict(int)
    for nm in nomes_ed:
        w = 1.0 / nome_raridade.get(nm, 1)
        for sid in nome_sets.get(nm, ()):
            score[sid] += w
            contagem[sid] += 1
    return score, contagem


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--suspeitos', action='store_true')
    ap.add_argument('--min-n', type=int, default=0)
    ap.add_argument('--ide', help='edição específica p/ inspecionar')
    args = ap.parse_args()

    if args.ide:
        _inspect(args.ide)
        return

    linhas = []
    for ide, e in ed.items():
        if not isinstance(e, dict):
            continue
        atual = e.get('set')
        if atual is None:
            continue
        n = e.get('n') or 0
        no = e.get('n_overlap')
        if n < args.min_n:
            continue
        if args.suspeitos and no is not None and no >= max(10, 0.5 * n):
            continue  # overlap alto = confiável
        nomes, _ = nomes_edicao(ide)
        if not nomes:
            continue
        score, cont = pontuar(nomes)
        if not score:
            continue
        top = sorted(score.items(), key=lambda x: -x[1])[:3]
        melhor = top[0][0]
        tot_nomes = len(nomes)
        cov_melhor = cont[melhor] / tot_nomes if tot_nomes else 0
        flag = 'ERR ' if (melhor != atual) else 'ok  '
        linhas.append((flag, ide, e.get('sigla'), atual, top, cont, round(cov_melhor, 2), n, no, e.get('lang')))

    linhas.sort(key=lambda x: (x[0] != 'ERR', -x[7]))
    for flag, ide, sig, atual, top, cont, cov, n, no, lang in linhas:
        t = ' | '.join(f'{s}({cont[s]}n)' for s, _ in top)
        print(f'{flag} idE {ide:>4} {str(sig or "-"):<7} atual={str(atual or "-"):<8} -> {t} | cov(1º)={cov} n={n} no={no} lang={lang}')


def _inspect(ide):
    nomes, nens = nomes_edicao(ide)
    if not nomes:
        print('sem set file')
        return
    score, cont = pontuar(nomes)
    print(f'=== idE {ide} ({ed[ide].get("sigla")}) mapeado={ed[ide].get("set")} n={len(nomes)} ===')
    top = sorted(score.items(), key=lambda x: -x[1])[:6]
    for sid, sc in top:
        print(f'  {sid:<9} score={sc:.1f} nomes={cont[sid]}/{len(nomes)}')
    # nomes distintivos (rários) que casam no top1 e top2
    s1 = top[0][0]
    s2 = top[1][0] if len(top) > 1 else None
    print('  nomes que casam no top1 mas não no top2 (distintivos):')
    if s2:
        for nm in sorted(nomes):
            if s1 in nome_sets.get(nm, ()) and (not s2 or s2 not in nome_sets.get(nm, ())):
                if nome_raridade.get(nm, 9) <= 4:
                    print(f'    - {nm} (em {nome_raridade.get(nm)} sets)')
    print('  amostra nEN:', [x for x, _ in list(nens)[:8]])


if __name__ == '__main__':
    main()