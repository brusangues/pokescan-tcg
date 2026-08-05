"""Gera frontend/public/fetch_result.json com amostra real do cache local.

Formato idêntico à resposta da pokemontcg.io (/v2/cards) — serve de
bucket offline para o /api/cards quando a API externa falha.
Amostra: cartas variadas (raridades, tipos, eras) para o Scanner funcionar.
"""
import json, random
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE = BASE_DIR / 'data' / 'ptcg_cards_cache.json'
OUT = BASE_DIR / 'frontend' / 'public' / 'fetch_result.json'

cards = json.loads(CACHE.read_text(encoding='utf-8'))
print(f'Cache: {len(cards)} cartas')

# Estratificação: pega cartas de eras diferentes e raridades variadas
random.seed(42)
amostra = []
sets_usados = set()
# 1 por set até ~24 sets, priorizando os mais recentes e o base set
for c in sorted(cards, key=lambda c: c['set'].get('releaseDate', ''), reverse=True):
    sid = c['set']['id']
    if sid in sets_usados:
        continue
    sets_usados.add(sid)
    amostra.append(c)
    if len(amostra) >= 24:
        break

# Garante algumas do Base Set (scanner testa com elas)
base = [c for c in cards if c['set']['id'] == 'base1'][:5]
ids_amostra = {c['id'] for c in amostra}
for c in base:
    if c['id'] not in ids_amostra:
        amostra.append(c)

# Embaralha e corta em ~30
random.shuffle(amostra)
amostra = amostra[:30]

payload = {
    'data': amostra,
    'page': 1,
    'pageSize': len(amostra),
    'count': len(amostra),
    'totalCount': len(amostra),
}

OUT.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
print(f'Gerado: {OUT} ({len(amostra)} cartas, {len(sets_usados)} sets)')
for c in amostra[:5]:
    print(f'  {c["id"]}: {c["name"]} ({c["set"]["name"]})')
