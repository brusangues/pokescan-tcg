import sys, numpy as np, pandas as pd
sys.path.insert(0, '.')
from catboost import CatBoostRegressor
from sklearn.metrics import mean_absolute_error, r2_score
import pokemon_price_monitor as pm

# USD model
m_usd = CatBoostRegressor()
m_usd.load_model('data/catboost_model.cbm')

cards = pm.fetch_all_cards(max_sets=50)
df = pd.DataFrame([pm.parse_card(c) for c in cards])
df = pm.enrich_pricing(df)
df = df[df['target_price'].notna() & (df['target_price'] > 0)].copy()
df['log_target'] = np.log1p(df['target_price'])

df_sorted = df.sort_values('release_year', na_position='first')
split = int(len(df_sorted) * 0.8)
test_df = df_sorted.iloc[split:]
X_test = pm.prepare_features(test_df)
y_test = test_df['log_target']

pred_log = m_usd.predict(X_test)
pred_real = np.expm1(pred_log)
real_real = np.expm1(y_test.values)

print(f'USD log MAE: {mean_absolute_error(y_test, pred_log):.4f}  R²: {r2_score(y_test, pred_log):.4f}')
print(f'USD real MAE: ${mean_absolute_error(real_real, pred_real):.2f}  R²: {r2_score(real_real, pred_real):.4f}')
