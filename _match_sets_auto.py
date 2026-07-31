import re
from pathlib import Path
import json
import requests

headers = {'User-Agent': 'Mozilla/5.0'}
content = Path(r'C:\Models\hermes\cache\web\www.ligapokemon.com.br-8804474451.md').read_text()

# Extrair: edid=NNN ed=SIGLA → Nome
# (https://www.ligapokemon.com.br/?view=cards/search&card=edid=NNN%20ed=SIGLA)
# [Nome do Set]
matches = re.findall(r'edid=(\d+)%20ed=(\w+)\)[^]]*\]\([^)]+\)\s*\n\s*\n\s*\[([^\]]+)\]', content)

print(f'Total matches: {len(matches)}')

# Agrupar por edid (deve ser único)
sets_por_edid = {}
for edid, sigla, nome in matches:
    if edid not in sets_por_edid:
        sets_por_edid[edid] = (sigla, nome)

print(f'Sets únicos: {len(sets_por_edid)}')
print()

# Mapeamento: TCGdex set_id → (edid, sigla_liga)
# Precisamos descobrir isso baixando sets TCGdex e matchando por nome
resp = requests.get('https://api.tcgdex.net/v2/en/sets', headers=headers, timeout=15)
tcg_sets = {s['id']: s['name'] for s in resp.json()}

# Match por nome (case-insensitive, partial)
tcg_to_liga = {}
for tcg_id, tcg_name in tcg_sets.items():
    tcg_lower = tcg_name.lower()
    best = None
    best_score = 0
    for edid, (sigla, nome_liga) in sets_por_edid.items():
        nome_lower = nome_liga.lower()
        # Score: chars em comum / len do nome TCGdex
        if tcg_lower in nome_lower or nome_lower in tcg_lower:
            score = len(set(tcg_lower) & set(nome_lower)) / max(len(tcg_lower), 1)
            if score > best_score:
                best_score = score
                best = (sigla, nome_liga, edid)
    if best and best_score > 0.3:
        tcg_to_liga[tcg_id] = {'sigla': best[0], 'nome_liga': best[1], 'edid': best[2], 'score': best_score}

print(f'TCGdex sets mapeados: {len(tcg_to_liga)}')
print()

# Procurar sets DP specificamente
procurados = {
    'dp1': ['Diamond & Pearl', 'Space-Time Creation'],
    'dp2': ['Diamond & Pearl', 'Secret of the Lakes'],
    'dp3': ['Shining Darkness'],
}

for tcg_id, nomes_possiveis in procurados.items():
    melhor = None
    for edid, (sigla, nome_liga) in sets_por_edid.items():
        for nome_possivel in nomes_possiveis:
            if nome_possivel.lower() in nome_liga.lower() or nome_liga.lower() in nome_possivel.lower():
                melhor = (sigla, nome_liga, edid)
                break
    if melhor:
        print(f'{tcg_id} → {melhor[0]} ({melhor[1]})')
    else:
        print(f'{tcg_id} → NÃO ENCONTRADO')