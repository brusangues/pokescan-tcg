import pandas as pd, numpy as np
import pokemon_price_monitor as pm

cards = pm.fetch_all_cards(max_sets=50)
df = pd.DataFrame([pm.parse_card(c) for c in cards])
df = pm.enrich_pricing(df)
df = df[df['target_price'].notna() & (df['target_price'] > 0)].copy()

lk_brl, lk_ico, sm = pm.build_liga_lookup()
df = pm.enrich_brl(df, lk_brl, lk_ico, sm)

merged = df['target_price_brl'].notna().sum()
total = len(df)
print(f'Total: {total} | Merged: {merged} ({merged/total:.1%}) | Unmerged: {total-merged} ({(total-merged)/total:.1%})')