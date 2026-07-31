import pandas as pd, numpy as np, json, re
from pathlib import Path
import requests

headers = {'User-Agent': 'Mozilla/5.0'}

# Carregar lookup da Liga
liga_dir = Path('data/liga')
liga_lookup = {}
for f in sorted(liga_dir.glob('set_[0-9]*.json')):
    with open(f) as fh:
        for c in json.load(fh):
            sigla = str(c.get('sSigla', '')).strip()
            m = re.search(r'\(?#?(\d+)', str(c.get('nEN', '')))
            if not m: continue
            num = int(m.group(1))
            nen = str(c.get('nEN', ''))
            name_m = re.match(r'^([^(#]+)', nen)
            nome = name_m.group(1).strip().lower() if name_m else ''
            key = (sigla, num)
            if key not in liga_lookup:
                liga_lookup[key] = {'nome': nome, 'preco': float(c.get('p1b', 0) or 0)}

# Para cada set TCGdex problematico, testar todas as siglas da Liga
sets_problem = ['sm2', 'sm3', 'sm4', 'sm5', 'sm6', 'sm7', 'sm8', 'sm9', 'sm10', 'sm11', 'sm12',
                'xy1', 'xy2', 'xy5', 'xy6', 'xy7', 'xy8', 'xy9', 'xy10', 'xy11', 'xy12',
                'bw1', 'bw6', 'bw7', 'bw8', 'dp1', 'dp2', 'dp3']

# Coletar TODAS as siglas da Liga
todas_siglas = sorted(set(s for s, n in liga_lookup.keys()))

print('Testando melhores siglas para cada set...')
for sid in sets_problem:
    cards_data = []
    resp = requests.get(f'https://api.tcgdex.net/v2/en/sets/{sid}', headers=headers, timeout=15)
    if resp.status_code != 200: continue
    sdata = resp.json()
    
    for c in sdata.get('cards', []):
        cid = c.get('id', '')
        parts = cid.split('-')
        if len(parts) != 2: continue
        num = re.sub(r'[^0-9]', '', parts[1])
        if not num: continue
        cards_data.append({'id': cid, 'num': int(num), 'name': c.get('name', '').lower()})
    
    melhores = []
    for sigla in todas_siglas[:50]:  # amostra 50 siglas
        match_count = 0
        for cd in cards_data[:100]:
            key = (sigla, cd['num'])
            if key in liga_lookup:
                match_count += 1
        if match_count > 0:
            melhores.append((sigla, match_count, len(cards_data)))
    
    if melhores:
        melhores.sort(key=lambda x: -x[1])
        print(f'{sid:12s} → {melhores[0][0]:8s} ({melhores[0][1]}/{melhores[0][2]} cards)')
        if len(melhores) > 1 and melhores[1][1] >= melhores[0][1] * 0.8:
            print(f'  também: {melhores[1][0]} ({melhores[1][1]}), {melhores[2][0] if len(melhores)>2 else ""} ({melhores[2][1] if len(melhores)>2 else ""})')
    else:
        print(f'{sid:12s} → NENHUMA sigla encontrada')
