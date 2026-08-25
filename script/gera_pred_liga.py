"""gera_pred_liga.py — Predição BRL Liga-first para TODA carta com preço na Liga.

Gera frontend/public/data/pred_liga.json:
  { "{idE}-{num}": { pred, real, iR, sigla } }
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
    for k, v in val.items():
        eid = v.pop('eid', None)
        if eid:
            out[eid] = v
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    n_real = sum(1 for v in val.values() if v['real'])
    print(f'✅ {OUT.name}: {len(val)} cartas (+{len(out)-len(val)} alias EN) | {n_real} com preço real da Liga')


if __name__ == '__main__':
    main()
