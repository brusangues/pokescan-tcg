"""P2.15: corrige liga_set_sigla_ptcg.json — resolve duplicatas e adiciona sets.

Correções com evidência de cartas identificadoras na Liga:
- sv8 (Surging Sparks): SV8A → SSP (230 matches na Liga)
- sv6 (Twilight Masquerade): SV6A → TWM (208 matches)
- bwp (BW promos): PR → BWPR (87 matches)
- sv6pt5 (Shrouded Fable): → SFA (93 matches)
- me5 (Pitch Black): → M5 (8 matches; sigla natural da Liga)

Removidos (sem cartas no cache ptcg — fantasmas que só criam colisão):
sv3a, sv4a, sv6a, sv8a, exu, A2a, tk-ex-m, tk-ex-p, miscp, P-A, mep
"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
MAP_PATH = BASE / 'data' / 'liga' / 'liga_set_sigla_ptcg.json'

mapping = json.loads(MAP_PATH.read_text(encoding='utf-8'))

correcoes = {
    'sv8': 'SSP',      # Surging Sparks (230 matches na Liga)
    'sv6': 'TWM',      # Twilight Masquerade (208)
    'sv9': 'JTG',      # Journey Together (163)
    'bwp': 'BWPR',     # BW Black Star Promos (87)
    'sv6pt5': 'SFA',   # Shrouded Fable (93)
    'me5': 'M5',       # Pitch Black (8; sigla natural da Liga)
}

remover = ['sv3a', 'sv4a', 'sv6a', 'sv8a', 'exu', 'A2a',
           'tk-ex-m', 'tk-ex-p', 'miscp', 'P-A', 'mep',
           # fantasmas: sets que não existem no cache ptcg (código TCGdex)
           'bwpr', 'ssp', 'sfa', 'm5',
           # mapeamentos errados/órfãos (sigla não existe na Liga ou conflita)
           'sv7',   # Stellar Crown: SFA é Shrouded Fable; Stellar sem match na Liga
           'sv10',  # Destined Rivals: SV10 não existe na Liga (set novo)
           'xyp', 'xy1',  # XY: sigla não existe na Liga (0 cartas) — sem match
           'ex15', 'ex16',  # PK: sigla não existe na Liga (0 cartas) — sem match
           ]

for sid, sigla in correcoes.items():
    antes = mapping.get(sid)
    mapping[sid] = sigla
    print(f'  {sid}: {antes} → {sigla}')

for sid in remover:
    if sid in mapping:
        del mapping[sid]
        print(f'  {sid}: removido (fantasma, sem cartas no cache)')

# valida: nenhuma sigla duplicada restante (exceto casos legítimos)
from collections import Counter
c = Counter(mapping.values())
dups = {k: v for k, v in c.items() if v > 1}
print(f'\nDuplicatas restantes: {dups if dups else "nenhuma"}')
print(f'Total entradas: {len(mapping)}')

MAP_PATH.write_text(json.dumps(mapping, ensure_ascii=False, indent=1), encoding='utf-8')
print('✅ Mapping salvo')
