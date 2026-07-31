import pandas as pd, numpy as np
import pokemon_price_monitor as pm

cards = pm.fetch_all_cards(max_sets=50)
df = pd.DataFrame([pm.parse_card(c) for c in cards])
df = pm.enrich_pricing(df)
df = df[df['target_price'].notna() & (df['target_price'] > 0)].copy()

# Split temporal
df_sorted = df.sort_values('release_year', na_position='first').reset_index(drop=True)
split_idx = int(len(df_sorted) * 0.8)
df_sorted['split'] = ['treino' if i < split_idx else 'teste' for i in range(len(df_sorted))]

# Tentar merge BRL
lk_brl, lk_ico, sm = pm.build_liga_lookup()
df_merged = pm.enrich_brl(df_sorted.copy(), lk_brl, lk_ico, sm)

# Predição BRL (pra todas as cartas, mesmo sem merge)
df_merged['target_price_usd'] = df_merged['target_price'].fillna(0)
m_brl = pm.load_model_brl()
X = pm.prepare_features(df_merged, extra_features=['target_price_usd'])
pred_log = m_brl.predict(X)
df_merged['pred_brl'] = np.expm1(pred_log)

# Separar merged (com preço BRL) vs unmerged (sem preço BRL)
com_merge = df_merged[df_merged['target_price_brl'].notna()].copy()
sem_merge = df_merged[df_merged['target_price_brl'].isna()].copy()

print(f'Total cartas com USD: {len(df_merged)}')
print(f'Com merge BRL:        {len(com_merge)} ({len(com_merge)/len(df_merged):.1%})')
print(f'Sem merge BRL:        {len(sem_merge)} ({len(sem_merge)/len(df_merged):.1%})\n')

print('='*70)
print('=== 5 EXEMPLOS COM MERGE BRL (SUCESSO) ===')
print('='*70)
for _, r in com_merge.sample(5, random_state=42).iterrows():
    print(f"ID: {r['id']:<12} | Nome: {r['name']:<22} | Set: {r['set_id']:<8} | Split: {r['split']}")
    print(f"  Raridade: {str(r.get('rarity_tcg', '?')):<18} | USD: ${r['target_price']:>6.2f} | BRL Real: R${r['target_price_brl']:>7.2f} | Pred BRL: R${r['pred_brl']:>7.2f} | iCO: {r.get('iCO',0)}")
    print()

print('='*70)
print('=== 5 EXEMPLOS SEM MERGE BRL (FALHA NO MATCH) ===')
print('='*70)
for _, r in sem_merge.sample(5, random_state=42).iterrows():
    print(f"ID: {r['id']:<12} | Nome: {r['name']:<22} | Set: {r['set_id']:<8} | Split: {r['split']}")
    print(f"  Raridade: {str(r.get('rarity_tcg', '?')):<18} | USD: ${r['target_price']:>6.2f} | BRL Real: N/A     | Pred BRL: R${r['pred_brl']:>7.2f}")
    print()
