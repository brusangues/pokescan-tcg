"""
script/retrain_models.py
========================
Re-treina os modelos USD e BRL com o cache local (data/ptcg_cards_cache.json)
e embeddings atuais (data/pokemon_embeddings_base32.csv — dinov2-base cls+mean PCA32).

Seguro para crons: NÃO faz fetch de API (usa cache), NÃO altera inputs das
rotinas — só sobrescreve data/catboost_model*.cbm (que o score_apos_crawl
carrega a cada execução).

Uso:
  python script/retrain_models.py              # USD + BRL
  python script/retrain_models.py --usd-only   # só USD
"""

import sys, json, argparse
from pathlib import Path
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
import pokemon_price_monitor as pm

DATA_DIR = BASE_DIR / 'data'


def load_base_from_cache():
    """Carrega base completa do cache local (sem API)."""
    print('📦 Carregando base do cache local...')
    cards = json.loads((DATA_DIR / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
    df = pd.DataFrame([pm.parse_card(c) for c in cards])
    df['_raw'] = cards
    df = pm._enrich(df)
    df = pm.add_supply_features(df)
    df['id'] = df['id'].astype(str)
    print(f'  Base: {len(df)} cartas, {df["target_price"].notna().sum()} com preço USD')
    return df, cards


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--usd-only', action='store_true')
    parser.add_argument('--brl-only', action='store_true')
    args = parser.parse_args()

    df, cards = load_base_from_cache()

    if not args.brl_only:
        print('\n' + '='*60)
        print('🎯 TREINANDO MODELO USD')
        print('='*60)
        pm.train_model(cards=cards)

    if not args.usd_only:
        print('\n' + '='*60)
        print('🎯 TREINANDO MODELO BRL')
        print('='*60)
        pm.train_model_brl(cards=cards)

    print('\n✅ Retreino completo. Modelos atualizados:')
    print(f'  {pm.MODEL_PATH}')
    print(f'  {pm.BRL_MODEL_PATH}')


if __name__ == '__main__':
    main()
