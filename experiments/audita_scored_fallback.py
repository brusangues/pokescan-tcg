"""audita_scored_fallback.py — Réplica do fallback por NOME do cardLookup.ts.

Para toda carta do cards.json, simula a página /card?set=X&num=Y&nome=NOME
(sem sigla na URL — o fluxo que estava bugado) e verifica qual registro
escorado o bloco de preço mostraria: sort ANTIGO vs sort NOVO (bônus de set).
Reporta quantos estavam errados antes, quantos corrigidos, e os que continuam
sem cobertura (nenhum candidato no set da página).
"""
import json, re
from collections import defaultdict

BASE = r"C:\projects\pokescan-tcg\frontend\public\data"
cards = json.load(open(f"{BASE}\\cards.json", encoding="utf-8"))
scored = json.load(open(f"{BASE}\\scored_latest.json", encoding="utf-8"))
smap = json.load(open(f"{BASE}\\set_map.json", encoding="utf-8"))


def norm(n):
    return re.sub(r"[^a-z0-9]", "", (n or "").lower())


def nscored(s):
    return norm(str(s.get("nEN") or s.get("nome") or "").split("(")[0])


# índice candidatos por nome normalizado
cands_by_nome = defaultdict(list)
for s in scored:
    cands_by_nome[nscored(s)].append(s)


def set_do_registro(s):
    return str(smap.get(str(s.get("sigla", "")).lower()) or "")


def rich(s):
    return (1 if s.get("setNome") else 0) + (1 if s.get("sNumber") else 0) + (1 if s.get("nEN") else 0)


def escolhe(cands, set_pagina, bonus_set):
    def chave(s):
        setA = 1 if set_do_registro(s) == set_pagina else 0
        return -(setA * bonus_set + rich(s))
    return sorted(cands, key=chave)[0] if cands else None


n_com_cand = 0
antigo_errado = []
novo_errado = []
ficam_sem = []
for c in cards:
    cands = cands_by_nome.get(norm(c.get("n", "")))
    if not cands:
        continue
    n_com_cand += 1
    set_pagina = c["s"]
    w_old = escolhe(cands, set_pagina, 0)
    w_new = escolhe(cands, set_pagina, 9)
    if w_old and set_do_registro(w_old) != set_pagina:
        # errado SÓ se existe candidato certo que foi preterido
        tem_certo = any(set_do_registro(x) == set_pagina for x in cands)
        antigo_errado.append((c["id"], c["n"], set_pagina,
                              w_old.get("sigla"), w_old.get("card_id"), tem_certo))
    if w_new and set_do_registro(w_new) != set_pagina:
        novo_errado.append((c["id"], c["n"], set_pagina, w_new.get("sigla")))
    if not any(set_do_registro(x) == set_pagina for x in cands):
        ficam_sem.append((c["id"], c["n"], set_pagina, (w_new or {}).get("sigla")))

print(f"cartas com >=1 homonimo escorado: {n_com_cand}")
certo_antes = [a for a in antigo_errado if a[5]]
print(f"\nANTIGO: paginas mostrando registro de OUTRO set: {len(antigo_errado)} "
      f"(das quais {len(certo_antes)} tinham o registro certo disponivel)")
print(f"NOVO (bonus set): ainda errado: {len(novo_errado)}")
for e in novo_errado[:10]:
    print("   AINDA ERRADO:", e)
print(f"\nsem cobertura no proprio set (mostraria homonimo ou nada): {len(ficam_sem)}")
from collections import Counter
print("por set da pagina:", Counter(f[2] for f in ficam_sem).most_common(12))
print("\nexemplos corrigidos pelo fix:")
for a in certo_antes[:12]:
    print(f"   {a[0]:14} {a[1][:22]:24} pagina={a[2]:8} mostrava={a[3]}")
