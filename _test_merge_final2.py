import pandas as pd, numpy as np
import pokemon_price_monitor as pm

# So testar o lookup e merge sem baixar de novo
lk_brl, lk_ico, sm = pm.build_liga_lookup()
print(f'Mapping: {len(sm)} sets')
print(f'Lookup BRL: {len(lk_brl)} cartas')

# Simular merge com ids do mapping
import json
# Testar quantos ids TCGdex tem match no mapping
resp = requests.get('https://api.tcgdex.net/v2/en/sets', headers=headers, timeout=15)
tcgdex_ids = [s['id'] for s in resp.json()]

matched = sum(1 for sid in tcgdex_ids if sid in sm)
print(f'TCGdex sets nao mapeados: {[s for s in tcgdex_ids if s not in sm][:10]}')
print(f'Sets mapeados: {matched}/{len(tcgdex_ids)} ({(matched/len(tcgdex_ids)):.1%})')