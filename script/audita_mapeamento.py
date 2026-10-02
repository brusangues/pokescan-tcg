"""Auditoria do mapeamento (P2.49). Roda no ciclo da macro e GRITA se algo saiu torto.

Falha (exit != 0) só em problema REAL:
  [1] carta com en_id cujo nome EN nao bate com o nome da Liga (join torto);
  [3] sigla que o alias manda para um set EN diferente do mapa 1:1 (contradicao).
Informativo (nao falha): edicoes sem mapeamento, ids duplicados do cache.
"""
import json, re, sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
cat = json.loads((R / 'data' / 'catalogo_liga.json').read_text(encoding='utf-8'))
mapa = json.loads((R / 'data' / 'liga' / 'liga_set_sigla_ptcg.json').read_text(encoding='utf-8'))
_p = R / 'data' / 'liga' / 'liga_siglas_alias.json'
alias = json.loads(_p.read_text(encoding='utf-8')).get('alias', {}) if _p.exists() else {}

def norm(s):
    s = re.sub(r'\(.*', '', str(s or ''))
    return re.sub(r'[^a-z0-9]', '', s.lower())

# [1] integridade do join
viol = [c for c in cat if c.get('en_id') and c.get('nome_en') and norm(c['nome_en']) != norm(c.get('nEN'))]

# [2] cobertura: edicoes com carta no catalogo e sem mapeamento nenhum (informativo)
siglas = {str(c.get('sigla')) for c in cat if c.get('sigla')}
sem_map = sorted(s for s in siglas if s not in (set(mapa.values()) | set(alias)))

# [3] contradicao: a mesma sigla no alias apontando para set EN diferente do 1:1
sig2sid = {}
for sid, sig in mapa.items():
    sig2sid.setdefault(sig, set()).add(sid)
contra = {sig: sorted(sig2sid.get(sig, set()) | {d['set_en']})
          for sig, d in alias.items() if sig in sig2sid and d['set_en'] not in sig2sid[sig]}

n_cas = sum(1 for c in cat if c.get('en_id'))
print(f'📋 catalogo {len(cat)} | casadas {n_cas} | liga_only {len(cat)-n_cas}')
print(f'[1] en_id com nome divergente: {len(viol)}')
for c in viol[:5]:
    print(f"     {c.get('id')}: EN={c.get('nome_en')!r} vs LIGA={c.get('nEN')!r}")
print(f'[2] edicoes sem mapeamento: {len(sem_map)} (informativo)')
print(f'[3] alias contradizendo o mapa 1:1: {len(contra)}')
for s, v in list(contra.items())[:6]:
    print(f'     {s}: {v}')
falha = bool(viol or contra)
print('RESULTADO:', 'FALHA ❌' if falha else 'OK ✅')
sys.exit(1 if falha else 0)
