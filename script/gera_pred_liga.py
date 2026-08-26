"""gera_pred_liga.py — Predição BRL Liga-first para TODA carta do site.

Gera frontend/public/data/pred_liga.json:
  { "{idE}-{num}": { pred, real, sigla, iCO, ... } }
  + alias pela carta EN ({set_ptcg}-{num}) quando existe join, e
  + cartas EN-only (promos/sets que a Liga não cataloga) com predição BRL
    do modelo usando features derivadas do cache EN.

- real: p1b da Liga (quando >0) — é o preço mercado BR observado
- pred: modelo brl_liga (script/brl_liga.py)
Consumo: cardLookup usa como fallback quando não há registro escorado do
próprio set — página /card mostra 'Previsão (Liga-first)' em vez de nada.

Rodar após cada snapshot novo (ou junto do build_static_data).
"""
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / 'script'))
import numpy as np
from script import brl_liga

OUT = BASE / 'frontend' / 'public' / 'data' / 'pred_liga.json'
CARDS = BASE / 'frontend' / 'public' / 'data' / 'cards.json'


def main():
    model, meta = brl_liga.carregar()
    if model is None:
        raise SystemExit('Modelo brl_liga não encontrado — rode script/brl_liga.py antes.')
    brl_liga._carregar_mediana()
    cat = json.loads(brl_liga.CAT_LIGA.read_text(encoding='utf-8'))
    ien = brl_liga.indice_en()
    med_usd = brl_liga.MODEL_MEDIANA.get('usd')

    rows, keys = [], []
    for c in cat:
        eid = c.get('en_id')
        me = ien.get(eid, {}) if eid else {}
        rows.append({
            'iR': float(c.get('iR') or 0), 'iCO': float(c.get('iCO') or 0),
            'usd': float(me['usd']) if me.get('usd') is not None else (med_usd or np.nan),
            'sigla': str(c.get('sigla') or 'desconhecido'),
            'rar': str(me.get('rar', 'desconhecido')),
            'types': str(me.get('types', 'desconhecido')),
        })
        keys.append(f"{c['idE']}-{c['num']}")
    import pandas as pd
    X = pd.DataFrame(rows)
    X['usd'] = X['usd'].fillna(med_usd) if med_usd is not None else X['usd'].fillna(0)
    for cc in brl_liga.CATS:
        X[cc] = X[cc].astype(str)
    preds = np.expm1(model.predict(X[brl_liga.FEATS]))

    val = {}
    for i, (k, pr) in enumerate(zip(keys, preds)):
        cl = cat[i]
        p1b = float(cl.get('p1b') or 0)
        val[k] = {
            'pred': round(float(pr), 2),
            'real': round(p1b, 2) if p1b > 0 else None,
            'sigla': cl.get('sigla'),
            'iCO': int(cl.get('iCO') or 0),
            'eid': cl.get('en_id'),
        }

    # Chave canônica {idE}-{num} + alias pela carta EN ({set_ptcg}-{num}) quando
    # existe join — o front resolve direto por card.s+num sem depender do setMap.
    out = dict(val)
    cobertos = set()
    for k, v in val.items():
        eid = v.pop('eid', None)
        if eid:
            out[eid] = v
            cobertos.add(eid)

    # ── Cartas EN-only (promos/sets que a Liga não cataloga): prediz BRL com
    # features derivadas do cache EN (usd/rar/types) + iR/iCO=0, sigla 'ONLY'.
    # P1.34/P2.41: possibilita 'Preço justo (modelo)' e link de busca na Liga
    # mesmo sem presença direta. Ex.: smp-SM108 "Ash's Pikachu".
    try:
        cards = json.loads(CARDS.read_text(encoding='utf-8'))
        extras_rows, extras_keys, extras_meta = [], [], []
        for c in cards:
            cid = c.get('id') or ''
            if cid.startswith('mep') or cid in cobertos or cid in out:
                continue
            me = ien.get(cid, {}) if cid else {}
            usd = float(c['p']) if c.get('p') else (float(me['usd']) if me.get('usd') is not None else (med_usd or np.nan))
            extras_rows.append({
                'iR': 0.0, 'iCO': 0.0,
                'usd': usd,
                'sigla': 'smp' if c.get('s') == 'smp' else 'only',
                'rar': str(me.get('rar', c.get('r') or 'desconhecido')),
                'types': str(me.get('types', 'desconhecido')),
            })
            extras_keys.append(cid)
            extras_meta.append({'sigla': None, 'iCO': 0, 'real': None, 'nome': c.get('n') or ''})
        if extras_rows:
            Xe = pd.DataFrame(extras_rows)
            Xe['usd'] = Xe['usd'].fillna(med_usd) if med_usd is not None else Xe['usd'].fillna(0)
            for cc in brl_liga.CATS:
                Xe[cc] = Xe[cc].astype(str)
            preds_e = np.expm1(model.predict(Xe[brl_liga.FEATS]))
            for k, pr, em in zip(extras_keys, preds_e, extras_meta):
                out[k] = {
                    'pred': round(float(pr), 2),
                    'real': None,
                    'sigla': em['sigla'],
                    'iCO': em['iCO'],
                    'nome': em['nome'],
                }
        print(f'  + {len(extras_keys)} cartas EN-only com predição BRL')
    except Exception as e:
        print('⚠ gera_pred_liga EN-only skip:', e)

    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    n_real = sum(1 for v in val.values() if v.get('real'))
    print(f'✅ {OUT.name}: {len(val)} cartas catálogo (+{len(out)-len(val)} alias EN/EN-only) | {n_real} com preço real da Liga')


if __name__ == '__main__':
    main()