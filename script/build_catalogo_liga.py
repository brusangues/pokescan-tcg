"""build_catalogo_liga.py — Fase 2.2: monta o CATÁLOGO CONSOLIDADO LIGA-FIRST.

Parte de TODAS as cartas das edições da LIGA POKEMON (data/liga/set_{idE}.json) —
nomes pt-BR (nPT), número (sN), edição (idE), preços BRL — e faz LEFT JOIN com a
fonte EN (pokemontcg via set_mapping + número extraído do nEN) + has_ptbr MEP.

Saída: data/catalogo_liga.json  (lista de cartas, chave = {idE}-{num}).
É a fonte canônica que as demais fases (site, scanner, modelos) passam a consumir.

Uso: python script/build_catalogo_liga.py
"""
import json, re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LIGA = BASE / 'data' / 'liga'

# 1. Mapa EN (pokemontcg) por id EN: {id: carta}
EN = json.loads((BASE / 'data' / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
en_by_id = {}
for c in EN:
    en_by_id[c['id']] = c

# 2. set_mapping EN->sigla; inverter p/ sigla->set_EN; + mapa por sigla
sm = json.loads((LIGA / 'liga_set_sigla_ptcg.json').read_text(encoding='utf-8'))  # set_EN -> sigla
sigla2set = {}
for set_en, sigla in sm.items():
    sigla2set.setdefault(sigla.upper(), []).append(set_en)

# 3. Índice EN por (set, número) — para o join por sN
en_by_set_num = {}
for c in EN:
    en_by_set_num.setdefault(c['id'].rsplit('-', 1)[0], {})[c.get('number', '')] = c

def extrair_num_en(nEN):
    """'Rowlet (#043/∞)' -> '043'; '#sv2/..' -> numero normalizado; None se ausente."""
    m = re.search(r'#([0-9A-Za-z]+)/', nEN or '')
    if not m:
        m = re.search(r'#([0-9A-Za-z]+)\b', nEN or '')
    if not m: return None
    return m.group(1).lstrip('0') or '0'

# 4. Iterar todas as edições da Liga
out = []
n_liga = 0; n_join_en = 0
eids = sorted([p.stem[4:] for p in LIGA.glob('set_*.json') if p.stem[4:].isdigit()], key=int)
for eid in eids:
    setp = LIGA / f'set_{eid}.json'
    try: cartas = json.loads(setp.read_text(encoding='utf-8'))
    except: continue
    if not isinstance(cartas, list): continue
    sigla = (cartas[0].get('sSigla') or '').upper() if cartas else ''
    sets_en = sigla2set.get(sigla, [])
    for c in cartas:
        sN = c.get('sN')
        num = str(int(sN)) if isinstance(sN, str) and sN.isdigit() else sN
        n_liga += 1
        # join EN: pega do 1o set EN candidato a carta com o número (extraído do nEN ou sN)
        num_en = extrair_num_en(c.get('nEN') or '')
        en = None
        for cand in {num_en, str(int(num)) if num.isdigit() else num}.union({num}):
            if not cand: continue
            for se in sets_en:
                en = en_by_set_num.get(se, {}).get(cand)
                if en: break
            if en: break
        out.append({
            'id': f'{eid}-{num}',
            'idE': int(eid) if str(eid).isdigit() else eid,
            'idNC': c.get('idNC', 0),
            'sigla': sigla,
            'num': num,
            'nPT': (c.get('nPT') or '').strip(),
            'nEN': c.get('nEN') or '',
            'sC': c.get('sC'), 'iCO': c.get('iCO'), 'iR': c.get('iR'),
            'preco_brl_p1a': c.get('p1a'), 'p1b': c.get('p1b'), 'p1c': c.get('p1c'),
            'preco_menor': c.get('precoMenor'), 'preco_maior': c.get('precoMaior'),
            'img_liga': c.get('sP') or '',
            'liga_only': en is None,
        })
        if en:
            n_join_en += 1
            out[-1]['en_id'] = en['id']
            out[-1]['en_set'] = en['set']['id']
            out[-1]['nome_en'] = en.get('name')
            out[-1]['img_en'] = (en.get('images') or {}).get('small', '')
            prices = (en.get('tcgplayer') or {}).get('prices') or {}
            out[-1]['preco_usd'] = prices.get('market') if isinstance(prices, dict) else None

OUT = BASE / 'data' / 'catalogo_liga.json'
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(f'✅ Catálogo Liga-first: {len(out)} cartas (join EN: {n_join_en} | liga_only: {len(out)-n_join_en})')
print(f'Salvo em {OUT} ({OUT.stat().st_size/1e6:.1f} MB)')