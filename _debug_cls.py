import sys, traceback
sys.path.insert(0, '.')
import pandas as pd, numpy as np
from catboost import CatBoostClassifier, CatBoostRegressor
from sklearn.metrics import accuracy_score, f1_score
import pokemon_price_monitor as pm

cards = pm.fetch_all_cards(max_sets=50)
df = pd.DataFrame([pm.parse_card(c) for c in cards])
df = pm.enrich_pricing(df)
df = df[df['target_price'].notna() & (df['target_price'] > 0)].copy()
df['log_target'] = np.log1p(df['target_price'])

df_sorted = df.sort_values('release_year', na_position='first')
split = int(len(df_sorted) * 0.8)
train_df, test_df = df_sorted.iloc[:split], df_sorted.iloc[split:]

X_train = pm.prepare_features(train_df)
y_train_p = train_df['log_target']
X_test = pm.prepare_features(test_df)
y_test_p = test_df['log_target']

cat_idx = [i for i, c in enumerate(X_train.columns) if c in pm.CAT_FEATURES]

print('Features:', X_train.shape, 'cat_idx:', cat_idx)

# Bins
bins = y_train_p.quantile([0, 0.2, 0.4, 0.6, 0.8, 1.0]).values
bins[0] = 0
bins[-1] = np.inf
labels = list(range(5))

y_train_cls = pd.cut(y_train_p, bins=bins, labels=labels, include_lowest=True)
y_test_cls = pd.cut(y_test_p, bins=bins, labels=labels, include_lowest=True)

print(f'Treino bins: {y_train_cls.value_counts().sort_index().tolist()}')
print(f'Teste bins: {y_test_cls.value_counts().sort_index().tolist()}')
print(f'Bins: {bins}')

try:
    model_cls = CatBoostClassifier(
        iterations=100, learning_rate=0.05, depth=6,
        loss_function='MultiClass', eval_metric='Accuracy',
        cat_features=cat_idx, verbose=50, random_seed=42,
        early_stopping_rounds=30,
    )
    model_cls.fit(X_train, y_train_cls, eval_set=(X_test, y_test_cls), verbose=50)
    
    pred = model_cls.predict(X_test).flatten()
    acc = accuracy_score(y_test_cls, pred)
    f1 = f1_score(y_test_cls, pred, average='weighted')
    print(f'\n✅ Acc: {acc:.2%} | F1: {f1:.3f}')
except Exception as e:
    traceback.print_exc()
    print(f'ERRO: {e}')
