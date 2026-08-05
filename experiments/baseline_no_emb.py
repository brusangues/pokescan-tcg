"""Baseline sem embeddings — para comparar o ganho real das ablações."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.metrics import mean_absolute_error, r2_score

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
import pokemon_price_monitor as pm
import json

CUTOFF = '2024-01-01'

# Carrega base
cards = json.loads((BASE_DIR / 'data' / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
df = pd.DataFrame([pm.parse_card(c) for c in cards])
df['_raw'] = cards
df = pm.enrich_pricing(df)
df = pm.add_supply_features(df)
df['id'] = df['id'].astype(str)

# Zera embeddings (baseline sem imagem)
pm.prepare_features._emb_cache = pd.DataFrame()

# Split temporal por release_year (parse_card gera release_year, não release_date)
train = df[df['release_year'] < 2024]
test = df[df['release_year'] >= 2024]
train = train[train['target_price'].notna() & (train['target_price'] > 0)]
test = test[test['target_price'].notna() & (test['target_price'] > 0)]

X_train = pm.prepare_features(train)
X_test = pm.prepare_features(test)
y_train = np.log1p(train['target_price'].values)
y_test = np.log1p(test['target_price'].values)

cat_idx = [i for i, c in enumerate(X_train.columns) if c in pm.CAT_FEATURES]
model = CatBoostRegressor(iterations=300, depth=8, learning_rate=0.05, loss_function='RMSE', random_seed=42, verbose=0)
model.fit(X_train, y_train, cat_features=cat_idx)

pred = np.expm1(model.predict(X_test))
real = np.expm1(y_test)
mae = mean_absolute_error(real, pred)
r2 = r2_score(real, pred)
print(f'\n📊 BASELINE SEM EMBEDDINGS: MAE=${mae:.2f} | R²={r2:.4f} | n_train={len(train)} n_test={len(test)}')
print(f'   n features: {X_train.shape[1]}')
