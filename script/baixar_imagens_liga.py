"""baixar_imagens_liga.py — P2.32: baixa as imagens (img_liga) de TODAS as cartas
do catálogo da Liga que NÃO estão no índice do scanner, para data/img_cache/{id}.png.

Robusto: idempotente (pula existentes), retry com backoff, rate-limit friendly
(pequena pausa), tolerante a 404/erros (pula e segue). Reusa o REPORT do gap.
Rodar antes do build_search_index p/ as cartas novas terem imagem local.
"""
import json, time, urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
IMG_CACHE = BASE / 'data' / 'img_cache'
SC = BASE / 'data' / 'scanner'
REPO = 'https://repositorio.sbrauble.com'
PAUSA = 0.05   # rate-limit friendly (20/seg)

def url_final(url: str) -> str:
    if url.startswith('//'):
        return REPO + url
    if url.startswith('/'):
        return REPO + url
    return url

def baixa(url: str, dest: Path) -> str:
    if dest.exists() and dest.stat().st_size > 5000:
        return 'cache'
    if not url or url == '-':
        return 'no-url'
    for tent in range(3):
        try:
            req = urllib.request.Request(url_final(url), headers={
                'User-Agent': 'Mozilla/5.0',
                'Referer': 'https://www.ligapokemon.com.br/'})
            with urllib.request.urlopen(req, timeout=12) as r:
                data = r.read()
            if data[:3] == b'\xff\xd8\xff':  # JPEG
                dest.write_bytes(data)
                return 'ok'
            return 'nao-jpeg'
        except Exception as e:
            if tent == 2:
                return 'fail:' + str(e)[:40]
            time.sleep(1.5 * (tent + 1))
    return 'fail'

def main():
    cat = json.loads((BASE/'data'/'catalogo_liga.json').read_text(encoding='utf-8'))
    cards_idx = set(str(c.get('id')) for c in json.loads((SC/'cards.json').read_text(encoding='utf-8')))
    faltam = []
    for c in cat:
        eid = c.get('en_id'); cid = eid if eid else f"{c.get('idE')}-{c.get('num')}"
        if str(cid) in cards_idx or not c.get('img_liga'):
            continue
        if not (IMG_CACHE / f'{cid}.png').exists():
            faltam.append((str(cid), c.get('img_liga')))
    print(f'🎯 {len(faltam)} imagens da Liga a baixar (idempotente; já-baixadas pulam)')
    stats = {'ok': 0, 'cache': 0, 'fail': 0, 'no-url': 0, 'nao-jpeg': 0}
    t0 = time.time()
    for i, (cid, url) in enumerate(faltam, 1):
        st = baixa(url, IMG_CACHE / f'{cid}.png')
        if st == 'ok':
            stats['ok'] += 1
        elif st == 'cache':
            stats['cache'] += 1
        elif st == 'no-url':
            stats['no-url'] += 1
        elif st == 'nao-jpeg':
            stats['nao-jpeg'] += 1
        else:
            stats['fail'] += 1
        if i % 200 == 0 or i == len(faltam):
            el = time.time() - t0
            print(f'  [{i}/{len(faltam)}] ok={stats["ok"]} cache={stats["cache"]} '
                  f'fail={stats["fail"]} no-url={stats["no-url"]} ({el/60:.1f}min, {el/max(i,1)*1000:.0f}ms/img)')
        time.sleep(PAUSA)
    print(f'\n✅ download: ok {stats["ok"]} + cache {stats["cache"]} = '
          f'{stats["ok"]+stats["cache"]} | fail {stats["fail"]} | no-url {stats["no-url"]} | nao-jpeg {stats["nao-jpeg"]}')
    print(f'⏱️  total {(time.time()-t0)/60:.1f} min')

if __name__ == '__main__':
    main()