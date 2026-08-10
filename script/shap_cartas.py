#!/usr/bin/env python
"""
shap_cartas.py — SHAP values por carta (P3.27 etapa 2).

Calcula a contribuição de cada feature para a predição de CADA carta do
predicoes_latest.csv (mesmas features do export_features.py), usando o
ShapValues nativo do CatBoost (rápido — sem depender do pacote shap).

Salva data/features/shap_cartas.json:
  { card_id: { 'usd': {bias, top:[{f,g,s,r},...]}, 'brl': {...} } }
  - s = shap value (escala log1p — sinal = direção)
  - r = impacto no preço em $/R$ (expm1(bias+s) − expm1(bias)) — intuitivo
  - top = top-4 features por |s|, com grupo (mesmos grupos da explicabilidade)

Uso: python script/shap_cartas.py [--top 5]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import pokemon_price_monitor as pm

EMB = [f'emb_{i}' for i in range(pm.N_EMB)]
GRUPOS: dict[str, list[str]] = {
    'Preço mercado (Cardmarket)': pm.CM_FEATURES + ['price_type'],
    'Card (atributos)': ['hp', 'subtypes_count', 'supertype', 'primary_type', 'rarity_tcg',
                         'pokedex_number'] + pm.ART_FEATURES,
    'Set / era': ['set_series', 'set_printed_total', 'release_year', 'card_age_years'],
    'Popularidade / grail': ['pokemon_popularity', 'pokemon_grail_score'],
    'Artista / treinador': ['illustrator', 'trainer_gender'],
    'Supply (E1)': pm.SUPPLY_FEATURES,
    'Liquidez (iCO)': ['iCO'],
    'Embeddings (DINOv2)': EMB,
    'USD (feature do BRL)': ['target_price_usd'],
}
FEATURE_GRUPO = {f: g for g, feats in GRUPOS.items() for f in feats}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=int, default=4, help='top-N features por carta/modelo')
    args = ap.parse_args()

    cards = json.loads((REPO / 'data' / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
    df = pd.DataFrame([pm.parse_card(c) for c in cards])
    df['_raw'] = cards  # pricing embutido do cache (evita buscar na API)
    df = pm.enrich_pricing(df)
    df = pm.add_supply_features(df)
    df['id'] = df['id'].astype(str)
    try:
        _lookup_brl, _lookup_ico, _set_map = pm.build_liga_lookup()
        df = pm.enrich_brl(df, _lookup_brl, _lookup_ico, _set_map)
    except Exception as e:
        print(f'  ⚠️ BRL merge falhou: {e}')

    X = pm.prepare_features(df)
    for c in pm.CAT_FEATURES:
        if c in X.columns:
            X[c] = X[c].fillna('Unknown').astype(str)
    df['target_price_usd'] = df['target_price'].fillna(df['target_price'].median())
    X_brl = pm.prepare_features(df, extra_features=['target_price_usd'])
    for c in pm.CAT_FEATURES:
        if c in X_brl.columns:
            X_brl[c] = X_brl[c].fillna('Unknown').astype(str)

    model = pm.load_model()
    model_brl = pm.load_model_brl()
    ids = df['id'].values
    nomes_usd = list(model.feature_names_)
    nomes_brl = list(model_brl.feature_names_)

    from catboost import Pool
    cat_idx_usd = [i for i, c in enumerate(X.columns) if c in pm.CAT_FEATURES]
    cat_idx_brl = [i for i, c in enumerate(X_brl.columns) if c in pm.CAT_FEATURES]
    pool_usd = Pool(X, cat_features=cat_idx_usd)
    pool_brl = Pool(X_brl, cat_features=cat_idx_brl)

    print('🔬 Calculando SHAP...')
    shap_usd = model.get_feature_importance(data=pool_usd, type='ShapValues')
    shap_brl = model_brl.get_feature_importance(data=pool_brl, type='ShapValues')
    print(f'  USD: {shap_usd.shape} | BRL: {shap_brl.shape}')

    out = {}
    for i, cid in enumerate(ids):
        entry = {}
        for nome, arr, nomes in (('usd', shap_usd[i], nomes_usd), ('brl', shap_brl[i], nomes_brl)):
            bias = float(arr[-1])
            top = []
            for j, s in enumerate(arr[:-1]):
                r = float(np.expm1(bias + s) - np.expm1(bias))
                top.append({'f': nomes[j], 'g': FEATURE_GRUPO.get(nomes[j], 'Outros'),
                            's': round(float(s), 4), 'r': round(r, 2)})
            top.sort(key=lambda x: -abs(x['s']))
            entry[nome] = {'bias': round(bias, 4), 'top': top[:args.top]}
        out[str(cid)] = entry

    dest = REPO / 'data' / 'features' / 'shap_cartas.json'
    dest.write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    print(f'💾 Salvo: {dest} ({len(out)} cartas, top-{args.top} por modelo)')


if __name__ == '__main__':
    main()
