import re, json
from pathlib import Path
import requests

headers = {'User-Agent': 'Mozilla/5.0'}

# Carregar sets da Liga (do PDF extraído)
text = Path(r'C:\Models\hermes\cache\documents\liga_sets_parte1.txt').read_text(encoding='utf-8')

# Extrair: Nome do Set SIGLA
liga_map = {}
for m in re.finditer(r'^([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .:!?-]+?)\s+([A-Z0-9]{2,6})\s*$', text, re.MULTILINE):
    nome, sigla = m.group(1).strip(), m.group(2).strip()
    if sigla not in liga_map:
        liga_map[sigla] = nome

print(f'Sets Liga: {len(liga_map)}')

# Baixar sets TCGdex
resp = requests.get('https://api.tcgdex.net/v2/en/sets', headers=headers, timeout=15)
tcgdex = {s['id']: s['name'] for s in resp.json()}
print(f'Sets TCGdex: {len(tcgdex)}')

# Match por nome (case-insensitive, português vs inglês)
# TCGdex tem nomes em PT-BR via /v2/pt/
resp_pt = requests.get('https://api.tcgdex.net/v2/pt/sets', headers=headers, timeout=15)
tcgdex_pt = {s['id']: s['name'] for s in resp_pt.json()}
print(f'Sets TCGdex PT: {len(tcgdex_pt)}')

def normalize(name):
    return re.sub(r'[^a-z0-9]', '', name.lower())

mapping = {}
for sid in tcgdex:
    # Nome em pt-BR
    pt_name = tcgdex_pt.get(sid, '')
    en_name = tcgdex.get(sid, '')
    
    best_sigla = None
    best_score = 0
    
    for sigla, liga_nome in liga_map.items():
        score = 0
        # Match exato do nome em português
        if pt_name:
            if normalize(pt_name) == normalize(liga_nome):
                score = 100
            elif normalize(pt_name) in normalize(liga_nome) or normalize(liga_nome) in normalize(pt_name):
                score = len(set(normalize(pt_name)) & set(normalize(liga_nome))) / max(len(set(normalize(pt_name))), 1) * 50
        # Também testar nome em inglês
        if en_name and score < 50:
            if normalize(en_name) in normalize(liga_nome) or normalize(liga_nome) in normalize(en_name):
                score2 = len(set(normalize(en_name)) & set(normalize(liga_nome))) / max(len(set(normalize(en_name))), 1) * 50
                score = max(score, score2)
        
        if score > best_score:
            best_score = score
            best_sigla = sigla
    
    if best_sigla and best_score >= 30:
        mapping[sid] = best_sigla

# Mapeamentos manuais para sets muito específicos
manual = {
    'dp1': 'DP1', 'dp2': 'DP2', 'dp3': 'DP3',
    'dp4': 'DP4D', 'dp5': 'DP5C',
    'sv01': 'SV1', 'sv02': 'PAL', 'sv03': 'OBF', 'sv04': 'PAR',
    'sv05': 'TEF', 'sv06': 'TWM', 'sv07': 'SFA', 'sv08': 'SCR',
    'svp': 'SVP',
    'swsh1': 'SSH', 'swsh2': 'RCL', 'swsh3': 'DAA', 'swsh4': 'VIV',
    'swsh5': 'BST', 'swsh6': 'CRE', 'swsh7': 'EVS', 
    'swsh9': 'BRS', 'swsh10': 'ASR', 'swsh11': 'LOR', 'swsh12': 'SIT',
}
for sid, sigla in manual.items():
    if sid not in mapping:
        mapping[sid] = sigla
    if mapping.get(sid) and sigla != mapping[sid]:
        # Priorizar manual
        pass

print(f'\nMapping final: {len(mapping)} sets')

# Salvar
Path('data/liga/liga_set_sigla.json').write_text(json.dumps(mapping, indent=2, ensure_ascii=False))
print('Salvo: data/liga/liga_set_sigla.json')