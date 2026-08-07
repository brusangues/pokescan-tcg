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
    ('me2', 735),      # M2   (Phantasmal Flames / Fogo Fantasmagórico)
    ('me3', 764),      # M3   (Perfect Order)
    ('me4', 771),      # M4   (Chaos Rising / Caos Ascendente)
    ('me5', 777),      # M5   (Pitch Black / Escuridão Absoluta)
]
# faixas a varrer: me1 antes do M2(735); me2pt5 entre M2(735) e M3(764)
VARRER = list(range(710, 734)) + list(range(736, 763))


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
            su = sigla.upper()
            if su in ('M1', 'MEG', 'ME1') and sid == '?':
                print(f'    ★ MEGA EVOLUTION (me1) = edid {eid}')
            if su in ('M25', 'ME2.5', 'ASC', 'ME2PT5') and sid == '?':
                print(f'    ★ ASCENDED HEROES (me2pt5) = edid {eid}')
        else:
            print('    (vazio)')
    set_ids |= set(alvos)
    SET_IDS_PATH.write_text(json.dumps(sorted(set_ids)))
    print('feito.')


if __name__ == '__main__':
    main()
