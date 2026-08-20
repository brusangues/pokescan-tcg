"""
script/prever_temporal.py — PREVISÃO temporal em produção (P1.29).

Carrega o catboost_model_temporal.cbm (treinado por train_temporal_prod.py)
e, para cada carta do catálogo com histórico TCGCSV, prevê o preço USD da
próxima semana usando:

  estáticas (cardmarket, set, embeddings, supply — via pokemon_price_monitor)
  + temporais da ÚLTIMA semana do histórico (ret_1w/4w/8w, momentum, spread)

prever_todas() -> dict { card_id: {"prev": float, "tendencia_pct": float} }
Se o modelo/meta não existir, retorna {} (build segue sem a previsão).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / 'data'
sys.path.insert(0, str(BASE))
import pokemon_price_monitor as pm
from script.tcgcsv_lib import ler_historico, bloco_semana

MODELO = DATA / 'catboost_model_temporal.cbm'
META = DATA / 'temporal_meta.json'


def _rename_temporal(col: str) -> str:
    return col[2:] if col.startswith('t_') else col


def prever_todas() -> dict:
    if not (MODELO.exists() and META.exists()):
        return {}
    try:
        from catboost import CatBoostRegressor
        meta = json.loads(META.read_text(encoding='utf-8'))
        m = CatBoostRegressor()
        m.load_model(str(MODELO))
        feat = meta['feature_names']
        car = meta.get('cat_features', [])

        # estáticas
        cache = json.loads((DATA / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
        df = pd.DataFrame([pm.parse_card(c) for c in cache])
        df['_raw'] = cache
        df = pm._enrich(df)
        df = pm.add_supply_features(df)
        df['id'] = df['id'].astype(str)
        X = pm.prepare_features(df)
        X['id'] = df['id'].values
        X = X.set_index('id')
        preco_atual = df.set_index('id')['target_price']

        # temporais da última semana (rename t_* → sem prefixo, padrão do treino)
        hist = ler_historico()
        semana = max(hist['data'])
        tmp = bloco_semana(hist, semana).rename(columns=_rename_temporal)
        X = X.join(tmp, how='left')

        # só cartas com preço principal real da última semana (senão predição sem base)
        ok = X['price_principal'].notna()
        sub = X.loc[ok, feat].copy()
        for c in feat:
            if c in car:
                sub[c] = sub[c].astype(str).fillna('NA')
            else:
                sub[c] = pd.to_numeric(sub[c], errors='coerce')

        pred_log = m.predict(sub)
        prev = np.exp(pred_log)
        atual = X.loc[ok, 'price_principal'].values

        out = {}
        for cid, p, a in zip(sub.index, prev, atual):
            if a and a > 0 and p > 0:
                out[cid] = {'prev': round(float(p), 2),
                            'tendencia_pct': round((float(p) / float(a) - 1) * 100, 1),
                            'atual': round(float(a), 2)}
        return out
    except Exception as e:
        print(f'⚠️  Previsão temporal indisponível: {e}', flush=True)
        return {}


def ranking_tendencias(top: int = 25, preco_min: float = 2.0, preco_max: float = 150.0,
                       tend_min: float = 3.0) -> dict:
    """P1.30 — ranking de tendência: cartas com maior subida/queda prevista
    p/ a próxima semana (preço USD — coerente com a previsão; nunca mistura
    moedas). Faixa de preço padrão [$2, $150]: exclui preços-lixo (<$2) e os
    extremos de alto valor (Gold Stars $1000+, onde a tendência é ruído por
    poucas transações e o item é pouco acionável). Junta a previsão com o
    catálogo (nome, set, imagem, raridade) — chave canônica = card_id do
    catálogo (id do pokemontcg.io).

    Retorna {'subidas': [...], 'quedas': [...], 'total': n}.
   """
    prev = prever_todas()
    if not prev:
        return {'subidas': [], 'quedas': [], 'total': 0}
    cache = json.loads((DATA / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
    por_id = {c['id']: c for c in cache}
    linhas = []
    for cid, v in prev.items():
        c = por_id.get(cid)
        if not c:
            continue
        atual = v.get('atual') or 0
        if atual < preco_min or atual > preco_max:
            continue
        tend = v['tendencia_pct']
        if abs(tend) < tend_min:
            continue
        s = c.get('set') or {}
        linhas.append({
            'card_id': cid,
            'nome': c.get('name'),
            'set': s.get('id', ''),
            'setNome': s.get('name', ''),
            'num': c.get('number'),
            'rarity': c.get('rarity'),
            'img': (c.get('images') or {}).get('small', ''),
            'atual': atual,
            'prev': v['prev'],
            'tendencia_pct': tend,
        })
    sub = sorted([l for l in linhas if l['tendencia_pct'] > 0],
                 key=lambda x: -x['tendencia_pct'])[:top]
    queda = sorted([l for l in linhas if l['tendencia_pct'] < 0],
                   key=lambda x: x['tendencia_pct'])[:top]
    return {'subidas': sub, 'quedas': queda, 'total': len(linhas)}


if __name__ == '__main__':
    r = prever_todas()
    print(f'cartas com previsão: {len(r):,}')
    for k in list(r)[:6]:
        print(f'  {k}: {r[k]}')