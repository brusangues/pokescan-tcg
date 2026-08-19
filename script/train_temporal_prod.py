"""
script/train_temporal_prod.py — TREINO PRODUTIVO do modelo de previsão
da semana seguinte (P1.29).

Combina as features ESTÁTICAS atuais (cardmarket, set, embeddings, supply —
via pokemon_price_monitor) com as features TEMPORAIS do histórico TCGCSV
(dataset_temporal.csv) e treina CatBoost no log(preço da semana seguinte).

  label  = log(target_plus1)   (preço de t+1)
  feats  = estáticas + temporais ATÉ t

Validação: a última semana do dataset é o teste (sem vazamento — features
mais recentes que qualquer feature de treino). Salva:
  data/catboost_model_temporal.cbm
  data/temporal_meta.json  (colunas usadas p/ o predict do build)

Uso: python script/train_temporal_prod.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
import pokemon_price_monitor as pm
from catboost import CatBoostRegressor

DATA = BASE / 'data'
EX = BASE / 'experiments' / 'tcgcsv'

# Nomes SEM prefixo (iguais às colunas do dataset_temporal.csv)
FEATS_TEMPORAIS = ['price_principal', 'price_normal', 'price_holo', 'price_reverse',
                   'ret_1w', 'ret_4w', 'ret_8w', 'mom_4w', 'vol_8w',
                   'spread_rev_norm', 'spread_rev_norm_rel', 'n_semanas']


def load_estaticas():
    cache = json.loads((DATA / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
    df = pd.DataFrame([pm.parse_card(c) for c in cache])
    df['_raw'] = cache
    df = pm._enrich(df)
    df = pm.add_supply_features(df)
    df['id'] = df['id'].astype(str)
    X = pm.prepare_features(df)
    X['id'] = df['id'].values
    X['release_year'] = df['release_year'].values if 'release_year' in df.columns else np.nan
    return X.set_index('id')


def main():
    print('📥 Estáticas do catálogo...', flush=True)
    est = load_estaticas()
    print(f'  estáticas: {len(est):,} cartas × {est.shape[1]} feats', flush=True)

    print('📥 Dataset temporal...', flush=True)
    tmp = pd.read_csv(EX / 'dataset_temporal.csv', dtype={'card_id': str})
    tmp = tmp.merge(est, left_on='card_id', right_index=True, how='inner')
    print(f'  pontos: {len(tmp):,} | semanas {tmp["data"].min()}→{tmp["data"].max()}', flush=True)

    tmp['log_label'] = np.log(tmp['target_plus1'])
    # exige um mínimo de histórico (mesma regra do experimento: posição ≥ 8)
    tmp = tmp[tmp['n_semanas'] >= 8]

    est_cols = [c for c in est.columns if c not in FEATS_TEMPORAIS and c != 'release_year']
    cols = est_cols + [c for c in FEATS_TEMPORAIS if c in tmp.columns]
    car = ['rarity_tcg', 'primary_type', 'set_series', 'price_type', 'supertype',
           'illustrator', 'trainer_gender']
    car = [c for c in car if c in cols]
    cat_idx = [i for i, c in enumerate(cols) if c in car]

    # validação: última semana como teste (features do teste mais recentes que o treino)
    ultima = tmp['data'].max()
    tr = tmp[tmp['data'] < ultima]
    te = tmp[tmp['data'] == ultima]

    def prep(dd):
        X = dd[cols].copy()
        for c in cols:
            if c in car:
                X[c] = X[c].astype(str).fillna('NA')
            else:
                X[c] = pd.to_numeric(X[c], errors='coerce')
        nan_cols = X.columns[X.isna().all()]
        X = X.drop(columns=nan_cols)
        return X

    Xtr, Xte = prep(tr), prep(te)
    feat_ok = [c for c in cols if c in Xtr.columns]
    cat_idx = [feat_ok.index(c) for c in feat_ok if c in car]

    m = CatBoostRegressor(iterations=1000, learning_rate=0.06, depth=7,
                          l2_leaf_reg=5, loss_function='RMSE',
                          random_seed=42, verbose=False,
                          early_stopping_rounds=60)
    m.fit(Xtr, tr['log_label'].values.astype(float),
          eval_set=(Xte, te['log_label'].values.astype(float)),
          cat_features=cat_idx)

    pred = m.predict(Xte)
    y = te['log_label'].values.astype(float)
    r2 = 1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2)
    mape = np.mean(np.abs(np.exp(pred) - np.exp(y)) / np.exp(y)) * 100
    print(f'\nValidação (última semana {ultima}, n={len(te):,}): '
          f'R²(log)={r2:.4f} | MAPE={mape:.1f}% | melhor iteração={m.get_best_iteration()}', flush=True)

    if 'release_year' in te.columns:
        tf = te.copy()
        tf['pred'] = np.exp(pred)
        tf['real'] = np.exp(y)
        for ano in sorted(tf['release_year'].dropna().unique())[-3:]:
            s = tf[tf['release_year'].astype(int) == ano]
            if len(s) < 50:
                continue
            rel = np.median(np.abs(s['pred'] - s['real']) / s['real']) * 100
            print(f'    safra {int(ano)}: n={len(s):,} | erro mediano={rel:.1f}%')

    imp = pd.Series(m.get_feature_importance(), index=feat_ok).sort_values(ascending=False)
    print('Top-12 importância:', ', '.join(f'{k}={v:.0f}' for k, v in imp.head(12).items()), flush=True)

    m.save_model(str(DATA / 'catboost_model_temporal.cbm'))
    meta = {
        'feature_names': feat_ok,
        'cat_features': [c for c in feat_ok if c in car],
        'ultima_semana': ultima,
        'r2': r2, 'mape': mape, 'n_pontos': int(len(tmp)),
        'melhor_iteracao': int(m.get_best_iteration()),
    }
    (DATA / 'temporal_meta.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    print(f'\n✅ Salvo: catboost_model_temporal.cbm + temporal_meta.json '
          f'({len(feat_ok)} features)', flush=True)


if __name__ == '__main__':
    main()