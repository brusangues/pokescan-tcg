#!/usr/bin/env python
"""
reanalisar_sets.py — re-avalia o set_map do edicoes_liga.json por casamento
de NOMES com o catálogo (a numeração dos sets latinos/PT difere da EN, então
o n_overlap por número engana). Usa gate de confiança para só propor trocas
sólidas. Só PROPÕE (não escreve) — informe o --aplicar para gravar.
"""
import json
import os
import sys
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ED = os.path.join(BASE, 'data', 'liga', 'edicoes_liga.json')
CACHE = os.path.join(BASE, 'data', 'ptcg_cards_cache.json')

cache = json.load(open(CACHE, encoding='utf-8'))
nome_por_set = defaultdict(set)
for c in cache:
    nome_por_set[c['set']['id']].add(c['name'].lower())

ed = json.load(open(ED, encoding='utf-8'))


def nomes_edicao(ide):
    f = os.path.join(BASE, 'data', 'liga', f'set_{ide}.json')
    if not os.path.exists(f):
        return set()
    d = json.load(open(f, encoding='utf-8'))
    return set(r['nEN'].split('(')[0].strip().lower() for r in d)


def main():
    aplicar = '--aplicar' in sys.argv
    propostas = []
    for ide, e in ed.items():
        if not isinstance(e, dict):
            continue
        no = e.get('n_overlap')
        n = e.get('n') or 1
        if e.get('set') is not None and no is not None and no >= max(10, 0.5 * n):
            continue  # overlap alto → mapping confiável, pula
        N = nomes_edicao(ide)
        if not N or len(N) < 5:
            continue
        # cobertura por set do catálogo
        cov = {}
        for sid, snomes in nome_por_set.items():
            inter = len(N & snomes)
            if inter > 0:
                cov[sid] = inter / len(N)
        if not cov:
            continue
        top = sorted(cov.items(), key=lambda x: -x[1])[:4]
        melhor, melhor_cov = top[0]
        segundo = top[1][1] if len(top) > 1 else 0
        atual = e.get('set')
        # gate: melhor set cobre >= 50% dos nomes e é >1.6x o segundo
        confiavel = melhor_cov >= 0.50 and melhor_cov >= 1.6 * segundo
        flag = '***' if (confiavel and atual and melhor != atual) else '   '
        propostas.append((flag, ide, e.get('sigla'), atual, melhor, round(melhor_cov, 2), round(segundo, 2), n, no, e.get('lang')))

    propostas.sort(key=lambda x: (x[0] != '***', -x[5]))
    print(f"{'':4}{'idE':>4} {'sigla':<7}{'atual':<8}{'melhor':<10}{'cov1':>5}{'cov2':>5}{'n':>5}{'no':>5} lang")
    for flag, ide, sig, atual, melhor, c1, c2, n, no, lang in propostas:
        print(f"{flag} {ide:>4} {str(sig or '-'):<7}{str(atual or '-'):<8}{str(melhor or '-'):<10}{c1:>5}{c2:>5}{n:>5}{str(no):>5} {lang}")

    if aplicar:
        # grava só as marcadas *** (confiáveis e diferentes do atual)
        gravou = []
        for flag, ide, sig, atual, melhor, c1, c2, n, no, lang in propostas:
            if flag == '***':
                ed[ide]['set'] = melhor
                gravou.append((ide, atual, melhor))
        json.dump(ed, open(ED, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'\nGRAVADAS {len(gravou)} trocas em edicoes_liga.json:')
        for ide, a, m in gravou:
            print(f'  {ide}: {a} -> {m}')


if __name__ == '__main__':
    main()