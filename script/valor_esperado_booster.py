#!/usr/bin/env python
"""
valor_esperado_booster.py — valor esperado (EV) de um booster por coleção, em R$.

EV = Σ_raridade  P(pull da raridade) × preço médio das cartas da raridade no set

Fontes de PULL RATE (flag --fonte):
  en (default) — estudos EN (ThePriceDex/TCGPlayer): data/liga/pull_rates_en.json
                 ajustado para o booster PT-BR de 6 cartas com --fator (default 0.5,
                 ou seja, "dividir pela metade": o booster EN tem 11 cartas).
  br           — cronograma oficial BR (CSV do usuário): data/liga/pull_rates.json

Fontes de PREÇO (R$, Liga Pokémon):
  data/scored/scored_*.csv  — preço real por carta (snapshot + hits)
  data/liga/set_*.json      — fallback (p1b)

Saída: ranking por set com EV total + breakdown por raridade + preço de caixa.
Uso: python script/valor_esperado_booster.py [--fonte en|br] [--fator 0.5] [--top N]
"""
import argparse
import csv
import glob
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# rarity do cache ptcg → bucket interno
BUCKET_POR_RARITY = {
    'Hyper Rare': 'hr',
    'Mega Hyper Rare': 'hr',
    'Special Illustration Rare': 'sir',
    'Ultra Rare': 'fa',
    'Illustration Rare': 'ar',
    'Double Rare': 'dr',
    'ACE SPEC Rare': 'ace',
    'Shiny Ultra Rare': 'shiny_ur',
    'Shiny Rare': 'shiny',
    'Mega Attack Rare': 'matk',
    'MEGA_ATTACK_RARE': 'matk',
    'Rare': 'rare',
    'Uncommon': 'uncommon',
    'Common': 'common',
}
BUCKET_LABEL = {
    'hr': 'Hyper Rare', 'sir': 'SIR', 'fa': 'Ultra Rare (FA)', 'ar': 'Illustration Rare',
    'dr': 'Double Rare', 'ace': 'ACE SPEC', 'shiny_ur': 'Shiny Ultra Rare', 'shiny': 'Shiny Rare',
    'matk': 'Mega Attack Rare', 'rare': 'Rare', 'uncommon': 'Uncommon', 'common': 'Common', 'filler': 'Outras',
}
# nome da rarity no ThePriceDex → bucket
EN_POR_BUCKET = {
    'hr': ['Hyper Rare', 'Mega Hyper Rare'],
    'sir': ['Special Illustration Rare'],
    'fa': ['Ultra Rare'],
    'ar': ['Illustration Rare'],
    'dr': ['Double Rare'],
    'ace': ['ACE SPEC Rare'],
    'shiny_ur': ['Shiny Ultra Rare'],
    'shiny': ['Shiny Rare'],
    'matk': ['Mega Attack Rare'],
    'rare': ['Rare'],
    'uncommon': ['Uncommon'],
    'common': ['Common'],
}


def _norm_num(x: str) -> str:
    return str(int(x)) if x.isdigit() else x


def _parse_nen(nEN: str):
    """'Eevee ex(174/∞)' ou 'Exeggcute (#001/191)' → (nome_limpo, num)."""
    m = re.match(r'^(.*?)\s*\(#?([^/]+)/', (nEN or '').strip())
    if not m:
        return None
    return m.group(1).strip().lower(), _norm_num(m.group(2).strip())


def load_precos_por_sigla() -> dict:
    """{sigla: {(nome, num): preco}} — scored CSVs (hits + snapshot), agrupado por sigla da Liga.

    A chave inclui a SIGLA para evitar colisões entre sets (ex: 'Togekiss 85' existe
    em vários sets com preços diferentes).
    """
    files = sorted(glob.glob(str(REPO / 'data' / 'scored' / 'scored_*.csv')))
    out: dict[str, dict] = {}
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
            sigla = (r.get('sSigla') or r.get('sigla') or '').upper()
            if not sigla:
                continue
            chave = (parsed[0], _norm_num(r.get('sNumber') or parsed[1]))
            out.setdefault(sigla, {})[chave] = preco
    return out


def load_precos_setjson() -> dict:
    """{sigla: {(nome, num): preco}} — set_*.json da Liga (p1b médio), por sigla."""
    out: dict[str, dict] = {}
    for f in glob.glob(str(REPO / 'data' / 'liga' / 'set_*.json')):
        try:
            d = json.loads(Path(f).read_text(encoding='utf-8'))
        except Exception:
            continue
        if isinstance(d, dict):
            d = d.get('cards') or []
        if not isinstance(d, list) or not d or 'sSigla' not in d[0]:
            continue
        sigla = d[0]['sSigla'].upper()
        sub = out.setdefault(sigla, {})
        for c in d:
            try:
                preco = float(c.get('p1b') or 0)
            except (TypeError, ValueError):
                continue
            if preco <= 0:
                continue
            parsed = _parse_nen(c.get('nEN') or '')
            if parsed:
                sub[parsed] = preco
    return out


def melhor_sigla(set_id: str, cards: list, por_sigla: dict, min_matches: int = 3) -> str | None:
    """Acha a sigla da Liga com maior overlap de cartas com o set (nome+num)."""
    alvo = set()
    for c in cards[:120]:
        alvo.add(((c.get('name') or '').strip().lower(), _norm_num(str(c.get('number') or ''))))
    melhor, melhor_n = None, 0
    for sigla, sub in por_sigla.items():
        n = len(alvo & sub.keys())
        if n > melhor_n:
            melhor, melhor_n = sigla, n
    if melhor_n < min_matches:
        return None
    return melhor


def pull_rates_para_buckets(fonte: str, fator: float, set_id: str) -> tuple[dict, float]:
    """Retorna ({bucket: taxa_por_booster}, p_buckets_total) com o fator aplicado."""
    if fonte == 'br':
        path = REPO / 'data' / 'liga' / 'pull_rates.json'
        cfg = json.loads(path.read_text(encoding='utf-8')).get(set_id)
        if not cfg:
            return {}, 0.0
        chaves = {'dr': 'dr', 'fa': 'fa', 'ar': 'ar', 'sir': 'sir', 'hr': 'hr'}
        rates = {}
        for b, ch in chaves.items():
            den = cfg.get(ch)
            if den:
                rates[b] = 1.0 / den * fator
        return rates, sum(rates.values())

    path = REPO / 'data' / 'liga' / 'pull_rates_en.json'
    dados = json.loads(path.read_text(encoding='utf-8'))
    info = dados.get(set_id)
    if not info:
        return {}, 0.0
    pr = info.get('pull_rates', {})
    rates = {}
    for b, nomes in EN_POR_BUCKET.items():
        for nome in nomes:
            if nome in pr and pr[nome].get('1em'):
                rates[b] = 1.0 / pr[nome]['1em'] * fator
                break
    return rates, sum(rates.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fonte', choices=['en', 'br'], default='en')
    ap.add_argument('--fator', type=float, default=6 / 11,
                    help='Ajuste para booster PT-BR (6 cartas vs 11 no EN). Default 6/11.')
    ap.add_argument('--top', type=int, default=20)
    args = ap.parse_args()

    cache = json.loads((REPO / 'data' / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
    pull_en = {}
    f_en = REPO / 'data' / 'liga' / 'pull_rates_en.json'
    if f_en.exists():
        pull_en = json.loads(f_en.read_text(encoding='utf-8'))
    por_sigla_scored = load_precos_por_sigla()
    por_sigla_setjson = load_precos_setjson()
    # funde as duas fontes por sigla (setjson sobrepõe o scored no mesmo (nome, num))
    por_sigla = {}
    for sigla, sub in por_sigla_scored.items():
        por_sigla.setdefault(sigla, {}).update(sub)
    for sigla, sub in por_sigla_setjson.items():
        por_sigla.setdefault(sigla, {}).update(sub)
    print(f'preços: scored={sum(len(v) for v in por_sigla_scored.values())} ({len(por_sigla_scored)} siglas) '
          f'+ setjson={sum(len(v) for v in por_sigla_setjson.values())} → {sum(len(v) for v in por_sigla.values())} | '
          f'fonte={args.fonte} fator={args.fator}')

    pull_ids = set()
    for f in ('pull_rates.json', 'pull_rates_en.json'):
        try:
            pull_ids |= set(json.loads((REPO / 'data' / 'liga' / f).read_text(encoding='utf-8')).keys())
        except Exception:
            pass
    pull_ids.discard('_comentario')

    por_set = {}
    for c in cache:
        s = c['set']['id']
        if s not in pull_ids:
            continue
        por_set.setdefault(s, {'cards': [], 'nome': c['set']['name']})
        por_set[s]['cards'].append(c)

    resultados = []
    for set_id, info in por_set.items():
        rates, _ = pull_rates_para_buckets(args.fonte, args.fator, set_id)
        if not rates:
            continue
        # ano de lançamento (ThePriceDex; fallback releaseDate do cache)
        ano = None
        if set_id in pull_en:
            ano = pull_en[set_id].get('ano')
        if ano is None and info['cards']:
            rd = (info['cards'][0].get('set') or {}).get('releaseDate') or ''
            ano = rd.split('/')[0] if rd else None
        # sigla da Liga com maior overlap → preços SEM colisão entre sets
        sigla = melhor_sigla(set_id, info['cards'], por_sigla)
        precos = por_sigla.get(sigla) if sigla else None
        soma = {b: 0.0 for b in BUCKET_LABEL}
        n = {b: 0 for b in BUCKET_LABEL}
        com_preco = 0
        for c in info['cards']:
            chave = ((c.get('name') or '').strip().lower(), _norm_num(str(c.get('number') or '')))
            preco = precos.get(chave) if precos else None
            if preco is None:
                continue
            com_preco += 1
            bucket = BUCKET_POR_RARITY.get(c.get('rarity'), 'filler')
            soma[bucket] += preco
            n[bucket] += 1

        ev = {}
        total = 0.0
        for b, taxa in rates.items():
            if not n.get(b):
                ev[b] = {'media': 0.0, 'n': 0, 'taxa': round(taxa, 4), 'contrib': 0.0}
                continue
            media = soma[b] / n[b]
            contrib = media * taxa
            ev[b] = {'media': round(media, 2), 'n': n[b], 'taxa': round(taxa, 4),
                     '1em': round(1.0 / taxa, 1) if taxa else None, 'contrib': round(contrib, 2)}
            total += contrib
        if n.get('filler'):
            media_filler = soma['filler'] / n['filler']
            contrib_filler = media_filler * max(0.0, 1.0 - sum(rates.values()))
            ev['filler'] = {'media': round(media_filler, 2), 'n': n['filler'],
                            'prob': round(max(0.0, 1.0 - sum(rates.values())), 4),
                            'contrib': round(contrib_filler, 2)}
            total += contrib_filler

        resultados.append({
            'set': set_id,
            'nome': info['nome'],
            'ano': ano,
            'ev': round(total, 2),
            'cobertura': round(com_preco / len(info['cards']) * 100) if info['cards'] else 0,
            'fonte': args.fonte,
            'fator': args.fator,
            'breakdown': ev,
        })

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

    def chave(r):
        return r['upside'] if r['upside'] is not None else -9999
    resultados.sort(key=chave, reverse=True)

    fator_txt = '6/11' if abs(args.fator - 6 / 11) < 1e-9 else f'{args.fator}'
    print(f'\n=== EV do booster por coleção (R$, {args.fonte} ×{fator_txt} — {len(resultados)} sets) ===')
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
