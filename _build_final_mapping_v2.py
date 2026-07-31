import pandas as pd, json, re
from pathlib import Path
import requests

headers = {'User-Agent': 'Mozilla/5.0'}

# Carregar CSV do usuário
csv_path = list(Path(r'C:\Models\hermes\cache\documents').glob('*Pokémon Completas*.csv'))[0]
liga_df = pd.read_csv(csv_path, encoding='utf-8')
print(f'Sets na lista do usuário: {len(liga_df)}')

# Construir mapping: código da Liga → (nome_en, nome_pt)
liga_sets = {}
for _, row in liga_df.iterrows():
    cod = str(row['Código']).strip()
    nome_en = str(row['Nome do Set (Inglês)']).strip()
    nome_pt = str(row['Nome do Set (Português - BR)']).strip()
    if cod:
        liga_sets[cod] = {'en': nome_en, 'pt': nome_pt}

# Baixar sets TCGdex (en e pt)
resp_en = requests.get('https://api.tcgdex.net/v2/en/sets', headers=headers, timeout=15)
tcg_en = {s['id']: s['name'] for s in resp_en.json()}

resp_pt = requests.get('https://api.tcgdex.net/v2/pt/sets', headers=headers, timeout=15)
tcg_pt = {s['id']: s['name'] for s in resp_pt.json()}

print(f'Sets TCGdex EN: {len(tcg_en)}')
print(f'Sets TCGdex PT: {len(tcg_pt)}')

def normalize(name):
    return re.sub(r'[^a-z0-9]', '', name.lower()).strip()

# Match por nomes EN e PT
mapping = {}
for sid in tcg_en:
    en_name = tcg_en.get(sid, '')
    pt_name = tcg_pt.get(sid, '')
    
    best = None
    best_score = 0
    
    for cod, info in liga_sets.items():
        score = 0
        
        # 1. Match exato PT
        if pt_name and normalize(pt_name) == normalize(info['pt']):
            score = 100
        # 2. Match exato EN
        elif en_name and normalize(en_name) == normalize(info['en']):
            score = 95
        # 3. Substring match PT
        elif pt_name and (normalize(pt_name) in normalize(info['pt']) or normalize(info['pt']) in normalize(pt_name)):
            score = 80
        # 4. Substring match EN
        elif en_name and (normalize(en_name) in normalize(info['en']) or normalize(info['en']) in normalize(en_name)):
            score = 75
        
        if score > best_score:
            best_score = score
            best = cod
    
    if best and best_score >= 60:
        mapping[sid] = best
    elif best and best_score >= 40:
        # Matches parciais - só incluir se não gerar ambiguidade
        candidates = [c for c, info in liga_sets.items() if 
                     (pt_name and normalize(pt_name) in normalize(info['pt'])) or
                     (en_name and normalize(en_name) in normalize(info['en']))]
        if len(candidates) == 1:
            mapping[sid] = best

# Mapeamentos manuais para sets que match parcial não pegou
manual = {
    'sv01': 'SV1', 'sv02': 'PAL', 'sv03': 'OBF', 'sv04': 'PAR',
    'sv05': 'TEF', 'sv06': 'TWM', 'sv07': 'SFA', 'sv08': 'SCR',
    'sv09': 'SV9', 'sv10': 'SV10',
    'sv03.5': 'SV3A', 'sv04.5': 'SV4A', 'sv06.5': 'SV6A', 'sv08.5': 'SV8A',
    'svp': 'SVP', 'sve': 'SV-BE',
    'swsh1': 'SSH', 'swsh2': 'RCL', 'swsh3': 'DAA', 'swsh4': 'VIV',
    'swsh4.5': 'SHF', 'swsh4.5sv': 'SFS',
    'swsh5': 'BST', 'swsh6': 'CRE', 'swsh7': 'EVS',
    'swsh8': 'FST', 'swsh9': 'BRS', 'swsh10': 'ASR',
    'swsh10.5': 'PGO', 'swsh10.5tg': 'ARTG',
    'swsh11': 'LOR', 'swsh11.5tg': 'LORTG',
    'swsh12': 'SIT', 'swsh12.5': 'CRZ',
    'swsh12.5tg': 'SITTG', 'swsh12.5gg': 'CZGG',
    'swshp': 'SSPR',
    'sm1': 'SUM', 'sm2': 'GRI', 'sm3': 'BUS', 'sm3.5': 'SLG',
    'sm4': 'CIN', 'sm5': 'UPR', 'sm6': 'FLI', 'sm7': 'CES',
    'sm7.5': 'DRM', 'sm8': 'LOT', 'sm9': 'TEU', 'sm10': 'UNB',
    'sm11': 'UNM', 'sm12': 'CEC', 'sm115': 'HIF',
    'smp': 'SMP',
    'xy1': 'XY', 'xy2': 'FLF', 'xy3': 'FFI', 'xy4': 'PHF',
    'xy5': 'PRC', 'xy6': 'ROS', 'xy7': 'AOR', 'xy8': 'BKT',
    'xy9': 'BKP', 'xy10': 'FCO', 'xy11': 'STS', 'xy12': 'EVO',
    'xy0': 'KSS', 'xypr': 'XYPR',
    'bw1': 'BLW', 'bw2': 'EPO', 'bw3': 'NVI', 'bw4': 'NXD',
    'bw5': 'DEX', 'bw6': 'DRX', 'bw7': 'BCR',
    'bw8': 'PLS', 'bw9': 'PLF', 'bw10': 'PLB', 'bw11': 'LTR',
    'base1': 'BS', 'base2': 'JU', 'base3': 'FO',
    'base4': 'B2', 'base5': 'TR',
    'gym1': 'G1', 'gym2': 'G2',
    'neo1': 'N1', 'neo2': 'N2', 'neo3': 'N3', 'neo4': 'N4',
    'lc': 'LC',
    'ecard1': 'EX', 'ecard2': 'AQ', 'ecard3': 'SK',
    'col1': 'CL',
    'hgss1': 'HS', 'hgss2': 'UL', 'hgss3': 'UD', 'hgss4': 'TM',
    'hgssp': 'HSPR',
    'pl1': 'PL', 'pl2': 'RR', 'pl3': 'SV', 'pl4': 'AR',
    'dpp': 'DP-P', 'dp1': 'DP1', 'dp2': 'DP2', 'dp3': 'DP3',
    'dp4': 'MT', 'dp5': 'SW',
    'ex1': 'RS', 'ex2': 'SS', 'ex3': 'DR', 'ex4': 'MA',
    'ex5': 'HL', 'ex6': 'FL', 'ex7': 'TRR', 'ex8': 'DX',
    'ex9': 'EM', 'ex10': 'UF', 'ex11': 'DS', 'ex12': 'HP',
    'ex13': 'CG', 'ex14': 'DF', 'ex15': 'PK',
    'pop1': 'P1', 'pop2': 'P2', 'pop3': 'P3', 'pop4': 'P4',
    'pop5': 'P5', 'pop6': 'P6', 'pop7': 'P7', 'pop8': 'P8', 'pop9': 'P9',
    'cel25': 'CEL', 'cel25cc': 'CCC',
    'me01': 'ME', 'me02': 'ME', 'me03': 'POR', 'me04': 'ME',
    'me05': 'ME', 'me06': 'ME', 'me07': 'ME', 'me08': 'ME', 'me09': 'ME',
    'sv1a': 'SV1A', 'sv2a': 'SV2A', 'sv2d': 'SV2D', 'sv2p': 'SV2P',
    'sv3a': 'SV3A', 'sv4a': 'SV4A', 'sv4k': 'SV4K', 'sv4m': 'SV4M',
    'sv5a': 'SV5A', 'sv5k': 'SV5K', 'sv5m': 'SV5M',
    'sv6a': 'SV6A', 'sv7a': 'SV7A', 'sv8a': 'SV8A',
    'sv9a': 'SV9A', 'sv10.5w': 'SV11W', 'sv10.5b': 'SV11B',
}

for sid, cod in manual.items():
    if cod in liga_sets or cod not in [v for v in mapping.values() if len(v) <= 6]:
        mapping[sid] = cod

print(f'\nMapping final: {len(mapping)} sets')

# Ver quantos TCGdex sets ficaram sem mapping
unmapped = [s for s in tcg_en if s not in mapping]
print(f'Não mapeados: {len(unmapped)}')
for s in unmapped:
    print(f'  {s}: EN="{tcg_en.get(s,"?")}" PT="{tcg_pt.get(s,"?")}"')

# Salvar
Path('data/liga/liga_set_sigla.json').write_text(json.dumps(mapping, indent=2, ensure_ascii=False))
print('\nSalvo: data/liga/liga_set_sigla.json')