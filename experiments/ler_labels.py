"""ler_labels.py — parseia a base rotulada manual do usuário (labels.txt) em JSON.

Formato (README.MD do repo labels):
- Uma linha = nome do arquivo da imagem (ANO-MES-DIA_HORAMINSEG.jpg)
- Linha opcional iniciando com '#' = comentário da disposição
- Linhas seguintes = descrições de cartas: NOME [NUM [INFO [ANO] [SET]] [LANG]]
  - NUM pode ter '/' (N/M), zero-à-esquerda mantido, ou ser promo (SM17/XY179…)
  - LANG: (kr)(jp)(en) só se ≠ português
- '--------------------------' = comentário de grupo

Saída: experiments/base_labels.json  {arquivo: {cartas:[...], comentario}}
Carta: {nome, num, set_extra, ano, lang, raw}
"""
import json, re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / '..' / 'pokescan-tcg-labels' / 'labels.txt'
OUT = REPO / 'experiments' / 'base_labels.json'

ANOS = set(str(y) for y in range(1900, 2100))
# siglas de set conhecidas (número de promo vem junto: SM17, XY179…)
SET_PAT = re.compile(r'^(?P<s>[A-Za-z]{1,3}\d{1,4}[A-Za-z]?|RC\d+|MEEpt)$')

def parse_linha(linha: str) -> dict | None:
    """Separa nome | num | set_extra | ano | lang de uma linha de carta."""
    linha = linha.strip()
    if not linha or linha.startswith('#') or set(linha) == {'-'}:
        return None
    toks = linha.split()
    out = {'nome': None, 'num': None, 'set': None, 'ano': None, 'lang': 'pt'}
    # lang no fim
    if toks and toks[-1] in ('(kr)', '(jp)', '(en)'):
        out['lang'] = toks[-1][1:-1]; toks = toks[:-1]
    if not toks:
        return None
    # ano = token 4 dígitos (1900-2099) — mover p/ ano
    resto = []
    for t in toks:
        if t in ANOS and not out['ano']:
            out['ano'] = t
        else:
            resto.append(t)
    toks = resto
    # numero = token com '/' (ex 227/198, RC32/RC32, 038/051) — pega o 1º
    num_idx = None
    for i, t in enumerate(toks):
        if '/' in t and re.match(r'^[\w/]+$', t):
            num_idx = i; out['num'] = t; break
    if num_idx is not None:
        # set_extra = tokens depois do numero (siglas/ano), antes da lang
        extras = toks[num_idx+1:]
        nome_toks = toks[:num_idx]
    else:
        # sem barra: pode ser promo (SM17, XY179) ou numero simples; o ÚLTIMO
        # token numerico/promover vira extra; colisão p/ promo no meio é rara.
        extras = [t for t in toks if SET_PAT.match(t) and not t.isdigit()]
        nome_toks = [t for t in toks if t not in extras]
        # numero simples (só dígitos) no fim, se houver
        if nome_toks and nome_toks[-1].isdigit():
            cand = nome_toks[-1]
            # evitar confundir com parte do nome composto (raro)
            out['num'] = cand; nome_toks = nome_toks[:-1]
    if extras and not out.get('set'):
        out['set'] = ' '.join(extras)
    out['nome'] = ' '.join(nome_toks) if nome_toks else None
    out['raw'] = linha
    return out

def main():
    texto = SRC.read_text(encoding='utf-8')
    linhas = texto.splitlines()
    base = {}
    cur = None
    for ln in linhas:
        ln_strip = ln.strip()
        if not ln_strip:
            continue
        if ln_strip.startswith('---') or set(ln_strip) == {'-'}:
            continue
        if not ln.startswith(' ') and ln_strip.endswith('.jpg'):
            cur = ln_strip
            base.setdefault(cur, {'cartas': [], 'comentario': None})
            continue
        if ln_strip.startswith('#'):
            if cur and not base[cur]['comentario']:
                base[cur]['comentario'] = ln_strip.lstrip('#').strip()
            continue
        # linha de carta
        card = parse_linha(ln_strip)
        if card and cur and card['nome']:
            base[cur]['cartas'].append(card)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(base, ensure_ascii=False, indent=1), encoding='utf-8')
    n_img = sum(bool(v['cartas']) for v in base.values())
    total = sum(len(v['cartas']) for v in base.values())
    print(f'✅ {OUT.name}: {len(base)} imagens, {n_img} com labels, {total} cartas')
    for f, v in base.items():
        if v['cartas']:
            langs = {}
            for c in v['cartas']: langs[c['lang']] = langs.get(c['lang'],0)+1
            print(f'  {f}: {len(v["cartas"])} cartas {langs}')
    print('\n--- amostra ---')
    for f in list(base)[:3]:
        for c in base[f]['cartas'][:3]:
            print(f'  {f} :: {c}')

if __name__ == '__main__':
    main()