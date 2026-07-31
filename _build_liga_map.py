import json, re
from pathlib import Path
import requests

headers = {'User-Agent': 'Mozilla/5.0'}
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'data'
LIGA_DIR = DATA_DIR / 'liga'

# 1. Carregar lookup da Liga por (sigla, num) → nome do card
liga_lookup = {}
for f in sorted(LIGA_DIR.glob('set_[0-9]*.json')):
    with open(f) as fh:
        cards = json.load(fh)
        for c in cards:
            sigla = str(c.get('sSigla', '')).strip()
            m = re.search(r'\(?#?(\d+)', str(c.get('nEN', '')))
            if not m: continue
            num = int(m.group(1))
            nen = str(c.get('nEN', ''))
            # Extrai nome do card do nEN (ex: "Pineco (#001/078)")
            name_m = re.match(r'^([^(#]+)', nen)
            nome_liga = name_m.group(1).strip().lower() if name_m else ''
            key = (sigla, num)
            if key not in liga_lookup:
                liga_lookup[key] = nome_liga

print(f'Lookup Liga: {len(liga_lookup)} ({len(set(s for s,_ in liga_lookup))} siglas)')

# 2. Baixar sets TCGdex e fazer match por nome do card
resp = requests.get('https://api.tcgdex.net/v2/en/sets', headers=headers, timeout=15)
tcg_sets = {s['id']: s for s in resp.json()}

# Match TCGdex → Liga sigla
tcg_to_liga = {}
total_cards = 0
matched_cards = 0

for sid in sorted(tcg_sets.keys()):
    resp = requests.get(f'https://api.tcgdex.net/v2/en/sets/{sid}', headers=headers, timeout=15)
    if resp.status_code != 200: continue
    sdata = resp.json()
    cards = sdata.get('cards', [])
    total_cards += len(cards)
    
    for c in cards[:150]:  # limit per set
        card_id = c.get('id', '')
        parts = card_id.split('-')
        if len(parts) != 2: continue
        local_id = re.sub(r'[^0-9]', '', parts[1])
        if not local_id: continue
        num = int(local_id)
        
        tcg_name = str(c.get('name', '')).strip().lower()
        if not tcg_name: continue
        
        # Busca na Liga pelo mesmo (sigla, num) — testa várias siglas
        # Como não sabemos a sigla, varremos todas com mesmo número
        best_match = None
        for (lsig, lnum), lnome in liga_lookup.items():
            if lnum != num: continue
            if tcg_name in lnome or lnome in tcg_name:
                best_match = lsig
                break
        
        if best_match:
            tcg_to_liga.setdefault(sid, {})[best_match] = tcg_to_liga.get(sid, {}).get(best_match, 0) + 1
            matched_cards += 1

print(f'Total cards: {total_cards}, matched: {matched_cards}')

# Para cada set, escolher a sigla Liga mais frequente
final_mapping = {}
for sid, siglas in tcg_to_liga.items():
    best_sig = max(siglas, key=siglas.get)
    count = siglas[best_sig]
    total_for_set = sum(siglas.values())
    # Só incluir se match for confiável (>=50% ou pelo menos 3 cartas)
    if count >= 3 and count / total_for_set >= 0.3:
        final_mapping[sid] = best_sig

print(f'\nMapping final: {len(final_mapping)} sets')
for sid, sig in sorted(final_mapping.items()):
    total = sum(tcg_to_liga.get(sid, {}).values())
    print(f'  {sid:12s} → {sig:8s} (matches: {tcg_to_liga[sid][sig]}/{total})')

# Salvar
output = DATA_DIR / 'liga' / 'liga_set_sigla.json'
output.write_text(json.dumps(final_mapping, indent=2, ensure_ascii=False))
print(f'\nSalvo: {output}')
