#!/usr/bin/env python
"""Baixa os set_*.json da Liga que faltam (edid conhecido dos hits + varredura p/ OBF/PAF)."""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scrapers import get_driver

REPO = Path(__file__).resolve().parent.parent
LIGA_DIR = REPO / 'data' / 'liga'
SET_IDS_PATH = LIGA_DIR / 'liga_set_ids.json'

# set_id → idE (descobertos nos scored_hits)
CONHECIDOS = [
    ('sv3pt5', 411),   # MEW  (151)
    ('sv4', 439),      # PAR  (Paradox Rift)
    ('sv7', 612),      # SCR  (Stellar Crown)
    ('sv8pt5', 649),   # PRE  (Prismatic Evolutions)
    ('sv10', 706),     # DRI  (Destined Rivals)
]
# faixas a varrer: OBF entre PAL(391) e MEW(411); PAF entre PAR(439) e SV4A(453)
VARRER = list(range(392, 410)) + list(range(440, 452))


def baixa_set(driver, eid):
    url = f'https://www.ligapokemon.com.br/?view=cards/search&card=edid={eid}%20ed=POR'
    driver.get(url)
    time.sleep(4)
    m = re.search(r'var cardsjson = (\[.*?\]);', driver.page_source, re.DOTALL)
    if not m:
        return None
    cards = json.loads(m.group(1))
    if not cards:
        return None
    sigla = cards[0].get('sSigla', '?')
    set_path = LIGA_DIR / f'set_{eid}.json'
    set_path.write_text(json.dumps(cards, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    return sigla, len(cards)


def main():
    driver = get_driver()
    set_ids = set(json.loads(SET_IDS_PATH.read_text())) if SET_IDS_PATH.exists() else set()
    alvos = {eid: sid for sid, eid in CONHECIDOS}
    # varredura: só testa se o arquivo ainda não existe
    for eid in VARRER:
        if not (LIGA_DIR / f'set_{eid}.json').exists():
            alvos[eid] = '?'
    for eid, sid in sorted(alvos.items()):
        print(f'==> edid={eid} ({sid})...')
        try:
            res = baixa_set(driver, eid)
        except Exception as e:
            print(f'    ERRO {e}')
            continue
        if res:
            sigla, n = res
            print(f'    {sigla}: {n} cartas')
            if sigla.upper() in ('OBF', 'SV3A') and sid == '?':
                print(f'    ★ OBSIDIAN FLAMES = edid {eid}')
            if sigla.upper() in ('PAF', 'SV1V') and sid == '?':
                print(f'    ★ PALDEAN FATES = edid {eid}')
        else:
            print('    (vazio)')
    set_ids |= set(alvos)
    SET_IDS_PATH.write_text(json.dumps(sorted(set_ids)))
    print('feito.')


if __name__ == '__main__':
    main()
