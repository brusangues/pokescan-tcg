#!/usr/bin/env python
"""
valor_esperado_booster.py — valor esperado (EV) de um booster por coleção,
em R$ (preços da Liga Pokémon).

EV = Σ_raridade  P(pull da raridade) × preço médio das cartas da raridade no set

Fontes:
- data/liga/pull_rates.json      — taxas "1 em X" por set_id (CSV do usuário)
- data/ptcg_cards_cache.json     — rarity por carta (buckets: dr/fa/ar/sir/hr)
- data/scored/scored_*.csv       — preço real BRL por carta (snapshot + hits recentes)
- data/liga/set_*.json           — fallback de preço (p1b) p/ cartas fora do scored

Saída: ranking por set com EV total + breakdown por raridade + EV do filler.
Uso: python script/valor_esperado_booster.py [--custo R$] [--top N]
"""
import argparse
import csv
import glob
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

BUCKETS = {
    'Double Rare': 'dr',
    'Ultra Rare': 'fa',
    'Illustration Rare': 'ar',
    'Special Illustration Rare': 'sir',
    'Hyper Rare': 'hr',
}
BUCKET_LABEL = {'dr': 'Double Rare', 'fa': 'Ultra Rare (FA)', 'ar': 'Illustration Rare', 'sir': 'SIR', 'hr': 'Hyper Rare'}


def _norm_num(x: str) -> str:
    return str(int(x)) if x.isdigit() else x


def _parse_nen(nEN: str):
    """'Eevee ex(174/∞)' ou 'Exeggcute (#001/191)' → (nome_limpo, num)."""
    m = re.match(r'^(.*?)\s*\(#?([^/]+)/', (nEN or '').strip())
    if not m:
        return None
    return m.group(1).strip().lower(), _norm_num(m.group(2).strip())


def load_precos_scored() -> dict:
    """{(nome, num): preco} dos CSVs scored mais recentes (hits + snapshot)."""
    files = sorted(glob.glob(str(REPO / 'data' / 'scored' / 'scored_*.csv')))
    out = {}
    for f in files:
        base = Path(f).name
        if not (base.startswith('scored_hits_') or base.startswith('scored_snapshot_')):
            continue
        try:
            with open(f, encoding='utf-8', newline='') as fh:
                rows = list(csv.DictReader(fh))
        except Exception:
            continue
        for r in rows:
            try:
                preco = float(str(r.get('real_ref') or r.get('preco_real_brl') or 0).replace(',', '.'))
            except (TypeError, ValueError):
                continue
            if preco <= 0:
                continue
            parsed = _parse_nen(r.get('nEN') or r.get('nome_en') or '')
            if not parsed:
                continue
            chave = (parsed[0], _norm_num(r.get('sNumber') or parsed[1]))
            out[chave] = preco
    return out


def load_precos_setjson() -> dict:
    """{(nome, num): preco} — fallback: set_*.json da Liga (p1b médio)."""
    out = {}
    for f in glob.glob(str(REPO / 'data' / 'liga' / 'set_*.json')):
        try:
            d = json.loads(Path(f).read_text(encoding='utf-8'))
        except Exception:
            continue
        if isinstance(d, dict):
            d = d.get('cards') or []
        for c in d:
            try:
                preco = float(c.get('p1b') or 0)
            except (TypeError, ValueError):
                continue
            if preco <= 0:
                continue
            parsed = _parse_nen(c.get('nEN') or '')
            if parsed:
                out[parsed] = preco
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--custo', type=float, default=None, help='Preço do booster em R$ (mostra upside EV−custo)')
    ap.add_argument('--top', type=int, default=20)
    args = ap.parse_args()

    pull = json.loads((REPO / 'data' / 'liga' / 'pull_rates.json').read_text(encoding='utf-8'))
    cache = json.loads((REPO / 'data' / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))

    precos = load_precos_scored()
    precos_set = load_precos_setjson()
    print(f'preços carregados: scored={len(precos)} setjson={len(precos_set)}')

    por_set = {}
    for c in cache:
        s = c['set']['id']
        if s not in pull:
            continue
        por_set.setdefault(s, {'cards': [], 'nome': c['set']['name']})
        por_set[s]['cards'].append(c)

    resultados = []
    for set_id, cfg in pull.items():
        if set_id not in por_set:
            continue
        info = por_set[set_id]
        soma = {b: 0.0 for b in BUCKETS.values()}
        n = {b: 0 for b in BUCKETS.values()}
        filler_soma, filler_n = 0.0, 0
        com_preco = 0
        for c in info['cards']:
            chave = ((c.get('name') or '').strip().lower(), _norm_num(str(c.get('number') or '')))
            preco = precos.get(chave) or precos_set.get(chave)
            if preco is None:
                continue
            com_preco += 1
            bucket = BUCKETS.get(c.get('rarity'))
            if bucket:
                soma[bucket] += preco
                n[bucket] += 1
            else:
                filler_soma += preco
                filler_n += 1

        ev = {}
        total = 0.0
        for b in BUCKETS.values():
            if not n[b]:
                ev[b] = {'media': 0.0, 'n': 0, '1em': cfg.get(b), 'contrib': 0.0}
                continue
            media = soma[b] / n[b]
            taxa = cfg.get(b)
            if not taxa:
                continue
            contrib = media / taxa
            ev[b] = {'media': round(media, 2), 'n': n[b], '1em': taxa, 'contrib': round(contrib, 2)}
            total += contrib
        if filler_n:
            media_filler = filler_soma / filler_n
            p_buckets = sum(1 / cfg[b] for b in BUCKETS.values() if cfg.get(b))
            p_filler = max(0.0, 1.0 - p_buckets)
            contrib_filler = media_filler * p_filler
            ev['filler'] = {'media': round(media_filler, 2), 'n': filler_n,
                            'prob': round(p_filler, 4), 'contrib': round(contrib_filler, 2)}
            total += contrib_filler

        resultados.append({
            'set': set_id,
            'nome': info['nome'],
            'ev': round(total, 2),
            'cobertura': round(com_preco / len(info['cards']) * 100) if info['cards'] else 0,
            'breakdown': ev,
        })

    resultados.sort(key=lambda r: -r['ev'])

    # junta preços de caixa/avulso (Liga) → preço do booster de referência
    caixas = {}
    f_caixas = REPO / 'data' / 'liga' / 'precos_caixas.json'
    if f_caixas.exists():
        caixas = json.loads(f_caixas.read_text(encoding='utf-8')).get('caixas', {})
    for r in resultados:
        info = caixas.get(r['set'])
        if info:
            medio = info['medio']
            r['booster_preco'] = round(medio / 36, 2) if info.get('tipo') == 'caixa' else round(medio, 2)
            r['caixa'] = info
            r['upside'] = round(r['ev'] - r['booster_preco'], 2)
        else:
            r['booster_preco'] = None
            r['upside'] = None

    # ranking por upside (quando houver preço de caixa), senão por EV
    def chave(r):
        return r['upside'] if r['upside'] is not None else -9999
    resultados.sort(key=chave, reverse=True)
    print(f'\n=== EV do booster por coleção (R$, preços Liga — {len(resultados)} sets) ===')
    print(f'{"Set":<9} {"Coleção":<24} {"EV R$":>7} {"Cob.":>5}  breakdown (contrib por raridade)')
    for r in resultados[:args.top]:
        parts = [f"{BUCKET_LABEL.get(b, b)} {v['contrib']:.2f}" for b, v in r['breakdown'].items()]
        linha = f'{r["set"]:<9} {r["nome"]:<24} {r["ev"]:>7.2f} {r["cobertura"]:>4}%  ' + ' | '.join(parts)
        if r['booster_preco'] is not None:
            linha += f'  | booster R${r["booster_preco"]} → upside {r["upside"]:+.2f}'
        print(linha)

    out_path = REPO / 'frontend' / 'public' / 'data' / 'ev_booster.json'
    out_path.write_text(json.dumps(resultados, ensure_ascii=False), encoding='utf-8')
    print(f'\nSalvo em {out_path}')


if __name__ == '__main__':
    main()
