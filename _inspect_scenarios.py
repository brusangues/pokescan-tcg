import pandas as pd, numpy as np
import pokemon_price_monitor as pm

# Coleta dados + predicoes
cards = pm.fetch_all_cards(max_sets=50)
df = pd.DataFrame([pm.parse_card(c) for c in cards])
df = pm.enrich_pricing(df)
df = df[df['target_price'].notna() & (df['target_price'] > 0)].copy()

# Split temporal
df_sorted = df.sort_values('release_year', na_position='first').reset_index(drop=True)
split_idx = int(len(df_sorted) * 0.8)
df_sorted['split'] = ['treino' if i < split_idx else 'teste' for i in range(len(df_sorted))]

# Merge BRL
lk_brl, lk_ico, sm = pm.build_liga_lookup()
df_merged = pm.enrich_brl(df_sorted.copy(), lk_brl, lk_ico, sm)

# Predicoes BRL
df_merged['target_price_usd'] = df_merged['target_price'].fillna(0)
m_brl = pm.load_model_brl()
X = pm.prepare_features(df_merged, extra_features=['target_price_usd'])
pred_log = m_brl.predict(X)
df_merged['pred_brl'] = np.expm1(pred_log)

# Filtra quem tem BRL real vs quem nao tem
merged_ok = df_merged[df_merged['target_price_brl'].notna()].copy()
merged_ok['erro_abs'] = (merged_ok['pred_brl'] - merged_ok['target_price_brl']).abs()
merged_ok['erro_pct'] = ((merged_ok['pred_brl'] - merged_ok['target_price_brl']) / merged_ok['target_price_brl']) * 100

sem_merge = df_merged[df_merged['target_price_brl'].isna()].copy()

# Separar cenários
erro_baixo = merged_ok.sort_values('erro_abs').head(5)
erro_alto = merged_ok.sort_values('erro_abs', ascending=False).head(5)

print("="*80)
print("1. MERGE OK - ERRO BAIXO (PREDIÇÃO QUASE PERFEITA)")
print("="*80)
for _, r in erro_baixo.iterrows():
    print(f"ID: {r['id']:<12} | Nome: {r['name']:<22} | Set: {r['set_id']:<8} | Split: {r['split']}")
    print(f"  Raridade: {str(r.get('rarity_tcg','?')):<18} | Holo: {r.get('is_holo',0)} | iCO: {r.get('iCO',0)}")
    print(f"  USD: ${r['target_price']:>6.2f} | Real BRL: R${r['target_price_brl']:>7.2f} | Pred BRL: R${r['pred_brl']:>7.2f} | Erro: R${r['erro_abs']:>5.2f}")
    print()

print("="*80)
print("2. MERGE OK - ERRO ALTO (DISCREPÂNCIA GRANDE)")
print("="*80)
for _, r in erro_alto.iterrows():
    print(f"ID: {r['id']:<12} | Nome: {r['name']:<22} | Set: {r['set_id']:<8} | Split: {r['split']}")
    print(f"  Raridade: {str(r.get('rarity_tcg','?')):<18} | Holo: {r.get('is_holo',0)} | iCO: {r.get('iCO',0)}")
    print(f"  USD: ${r['target_price']:>6.2f} | Real BRL: R${r['target_price_brl']:>7.2f} | Pred BRL: R${r['pred_brl']:>7.2f} | Erro: R${r['erro_abs']:>5.2f} ({r['erro_pct']:+.0f}%)")
    print()

print("="*80)
print("3. SEM MERGE (SOMENTE PREÇO USD DISPONÍVEL)")
print("="*80)
for _, r in sem_merge.sample(5, random_state=123).iterrows():
    print(f"ID: {r['id']:<12} | Nome: {r['name']:<22} | Set: {r['set_id']:<8} | Split: {r['split']}")
    print(f"  Raridade: {str(r.get('rarity_tcg','?')):<18} | Holo: {r.get('is_holo',0)}")
    print(f"  USD: ${r['target_price']:>6.2f} | Real BRL: N/A     | Pred BRL (estimada): R${r['pred_brl']:>7.2f}")
    print()
