#!/usr/bin/env python
"""
gerar_edicoes_liga.py — gera data/liga/edicoes_liga.json, o ÍNDICE CANÔNICO de edições.

Para cada edição da Liga (idE) que existe em data/liga/set_*.json:
    {sigla, set (set_id ptcg quando casado), lang ('en'|'jp'|null), n (cartas)}

Como casa set_id ptcg → edição: OVERLAP de (nome, número normalizado) entre o cache
ptcg e as cartas do set_*.json — a edição com mais matches vence (evita os erros do
mapping manual, ex: sv4→SV4A era Shiny Treasure JP; o certo é PAR/edid 439).

Linguagem: 'jp' se o nEN usa sufixo 'JP' (ex: '#001JP/165') ou sigla em JP_SIGLAS.

Também REWRITEIA data/liga/liga_set_sigla_ptcg.json: uma entrada por set_id → sigla
da edição canônica (removendo chaves duplicadas me01/mee/me05/me02…).

Uso: python script/gerar_edicoes_liga.py
"""
import glob
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIGA = REPO / 'data' / 'liga'
CACHE = REPO / 'data' / 'ptcg_cards_cache.json'
MAP_PATH = LIGA / 'liga_set_sigla_ptcg.json'
OUT = LIGA / 'edicoes_liga.json'

# siglas JP conhecidas (edição japonesa na Liga)
JP_SIGLAS = {
    'SV1A', 'SV2A', 'SV3A', 'SV4A', 'SV5A', 'SV6A', 'SV7A', 'SV8A', 'SV9A', 'SV10A',
    'SV11W', 'SV11B', 'S9A', 'S8B', 'EPJPN', 'SVPJP', 'SV1S', 'SV1V', 'M2APB', 'M2AES',
}


def _norm_num(x) -> str:
    x = str(x).strip()
    m = re.match(r'(\d+)', x)
    return str(int(m.group(1))) if m else x.lower()


def _parse_nen(nEN: str):
    """'Eevee ex(174/∞)' | 'Bulbasaur (#001/165)' | 'Bulbasaur (#001JP/165)' → (nome, num, jp)."""
    m = re.match(r'^(.*?)\s*\(#?([^/]+)/', (nEN or '').strip())
    if not m:
        return None
    num_raw = m.group(2).strip()
    jp = 'jp' in num_raw.lower()
    return m.group(1).strip().lower(), _norm_num(num_raw), jp


def _eh_jp(sigla: str, nEN_jp: bool) -> bool:
    """Edição japonesa? Sufixo 'JP'/'JPN'/'Jp' na SIGLA (PGOJP, SVPJp, EPJPN),
    sufixo 'JP' no número do nEN, ou sigla na lista explícita."""
    if nEN_jp:
        return True
    s = sigla.upper()
    if s in JP_SIGLAS:
        return True
    if s.endswith('JP') or s.endswith('JPN'):
        return True
    # 'SV2A' (151 JP) não tem sufixo — fica na lista explícita
    return False


def edicoes_da_liga():
    ed = {}
    for f in sorted(glob.glob(str(LIGA / 'set_*.json'))):
        try:
            d = json.loads(Path(f).read_text(encoding='utf-8'))
        except Exception:
            continue
        if isinstance(d, dict):
            d = d.get('cards') or []
        if not d:
            continue
        eid = str(d[0].get('idE'))
        ed[eid] = {
            'sigla': (d[0].get('sSigla') or '').strip(),
            'set': None,
            'lang': None,
            'n': len(d),
        }
    return ed


def main():
    ed = edicoes_da_liga()
    print(f'edições na Liga: {len(ed)}')

    cache = json.loads(CACHE.read_text(encoding='utf-8'))
    # cartas do cache por set_id: {(nome_lower, num): 1}
    por_set = {}
    for c in cache:
        sid = c['set']['id']
        por_set.setdefault(sid, {}).setdefault(
            (_norm_num(c.get('number')), (c.get('name') or '').strip().lower()), 0)
        por_set[sid][(_norm_num(c.get('number')), (c.get('name') or '').strip().lower())] += 1

    # cartas da Liga por idE: {(nome_lower, num): 1} (+ flag jp por nEN)
    por_ed = {}
    for f in sorted(glob.glob(str(LIGA / 'set_*.json'))):
        try:
            d = json.loads(Path(f).read_text(encoding='utf-8'))
        except Exception:
            continue
        if isinstance(d, dict):
            d = d.get('cards') or []
        if not d:
            continue
        eid = str(d[0].get('idE'))
        idx = {}
        jp = False
        for c in d:
            p = _parse_nen(c.get('nEN'))
            if not p:
                continue
            nome, num, jp_flag = p
            idx[(num, nome)] = 1
            if jp_flag:
                jp = True
        por_ed[eid] = (idx, jp)

    # overlap set_id ptcg → edições
    scores = {}
    for sid, cards in por_set.items():
        melhores = []
        for eid, (idx, jp) in por_ed.items():
            n = sum(1 for k in cards if k in idx)
            if n >= 3:
                melhores.append((n, eid, jp))
        if melhores:
            melhores.sort(key=lambda x: -x[0])
            scores[sid] = melhores

    # monta o índice: edição → set (a melhor do set_id; se dois set_ids disputam
    # o mesmo idE, mantém o de MAIOR overlap — evita 'xy8' (5) sobrescrever 'sv4' (266))
    usados = {}
    for sid, melhores in scores.items():
        n, eid, jp = melhores[0]
        if eid not in usados or n > usados[eid][1]:
            usados[eid] = (sid, n)

    mapping = {}
    for eid, info in ed.items():
        if eid in usados:
            sid, n = usados[eid]
            info['set'] = sid
            info['n_overlap'] = n
            lang = 'jp' if _eh_jp(info['sigla'], por_ed[eid][1]) else 'en'
            info['lang'] = lang
            mapping[sid] = info['sigla']  # sigla canônica (sem duplicatas)

    # edições sem set ptcg: lang por heurística
    for eid, info in ed.items():
        if info['lang'] is None:
            info['lang'] = 'jp' if _eh_jp(info['sigla'], False) else None

    OUT.write_text(json.dumps(ed, ensure_ascii=False, indent=1, sort_keys=True), encoding='utf-8')
    print(f'salvo {OUT.name}: {len(ed)} edições, {len(mapping)} sets mapeados')

    # rewrite do liga_set_sigla_ptcg.json (1 entrada por set, sigla canônica)
    antigo = json.loads(MAP_PATH.read_text(encoding='utf-8'))
    for sid, sigla in mapping.items():
        antigo[sid] = sigla
    # remove chaves duplicadas/órfãs dos me* (me1/mee/me01...)
    for k in list(antigo):
        if k.startswith('me0') and k not in mapping:
            del antigo[k]
    MAP_PATH.write_text(json.dumps(antigo, ensure_ascii=False, indent=1, sort_keys=True), encoding='utf-8')
    print('liga_set_sigla_ptcg.json reescrito')

    print('\n=== sets sv/me mapeados (edição canônica):')
    for sid in sorted(mapping):
        if sid.startswith(('sv', 'me')):
            eid = next(e for e, i in ed.items() if i.get('set') == sid)
            print(f'  {sid} → edid {eid} ({ed[eid]["sigla"]}, {ed[eid]["lang"]}, overlap {ed[eid].get("n_overlap")})')


if __name__ == '__main__':
    main()
