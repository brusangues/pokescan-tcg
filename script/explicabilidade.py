#!/usr/bin/env python
"""
explicabilidade.py — feature importance do CatBoost AGREGADO POR GRUPO (P3.27, 1ª etapa).

Grupos de features (definidos em pokemon_price_monitor.py):
  - Preço mercado (Cardmarket)  — cardmarket_* + price_type
  - Card (atributos)            — hp, subtypes_count, supertype, primary_type,
                                  rarity_tcg, pokedex_number, is_holo/reverse/normal/shiny/legendary
  - Set / era                   — set_series, set_printed_total, release_year, card_age_years
  - Popularidade / grail        — pokemon_popularity, pokemon_grail_score
  - Artista / treinador         — illustrator, trainer_gender
  - Supply (E1)                 — rarity_pool_size, pull_cost_log
  - Liquidez (iCO)              — iCO
  - Embeddings (DINOv2)         — emb_0..emb_31
  - USD (feature do BRL)        — target_price_usd (só modelo BRL)

Uso: python script/explicabilidade.py [--brl] [--tipo PredictionValuesChange|LossFunctionChange]
Saída: ranking de grupos no terminal + frontend/public/data/explicabilidade.json
"""
import argparse
import json
import sys
from pathlib import Path

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
# grupo por feature (default: 'Outros')
FEATURE_GRUPO = {f: g for g, feats in GRUPOS.items() for f in feats}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--brl', action='store_true', help='modelo BRL (tem target_price_usd)')
    ap.add_argument('--tipo', default='PredictionValuesChange',
                    choices=['PredictionValuesChange', 'LossFunctionChange'])
    args = ap.parse_args()

    modelo = pm.load_model_brl() if args.brl else pm.load_model()
    nome = 'BRL' if args.brl else 'USD'
    imp = modelo.get_feature_importance(type=args.tipo)
    nomes = list(modelo.feature_names_)

    if len(imp) != len(nomes):
        # fallback: importance por nome se o modelo não guardou a ordem
        nomes = list(pm.FEATURE_COLS_BRL if args.brl else pm.FEATURE_COLS)
        if len(imp) != len(nomes):
            print('tamanhos divergentes — usando nomes do modelo')
            nomes = list(modelo.feature_names_)

    por_feature = {}
    for n, v in zip(nomes, imp):
        por_feature[n] = float(v)

    # agrega por grupo
    grupos: dict[str, float] = {}
    grupo_n = {}
    for f, v in por_feature.items():
        g = FEATURE_GRUPO.get(f, 'Outros')
        grupos[g] = grupos.get(g, 0.0) + v
        grupo_n[g] = grupo_n.get(g, 0) + 1
    total = sum(grupos.values())

    ranking = sorted(grupos.items(), key=lambda x: -x[1])
    print(f'\n=== Feature importance por GRUPO — modelo {nome} ({args.tipo}) ===')
    print(f'{"Grupo":<28} {"Importance":>10} {"% do total":>10} {"n":>3}')
    print('-' * 56)
    for g, v in ranking:
        print(f'{g:<28} {v:>10.3f} {v / total * 100:>9.1f}% {grupo_n[g]:>3}')

    # top 10 features individuais (referência)
    top = sorted(por_feature.items(), key=lambda x: -x[1])[:10]
    print(f'\n=== Top 10 features individuais ===')
    for f, v in top:
        print(f'  {f:<22} {v:>10.3f}  ({FEATURE_GRUPO.get(f, "Outros")})')

    # salva JSON para o front
    out = {
        'modelo': nome,
        'tipo': args.tipo,
        'total': round(total, 4),
        'grupos': [
            {'grupo': g, 'importance': round(v, 4), 'pct': round(v / total * 100, 2), 'n': grupo_n[g]}
            for g, v in ranking
        ],
        'topFeatures': [
            {'feature': f, 'importance': round(v, 4), 'pct': round(v / total * 100, 2),
             'grupo': FEATURE_GRUPO.get(f, 'Outros')}
            for f, v in top
        ],
    }
    dest = REPO / 'frontend' / 'public' / 'data' / 'explicabilidade.json'
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'\nSalvo em {dest}')


if __name__ == '__main__':
    main()
