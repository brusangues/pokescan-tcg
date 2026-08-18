#!/usr/bin/env python
"""
mapear_sets_tcgcsv.py — mapeamento robusto catálogo ↔ TCGCSV (cat. 3 / EN).

Estratégia de match (em ordem):
1. abbreviation (TCGCSV) == ptcgoCode (catálogo)  — sigla oficial
2. nome normalizado do grupo == nome normalizado do set
3. dicionário manual (exceções conhecidas — siglas divergentes, subsets)

Saídas (em experiments/tcgcsv/):
  set_group_map.json  — {set_id: [groupId, ...]} (candidatos, em ordem de preferência)
  pid_to_card.json    — {productId: card_id} (join fino por (set_id, número))
  mapeamento_resumo.txt — cobertura por método

NÃO toca no produtivo.
"""
import json
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EX = REPO / 'experiments' / 'tcgcsv'
CAT = '3'
UA = {'User-Agent': 'pokescan-tcg-mapeamento/0.1'}

# Exceções manuais: set_id do catálogo -> groupId(s) TCGCSV
# (siglas divergentes entre pokemontcg.io e TCGPlayer, subsets, promos)
EXCECOES = {
    'ex7': [1428],            # Team Rocket Returns: ptcgoCode TRR, TCGCSV 'RR'
    'sm1': [1863],            # Sun & Moon: ptcgoCode SUM, TCGCSV 'SM Base Set' SM01
    'cel25c': [],             # Celebrations Classic Collection (subset — sem grupo próprio)
    'swsh45sv': [],           # Shining Fates Shiny Vault (subset)
    'sma': [],                # Hidden Fates Shiny Vault (subset)
    'sv3pt5': [23237],        # 151: TCGCSV 'SV: Scarlet & Violet 151' (MEW)
    'pgo': [3064],            # Pokemon GO (PGO)
    'bw1': [1400],            # Black and White: ptcgoCode BLW colide com Trainer Kit
    'svp': [],                # SV Black Star Promos (sem grupo único)
    'swshp': [],              # SWSH Black Star Promos
    'xyp': [],                # XY Black Star Promos
    'smp': [],                # SM Black Star Promos
    'bwp': [],                # BW Black Star Promos
    'hsp': [],                # HGSS Black Star Promos
    'dpp': [],                # DP Black Star Promos
    'np': [],                 # Nintendo Black Star Promos
    'basep': [1370],          # Wizards Black Star Promos: TCGCSV 'Deck Exclusives'? (a conferir)
}


def get(url: str, retries: int = 3) -> dict:
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception as e:
            if i == retries - 1:
                raise
            time.sleep(1.5 * (i + 1))


def norm(s: str) -> str:
    return ''.join(ch for ch in (s or '').lower() if ch.isalnum())


def group_nome_base(nome: str) -> str:
    """'SWSH01: Sword & Shield Base Set' / 'SM - Guardians Rising' /
    'ME03: Perfect Order' → 'swordshield' / 'guardiansrising' / 'perfectorder'.
    Remove o prefixo (sigla + separador ':' ou ' - ') e sufixos 'Base Set'."""
    import re
    n = re.sub(r'^\w+\d*\s*[:—-]\s*', '', nome)   # prefixo tipo 'SM05 - ' / 'SV02: '
    for suf in ('Base Set', 'Base'):
        if n.strip().endswith(suf) and len(n.strip()) > len(suf):
            n = n[: -len(suf)]
    return norm(n.replace('&amp;', '&'))


def main():
    cache = json.loads((REPO / 'data' / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))

    # Sets do catálogo
    sets = {}
    for c in cache:
        s = c.get('set') or {}
        sid = s.get('id') if isinstance(s, dict) else None
        if sid:
            sets.setdefault(sid, s)

    # Groups TCGCSV
    groups = get(f'https://tcgcsv.com/tcgplayer/{CAT}/groups').get('results', [])
    g_abbr, g_nome = defaultdict(list), defaultdict(list)
    for g in groups:
        a = (g.get('abbreviation') or '').upper()
        if a:
            g_abbr[a].append(g)
        g_nome[group_nome_base(g.get('name', ''))].append(g)

    # Passo 1+2: match por sigla e por nome
    set_groups: dict[str, list[int]] = {}
    metodo = {}
    for sid, s in sets.items():
        pc = (s.get('ptcgoCode') or '').upper()
        cands = []
        if pc and pc in g_abbr:
            cands += [g['groupId'] for g in g_abbr[pc]]
        gn = norm(s.get('name', ''))
        if gn in g_nome:
            cands += [g['groupId'] for g in g_nome[gn]]
        # dedup preservando ordem
        vistos = set()
        cands = [gid for gid in cands if not (gid in vistos or vistos.add(gid))]
        if cands:
            set_groups[sid] = cands
            metodo[sid] = 'sigla' if (pc and pc in g_abbr and g_abbr[pc][0]['groupId'] == cands[0]) else 'nome'

    # Passo 3: exceções manuais
    for sid, gids in EXCECOES.items():
        if gids:
            set_groups[sid] = gids + [g for g in set_groups.get(sid, []) if g not in gids]
            metodo[sid] = 'manual'
        # gids vazio = sem grupo (subset/promo sem grupo TCGCSV)

    # Join fino: products TCGCSV → card_id via (set_id, número)
    products = json.loads((EX / 'products_en.json').read_text(encoding='utf-8'))
    by_set_num = {}
    for c in cache:
        sid = (c.get('set') or {}).get('id') if isinstance(c.get('set'), dict) else c.get('set')
        by_set_num.setdefault((sid, str(c.get('number', ''))), c.get('id'))

    # productId → (groupId, groupName) — o products_en.json não guarda groupId
    pid_gid = {}
    for pid, m in products.items():
        gn = group_nome_base(m.get('group', ''))
        if gn in g_nome:
            pid_gid[pid] = [g['groupId'] for g in g_nome[gn]]

    pid_to_card = {}
    stats = defaultdict(int)
    for pid, m in products.items():
        if not m.get('number'):
            continue
        gids = pid_gid.get(pid) or []
        achou = False
        for gid in gids:
            for sid, cand_gids in set_groups.items():
                if gid in cand_gids:
                    cid = by_set_num.get((sid, m['number']))
                    if cid:
                        pid_to_card[pid] = cid
                        stats[sid] += 1
                        achou = True
                        break
            if achou:
                break
        # fallback: match por (nome normalizado do grupo → set) sem groupId
        if not achou:
            gn = group_nome_base(m.get('group', ''))
            for sid, s in sets.items():
                if norm(s.get('name', '')) == gn:
                    cid = by_set_num.get((sid, m['number']))
                    if cid:
                        pid_to_card[pid] = cid
                        stats[sid] += 1
                    break

    (EX / 'set_group_map.json').write_text(
        json.dumps({k: v for k, v in sorted(set_groups.items())}, ensure_ascii=False), encoding='utf-8')
    (EX / 'pid_to_card.json').write_text(
        json.dumps(pid_to_card, ensure_ascii=False), encoding='utf-8')

    cobertos = len(stats)
    print(f'=== MAPEAMENTO ===')
    print(f'sets do catálogo: {len(sets)} | com grupo TCGCSV: {len(set_groups)} '
          f'({len(set_groups) / len(sets) * 100:.0f}%)')
    print(f'  por sigla: {sum(1 for m in metodo.values() if m == "sigla")} | '
          f'por nome: {sum(1 for m in metodo.values() if m == "nome")} | '
          f'manual: {sum(1 for m in metodo.values() if m == "manual")}')
    print(f'cards do catálogo com productId (join fino): {len(pid_to_card):,} '
          f'({len(pid_to_card) / len(by_set_num) * 100:.1f}% do catálogo)')
    print(f'sets com pelo menos 1 card casado: {cobertos}/{len(sets)}')

    # sets com cards mas SEM grupo mapeado (via fallback nome) — conferir
    sem_grupo = [sid for sid in stats if sid not in set_groups]
    if sem_grupo:
        print(f'  ⚠ sets casados no fallback mas sem grupo no mapa: {sem_grupo[:10]}')

    with open(EX / 'mapeamento_resumo.txt', 'w', encoding='utf-8') as fh:
        fh.write(json.dumps({'set_groups': len(set_groups), 'pid_to_card': len(pid_to_card),
                             'metodo': metodo}, ensure_ascii=False, indent=1))
    print('salvo: set_group_map.json, pid_to_card.json, mapeamento_resumo.txt')


if __name__ == '__main__':
    main()