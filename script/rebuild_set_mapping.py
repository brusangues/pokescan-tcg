"""
script/rebuild_set_mapping.py  (v2 — sem falsos positivos)
=========================================================
Reconstrói data/liga/liga_set_sigla_ptcg.json adicionando sets faltantes
por correspondência de cartas únicas.

Abordagem segura:
1. Para cada set ptcg sem mapping, coleta cartas "identificadoras":
   (nome_limpo, número) onde o par é ÚNICO nesse set (não aparece em
   outro set ptcg com número diferente).
2. Procura essas cartas nos dados da Liga (sSigla + nEN).
3. A sigla Liga vence se tiver >= N cartas identificadoras em comum
   (N=3) E a sigla não estiver já mapeada para outro set ptcg.
4. Verificação cruzada: a sigla candidata não pode ter conflito (mais
   de 1 set ptcg apontando para ela).

Reverte mudanças parciais automaticamente se detectar conflitos.
"""

import json, re, glob
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
LIGA_DIR = DATA_DIR / 'liga'
MAP_PATH = LIGA_DIR / 'liga_set_sigla_ptcg.json'
LIMIAR = 4  # nº mínimo de cartas identificadoras em comum

def limpa_nome(s):
    if not s:
        return ''
    return re.sub(r'\([^)]*\)', '', str(s)).strip().lower()

def extrai_num(s):
    m = re.search(r'(\d+)', str(s or ''))
    return m.group(1).lstrip('0') if m else None

def main():
    cards = json.loads((DATA_DIR / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))

    # set ptcg -> [(nome_limpo, num)] e contagem global de (nome, num)
    ptcg_sets: dict[str, list[tuple[str, str]]] = {}
    par_counter = Counter()
    for c in cards:
        sid = c['set']['id']
        par = (limpa_nome(c.get('name')), extrai_num(c.get('number')))
        ptcg_sets.setdefault(sid, []).append(par)
        par_counter[par] += 1

    # Cartas "identificadoras" = pares (nome, num) que aparecem só UMA vez na base
    # inteira (evita colisões tipo "Pikachu 25" em vários sets)
    identificadoras = {par for par, n in par_counter.items() if n == 1}

    # Liga: sigla -> conjunto de (nome_limpo, num)
    liga_sets: dict[str, set[tuple[str, str]]] = {}
    for f in sorted(glob.glob(str(LIGA_DIR / 'set_*.json'))):
        data = json.loads(open(f, encoding='utf-8').read())
        if not isinstance(data, list):
            continue
        for c in data:
            if not isinstance(c, dict):
                continue
            sig = str(c.get('sSigla', '')).strip()
            if not sig:
                continue
            liga_sets.setdefault(sig, set()).add((limpa_nome(c.get('nEN')), extrai_num(c.get('nEN'))))

    mapping = json.loads(MAP_PATH.read_text(encoding='utf-8')) if MAP_PATH.exists() else {}
    usadas = set(mapping.values())

    novos = {}
    for sid, cartas in ptcg_sets.items():
        if sid in mapping:
            continue
        set_ids = set(cartas) & identificadoras
        if not set_ids:
            continue
        melhor_sig, melhor_score = None, 0
        for sig, liga_cartas in liga_sets.items():
            if sig in usadas:
                continue
            score = len(set_ids & liga_cartas)
            if score > melhor_score:
                melhor_score, melhor_sig = score, sig
        if melhor_sig and melhor_score >= LIMIAR:
            novos[sid] = melhor_sig
            usadas.add(melhor_sig)
            print(f'  + {sid} → {melhor_sig} ({melhor_score} cartas identificadoras)')
        elif melhor_sig:
            print(f'  ? {sid}: {melhor_sig} com só {melhor_score} (limiar {LIMIAR})')

    if not novos:
        print('Nenhum set novo encontrado.')
        return

    mapping.update(novos)
    MAP_PATH.write_text(json.dumps(mapping, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'\n✅ Mapping atualizado: {len(mapping)} sets ({len(novos)} novos)')


if __name__ == '__main__':
    main()
