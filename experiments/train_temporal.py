#!/usr/bin/env python
"""
train_temporal.py — EXPERIMENTO: modelo com dados temporais de verdade.

Mistura as features ESTÁTICAS atuais (cardmarket, set, embeddings, supply —
via pokemon_price_monitor) com as features TEMPORAIS do histórico TCGCSV
(dataset_temporal.csv) e treina CatBoost com CORTE TEMPORAL:

  train = pontos com data <= CORTE (features ATÉ aquela semana)
  test  = pontos com data >  CORTE (prever o preço da semana SEGUINTE)

Comparações:
  baseline   — só estáticas → target_plus1
  temporal   — estáticas + temporais → target_plus1
Avaliação no teste (sem vazamento) + POR SAFRA (release_year) + importância.

Uso: python experiments/train_temporal.py [--corte 2026-07-21] [--safra-min 2025]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
EX = REPO / 'experiments' / 'tcgcsv'
sys.path.insert(0, str(REPO))
import pokemon_price_monitor as pm

FEATS_TEMPORAIS = ['price_principal', 'price_normal', 'price_holo', 'price_reverse',
                   'ret_1w', 'ret_4w', 'ret_8w', 'mom_4w', 'vol_8w',
                   'spread_rev_norm', 'spread_rev_norm_rel', 'n_semanas']


def load_estaticas():
    """Features estáticas (uma linha por card_id) — mesmo pipeline do produtivo."""
    cache = json.loads((REPO / 'data' / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
    df = pd.DataFrame([pm.parse_card(c) for c in cache])
    df['_raw'] = cache
    df = pm.enrich_pricing(df)
    df = pm.add_supply_features(df)
    df['id'] = df['id'].astype(str)
    X = pm.prepare_features(df)
    X['id'] = df['id'].values
    X['release_year'] = df['release_year'].values if 'release_year' in df.columns else np.nan
    return X.set_index('id')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--corte', default='2026-07-21', help='semana limite do treino (teste = depois dela)')
    ap.add_argument('--safra-min', type=int, default=2025, help='safras novas p/ avaliação focada')
    args = ap.parse_args()

    print('Carregando features estáticas (catálogo)...', flush=True)
    est = load_estaticas()
    print(f'  estáticas: {len(est):,} cartas × {est.shape[1]} features', flush=True)

    print('Carregando dataset temporal...', flush=True)
    tmp = pd.read_csv(EX / 'dataset_temporal.csv', dtype={'card_id': str})
    tmp = tmp.merge(est, left_on='card_id', right_index=True, how='inner')
    print(f'  pontos com estáticas+histórico: {len(tmp):,}', flush=True)

    tmp['log_label'] = np.log(tmp['target_plus1'])
    tmp['log_price'] = np.log(tmp['price_principal'])

    corte = args.corte
    train = tmp[tmp['data'] <= corte]
    test = tmp[tmp['data'] > corte]
    print(f'CORTE {corte}: train {len(train):,} pontos (sem {train["data"].min()}→{train["data"].max()}) | '
          f'test {len(test):,} (sem {test["data"].min()}→{test["data"].max()})', flush=True)

    car = ['rarity_tcg', 'primary_type', 'set_series', 'price_type', 'supertype', 'illustrator', 'trainer_gender']
    car = [c for c in car if c in train.columns and train[c].notna().any()]

    def avaliar(cols, nome):
        Xtr, Xte = train[cols].copy(), test[cols].copy()
        for c in cols:
            if c in car:
                Xtr[c] = Xtr[c].astype(str).fillna('NA')
                Xte[c] = Xte[c].astype(str).fillna('NA')
            else:
                Xtr[c] = pd.to_numeric(Xtr[c], errors='coerce').fillna(Xtr[c].median())
                Xte[c] = pd.to_numeric(Xte[c], errors='coerce').fillna(Xte[c].median())
        from catboost import CatBoostRegressor
        m = CatBoostRegressor(iterations=800, learning_rate=0.06, depth=7,
                              l2_leaf_reg=5, loss_function='RMSE', random_seed=42,
                              verbose=0)
        m.fit(Xtr, train['log_label'].values.astype(float), cat_features=[c for c in car if c in cols])
        pred = m.predict(Xte)
        y = test['log_label'].values.astype(float)
        # métricas no log (previsão de preço)
        r2 = 1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2)
        mae = np.mean(np.abs(y - pred))
        # de volta ao preço
        pred_p = np.exp(pred)
        y_p = np.exp(y)
        mape = np.mean(np.abs(pred_p - y_p) / y_p) * 100
        print(f'\n  [{nome}]')
        print(f'    R²(log)={r2:.4f} | MAE(log)={mae:.4f} | MAPE={mape:.1f}%')
        print(f'    mediana preço real={np.median(y_p):.2f} | predito={np.median(pred_p):.2f}')
        # por safra
        if 'release_year' in test.columns:
            test_f = test.copy()
            test_f['pred'] = pred
            test_f['real'] = y_p
            for ano in sorted(test_f['release_year'].dropna().unique()):
                s = test_f[test_f['release_year'].astype(int) == ano]
                if len(s) < 50:
                    continue
                e = np.mean(np.abs(np.exp(s['pred']) - s['real']) / s['real']) * 100
                marca = ' ◀ safra nova' if ano >= args.safra_min else ''
                print(f'    safra {ano}: n={len(s):>5} | MAPE={e:.1f}%{marca}')
        # importância das temporais
        if nome == 'temporal':
            imp = pd.Series(m.get_feature_importance(), index=cols).sort_values(ascending=False)
            print('    top-10 importância:', ', '.join(f'{k}={v:.0f}' for k, v in imp.head(10).items()))
        return r2, mape

    est_cols = [c for c in est.columns if c not in FEATS_TEMPORAIS and c != 'release_year']
    print('\n=== BASELINE (só estáticas) ===')
    avaliar(est_cols, 'baseline')
    print('\n=== TEMPORAL (estáticas + histórico TCGCSV) ===')
    avaliar(est_cols + FEATS_TEMPORAIS, 'temporal')


if __name__ == '__main__':
    main()