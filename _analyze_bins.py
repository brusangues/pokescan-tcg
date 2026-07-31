import pandas as pd, numpy as np
import pokemon_price_monitor as pm

cards = pm.fetch_all_cards(max_sets=50)
df = pd.DataFrame([pm.parse_card(c) for c in cards])
df = pm.enrich_pricing(df)
df = df[df['target_price'].notna() & (df['target_price'] > 0)].copy()

lk_brl, lk_ico, sm = pm.build_liga_lookup()
df = pm.enrich_brl(df, lk_brl, lk_ico, sm)
df = df[df['target_price_brl'].notna() & (df['target_price_brl'] > 0)].copy()

print(f'Total BRL cards: {len(df)}')
print(f'Preço BRL: min=R${df["target_price_brl"].min():.2f}, max=R${df["target_price_brl"].max():.2f}, mediana=R${df["target_price_brl"].median():.2f}')
print()

# Percentis
for p in [10, 20, 40, 60, 80, 90, 95, 99]:
    val = df['target_price_brl'].quantile(p/100)
    print(f'  {p}%: R${val:.2f}')

# Log scale bins
print()
print('=== Log bins sugeridos ===')
logs = np.logspace(0, np.log10(df['target_price_brl'].max()), 6)
for i, v in enumerate(logs):
    print(f'  Bin {i}: até R${v:.0f}')

# Percentil bins
print()
print('=== Bins por percentil (5 bins) ===')
bins = df['target_price_brl'].quantile([0, 0.2, 0.4, 0.6, 0.8, 1.0])
for i in range(5):
    print(f'  Bin {i+1}: R${bins.iloc[i]:.2f} a R${bins.iloc[i+1]:.2f} ({bins.index[i+1]*100:.0f}%)')
