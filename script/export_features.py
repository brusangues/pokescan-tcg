"""
script/export_features.py
=========================
Exporta as predições do modelo COM as features usadas + labels reais,
para a página de debug /features do frontend.

Gera data/features/predicoes_latest.csv:
  - id, name, set_id, set_name (identificação)
  - todas as features do X (numéricas + categóricas)
  - label real (target_price USD e BRL)
  - predições (pred_usd, pred_brl)

Uso:
  python script/export_features.py              # base toda (20k, ~40s)
  python script/export_features.py --top 200    # só as 200 mais recentes
"""

import sys, json, argparse
from pathlib import Path
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
import pokemon_price_monitor as pm

OUT_DIR = BASE / 'data' / 'features'
OUT_PATH = OUT_DIR / 'predicoes_latest.csv'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--top', type=int, default=None,
                        help='Limita a N cartas (mais recentes). Default: base toda')
    parser.add_argument('--filtro-preco', action='store_true',
                        help='Só cartas com preço real (label) — default: todas')
    args = parser.parse_args()

    print('📦 Carregando cache local...')
    cards = json.loads((BASE / 'data' / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
    df = pd.DataFrame([pm.parse_card(c) for c in cards])
    df['_raw'] = cards
    df = pm.enrich_pricing(df)
    df = pm.add_supply_features(df)
    df['id'] = df['id'].astype(str)

    if args.top:
        # 'mais recentes' ≈ maior release_year + maior id
        df = df.sort_values(['release_year', 'id'], ascending=[False, False])
        # Amostra estratificada por set: pega floor(top/sets) de cada set,
        # evitando que 1 set recente domine a amostra (ex. me5 sem preço)
        if 'set_id' in df.columns:
            n_sets = df['set_id'].nunique()
            por_set = max(1, args.top // n_sets)
            df = df.groupby('set_id', group_keys=False).head(por_set).head(args.top)
        else:
            df = df.head(args.top)
        print(f'  Limitado a {len(df)} cartas')

    print(f'  Base: {len(df)} cartas | com preço USD: {df["target_price"].notna().sum()}')

    # Features USD (colunas do X)
    X = pm.prepare_features(df)
    for c in pm.CAT_FEATURES:
        if c in X.columns:
            X[c] = X[c].fillna('Unknown').astype(str)

    # BRL: adiciona target_price_usd como feature extra (como o treino)
    df['target_price_usd'] = df['target_price'].fillna(df['target_price'].median())
    X_brl = pm.prepare_features(df, extra_features=['target_price_usd'])
    for c in pm.CAT_FEATURES:
        if c in X_brl.columns:
            X_brl[c] = X_brl[c].fillna('Unknown').astype(str)

    print('🤖 Carregando modelos...')
    model = pm.load_model()
    model_brl = pm.load_model_brl()

    print('🔮 Predizendo...')
    pred_usd = np.expm1(model.predict(X))
    try:
        pred_brl = np.expm1(model_brl.predict(X_brl))
    except Exception as e:
        print(f'  ⚠️ BRL predict falhou: {e}')
        pred_brl = np.full(len(X_brl), np.nan)

    out = pd.DataFrame({
        'id': df['id'].values,
        'name': df['name'].values,
        'set_id': df['set_id'].values,
        'set_name': df['set_name'].values,
        'release_year': df['release_year'].values,
        'label_usd': df['target_price'].values,
        'label_brl': df['target_price_brl'].values if 'target_price_brl' in df.columns else np.nan,
        'pred_usd': pred_usd,
        'pred_brl': pred_brl,
    })
    # Features do X (todas as colunas numéricas/categóricas)
    for col in X.columns:
        out[col] = X[col].values
    for col in X_brl.columns:
        if col not in out.columns:
            out[col] = X_brl[col].values

    # Filtro opcional: só com label
    if args.filtro_preco:
        out = out[out['label_usd'].notna() & (out['label_usd'] > 0)].copy()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_PATH, index=False)
    print(f'💾 Salvo: {OUT_PATH} ({len(out)} linhas, {out.shape[1]} colunas)')


if __name__ == '__main__':
    main()
