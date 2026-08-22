"""baixar_imagens_ptbr.py — baixa as imagens das coleções pt-BR da LIGA
(edicoes em data/liga/ptbr_edicoes.json) para data/mep_cards/{imagem_mask}.
Fonte: repositorio.sbrauble.com (sP relativo + base). Só cartas base (sN numérico,
sem variantes Staff). Salva como {mask.format(num=int(sN))} — compatível com o
build_search_index.
Uso: python crawler/baixar_imagens_ptbr.py [--queto]
"""
import json, sys, time, urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LIGA = BASE / 'data' / 'liga'
CFG = json.loads((LIGA / 'ptbr_edicoes.json').read_text(encoding='utf-8'))
img_dir = BASE / CFG.get('imagens_dir', 'data/mep_cards')
img_dir.mkdir(parents=True, exist_ok=True)

BASE_IMG = 'https://repositorio.sbrauble.com'

def download(url, dest):
    if dest.exists() and dest.stat().st_size > 5000:
        return 'cache'
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                               "Referer": "https://www.ligapokemon.com.br/"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    if data[:3] != b"\xff\xd8\xff":
        raise ValueError('não é JPEG')
    dest.write_bytes(data)
    return f'{len(data)//1024}KB'

total_ok = 0; total_puladas = 0; erros = 0
for idE, meta in CFG.get('edicoes', {}).items():
    mask = meta.get('imagem_mask')
    if not mask:
        continue
    set_path = LIGA / f'set_{idE}.json'
    if not set_path.exists():
        print(f'⚠ edição {idE} sem set_.json'); continue
    sigla = meta.get('sigla')
    nome = meta.get('nome','')
    print(f'\n=== Edição {idE} ({sigla}) — {nome} ===')
    ok = 0; puladas = 0
    for carta in json.loads(set_path.read_text(encoding='utf-8')):
        sN = carta.get('sN')
        if not (isinstance(sN, str) and sN.isdigit()):
            puladas += 1; continue  # Staff/promo
        sP = carta.get('sP') or ''
        if not sP:
            puladas += 1; continue
        num = str(int(sN))
        dest = img_dir / mask.format(num=num)
        url = BASE_IMG + sP.replace('//', '/', 1) if sP.startswith('//') else BASE_IMG + '/' + sP.lstrip('/')
        try:
            r = download(url, dest)
            if r == 'cache': ok += 1
            else: ok += 1
            if r != 'cache' and len(str(r)): pass
        except Exception as e:
            erros += 1
            if erros <= 6:
                print(f'  erro {sN}: {e}')
        time.sleep(0.08)
    total_ok += ok; total_puladas += puladas
    print(f'  baixadas: {ok} | puladas (staff/sem sP): {puladas}')
print(f'\n✅ total baixadas/cache: {total_ok} | puladas: {total_puladas} | erros: {erros}')