#!/usr/bin/env python
"""
ab_tcgcsv.py — A/B para a troca TCGPlayer→TCGCSV no modelo de produção.

Três pipelines treinados com o MESMO split temporal do produtivo
(80% safras antigas / 20% mais novas — por release_year):

  A) atual      : enrich_pricing (tcgplayer do cache pokemontcg.io)
  B) tcgcsv     : target/escolha de variante vindos do TCGCSV (última semana)
  C) tcgcsv+tmp : B + features temporais (ret_1w/4w/8w, momentum, spread...)

Avaliação CRUZADA no holdout (as safras novas):
  - cada modelo medido no target TCGCSV (preço real atual) e no target cache
  - o que decide a troca: o modelo que melhor prevê o preço REAL (TCGCSV)

Uso: python experiments/ab_tcgcsv.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
EX = REPO / 'experiments' / 'tcgcsv'
sys.path.insert(0, str(REPO))
import pokemon_price_monitor as pm

ULTIMA_SEMANA = '2026-08-11'
FEATS_TEMPORAIS = ['t_price_principal', 't_price_normal', 't_price_holo', 't_price_reverse',
                   't_ret_1w', 't_ret_4w', 't_ret_8w', 't_mom_4w', 't_vol_8w',
                   't_spread_rev_norm', 't_spread_rev_norm_rel', 't_n_semanas']


def load_tcgcsv_tables():
    """pid→card, preço principal por card (última semana) e temporais por card."""
    pid2card = json.loads((EX / 'pid_to_card.json').read_text(encoding='utf-8'))
    hist = pd.read_csv(EX / 'historico_en.csv', dtype={'productId': str})
    hist['card'] = hist['productId'].map(pid2card)
    hist = hist.dropna(subset=['card'])[['data', 'productId', 'subtype', 'market_price', 'card']]
    h = hist[hist['data'] == ULTIMA_SEMANA]

    # preço principal + variante por card (prioridade holofoil → normal → reverse)
    preco, variante = {}, {}
    for pid, g in h.groupby('productId'):
        vals = {r['subtype']: r['market_price'] for _, r in g.iterrows() if r['market_price'] > 0}
        cid = pid2card.get(pid)
        if not cid:
            continue
        for st in ('Holofoil', 'Normal', 'Reverse Holofoil'):
            if st in vals:
                preco[cid] = vals[st]
                variante[cid] = st.lower()
                break
    # temporais: bloco da última semana (reuso da lógica do validar_brl)
    from experiments.temporal_lib import bloco_semana
    temporais = bloco_semana(hist, ULTIMA_SEMANA)
    return preco, variante, temporais


def apply_tcgcsv(df, preco, variante, temporais):
    """Sobrepõe target_price/price_type do cache pelos do TCGCSV + anexa temporais."""
    df = df.copy()
    ids = df['id'].astype(str)
    has = ids.isin(preco)
    df['target_price_tcgcsv'] = np.where(has, ids.map(preco), df['target_price'])
    df['price_type_tcgcsv'] = np.where(has, ids.map(variante), df['price_type'])
    tmp = temporais.reindex(ids.values)
    for c in FEATS_TEMPORAIS:
        df[c] = tmp[c].values
    df['tem_tcgcsv'] = has.astype(int)
    return df


def treinar(df, label_col, extra_cols=None, nome=''):
    """Split temporal por release_year (como o produtivo) + CatBoost MAE."""
    d = df[df[label_col].notna() & (df[label_col] > 0)].copy()
    d['log_target'] = np.log1p(d[label_col])
    d = d.sort_values('release_year', na_position='first')
    split = int(len(d) * 0.8)
    tr, te = d.iloc[:split], d.iloc[split:]

    cols = [c for c in pm.FEATURE_COLS if c in tr.columns] + (extra_cols or [])
    cat_idx = [i for i, c in enumerate(cols) if c in pm.CAT_FEATURES]

    def _prep(dd):
        X = pm.prepare_features(dd)
        for c in cols:
            if c not in X.columns:
                # extras (t_*) não vêm do prepare_features — copia do df direto
                if c in dd.columns:
                    X[c] = pd.to_numeric(dd[c], errors='coerce')
                else:
                    continue
            if c in pm.CAT_FEATURES:
                X[c] = X[c].astype(str).fillna('NA')
            else:
                X[c] = pd.to_numeric(X[c], errors='coerce')
        return X[cols]

    Xtr, Xte = _prep(tr), _prep(te)
    from catboost import CatBoostRegressor
    m = CatBoostRegressor(iterations=500, learning_rate=0.05, depth=6,
                          l2_leaf_reg=3, loss_function='MAE', eval_metric='MAE',
                          cat_features=cat_idx, verbose=0, random_seed=42,
                          early_stopping_rounds=30)
    m.fit(Xtr, tr['log_target'].values.astype(float), eval_set=(Xte, te['log_target'].values.astype(float)))
    return m, tr, te, cols


def reportar(m, te, cols, label_col, nome):
    te = te[te[label_col].notna() & (te[label_col] > 0)].copy()
    Xte = pm.prepare_features(te)
    for c in cols:
        if c not in Xte.columns:
            if c in te.columns:
                Xte[c] = pd.to_numeric(te[c], errors='coerce')
            else:
                continue
        if c in pm.CAT_FEATURES:
            Xte[c] = Xte[c].astype(str).fillna('NA')
        else:
            Xte[c] = pd.to_numeric(Xte[c], errors='coerce')
    pred = np.expm1(m.predict(Xte[[c for c in cols if c in Xte.columns]]))
    y = te[label_col].values
    r2 = 1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2)
    mae = np.mean(np.abs(pred - y))
    mape = np.median(np.abs(pred - y) / y) * 100
    print(f'    [{nome}] no target {label_col}: R²={r2:.4f} | MAE=${mae:.2f} | erro mediano={mape:.1f}%')
    # por safra (as 3 mais novas)
    for ano in sorted(te['release_year'].dropna().unique())[-3:]:
        s = te[te['release_year'].astype(int) == ano]
        if len(s) < 50:
            continue
        row_idx = Xte.index.intersection(s.index)
        if len(row_idx) == 0:
            continue
        rel = np.abs(np.expm1(m.predict(Xte.loc[row_idx, [c for c in cols if c in Xte.columns]])) - s.loc[row_idx, label_col].values) / s.loc[row_idx, label_col].values
        print(f'      safra {int(ano)}: n={len(row_idx)} | erro mediano={np.median(rel)*100:.1f}%')
    return mae


def main():
    cache = json.loads((REPO / 'data' / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
    df = pd.DataFrame([pm.parse_card(c) for c in cache])
    df['_raw'] = cache
    df['id'] = df['id'].astype(str)

    print('Pipeline A (cache pokemontcg.io)...', flush=True)
    dfA = pm.enrich_pricing(df)

    print('Pipeline B/C (TCGCSV)...', flush=True)
    preco, variante, temporais = load_tcgcsv_tables()
    dfB = apply_tcgcsv(dfA, preco, variante, temporais)  # target/price_type sobrepostos

    n_ok = dfB['tem_tcgcsv'].sum()
    print(f'  cartas com preço TCGCSV: {n_ok:,}/{len(dfB):,} '
          f'({n_ok / len(dfB) * 100:.1f}%) — restante usa cache (fallback)', flush=True)

    print('\n=== TREINO (split temporal por safra: 80% antigas / 20% novas) ===', flush=True)
    mA, trA, teA, colsA = treinar(dfA, 'target_price', nome='A')
    print('A treinado.', flush=True)
    mB, trB, teB, colsB = treinar(dfB, 'target_price_tcgcsv', nome='B')
    print('B treinado.', flush=True)
    mC, trC, teC, colsC = treinar(dfB, 'target_price_tcgcsv', FEATS_TEMPORAIS, nome='C')
    print('C treinado.', flush=True)

    print('\n=== AVALIAÇÃO CRUZADA (holdout = 20% safras mais novas, mesmo conjunto) ===')
    print('No target CACHE (o que o site mostra hoje):')
    reportar(mA, teB, colsA, 'target_price', 'A(cache)')
    reportar(mB, teB, colsB, 'target_price', 'B(tcgcsv)')
    reportar(mC, teB, colsC, 'target_price', 'C(tcgcsv+tmp)')
    print('\nNo target TCGCSV (preço real da fonte nova):')
    reportar(mA, teB, colsA, 'target_price_tcgcsv', 'A(cache)')
    reportar(mB, teB, colsB, 'target_price_tcgcsv', 'B(tcgcsv)')
    reportar(mC, teB, colsC, 'target_price_tcgcsv', 'C(tcgcsv+tmp)')

    if colsC != colsB:
        imp = pd.Series(mC.get_feature_importance(), index=colsC).sort_values(ascending=False)
        print('\nImportância (C):', ', '.join(f'{k}={v:.0f}' for k, v in imp.head(10).items()))


if __name__ == '__main__':
    main()