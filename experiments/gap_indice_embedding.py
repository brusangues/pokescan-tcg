"""gap_indice_embedding.py — P2.32: mede o gap REAL do índice do scanner.

Cartas em data/catalogo_liga.json fora do índice (data/scanner) são candidatas.
NÃO basta indexar todas — subsets JP podem ter MESMA arte que a versão EN já
indexada (duplicaria arte e confundiria o matching). Este script baixa a imagem
(img_liga) da candidata, calcula seu embedding DINOv2 (mesmo pipeline do
build_search_index) e mede o cosseno contra o índice atual:

  cosseno >= .90  → 'coberta' (mesma arte já indexada; pula)
  cosseno <  .90  → 'gap'     (arte única que o usuário fotografaria e n/ casa)

Saída: data/scanner/gap_embedding_{ts}.json + contagem. Uso: --amostra N p/ rodar
rápido e validar a metodologia antes de processar tudo (17k imagens).
"""
import argparse, json, time, urllib.request
from pathlib import Path
import numpy as np
import cv2, onnxruntime as ort
from PIL import Image

BASE = Path(__file__).resolve().parent.parent
SC = BASE / 'data' / 'scanner'
IMG_CACHE = BASE / 'data' / 'img_cache'
REPO = 'https://repositorio.sbrauble.com'
THRESH = 0.90

_sess, _idx, _cards = None, None, None

def load():
    global _sess, _idx, _cards
    if _idx is not None: return
    _cards = json.loads((SC/'cards.json').read_text(encoding='utf-8'))
    u16 = np.fromfile(SC/'index_pca128_fp16.bin', dtype=np.uint16)
    _idx = u16.view(np.float16).astype(np.float32)
    _sess = ort.InferenceSession(str(BASE/'experiments'/'models'/'dv_model_uint8.onnx'),
                                 providers=['CPUExecutionProvider'])

def baixa_img(url, dest):
    """Baixa a imagem da Liga se não tiver cache. Retorna (path, ok)."""
    if dest.exists() and dest.stat().st_size > 5000:
        return dest, True
    if not url or url == '-':
        return None, False
    u = url
    if url.startswith('//'):
        u = REPO + url  # REPO = https://repositorio.sbrauble.com
    elif url.startswith('/'):
        u = REPO + url
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0",
                                             "Referer": "https://www.ligapokemon.com.br/"})
    for _ in range(2):
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                data = r.read()
            if data[:3] == b"\xff\xd8\xff":  # JPEG
                dest.write_bytes(data)
                return dest, True
        except Exception:
            time.sleep(0.3)
    return None, False

def preprocess(path):
    im = Image.open(path).convert('RGB')
    w, h = im.size; s = 256 / min(w, h)
    im = im.resize((round(w*s), round(h*s)), Image.BICUBIC)
    ww, hh = im.size; l, t = (ww-224)//2, (hh-224)//2
    im = im.crop((l, t, l+224, t+224))
    x = np.asarray(im, dtype=np.float32)/255.0
    m = np.array([0.485,0.456,0.406], dtype=np.float32).reshape(3,1,1)
    sd = np.array([0.229,0.224,0.225], dtype=np.float32).reshape(3,1,1)
    return ((x.transpose(2,0,1)-m)/sd)[None]

def embed_cosseno(path):
    """Embedding da imagem, projeção PCA, cosseno máx contra índice."""
    x = preprocess(path)
    hs = _sess.run(None, {'pixel_values': x})[0][0]
    v = np.concatenate([hs[0], hs[1:].mean(axis=0)]).astype(np.float32)
    pca = np.fromfile(SC/'pca_bundle.bin', dtype=np.float32)
    mean = pca[:768]; comps = pca[768:].reshape(128, 768)
    p = comps @ (v - mean)
    q = p / (np.linalg.norm(p) or 1.0)
    # cosseno contra índice (N linhas x 128, fp32). Máximo por carta.
    mat = _idx.reshape(-1, 128).astype(np.float32)
    scores = mat @ q
    return float(np.clip(scores.max(), 0, 1))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--amostra', type=int, default=0)
    ap.add_argument('--thresh', type=float, default=THRESH)
    a = ap.parse_args()
    load()
    cat = json.loads((BASE/'data'/'catalogo_liga.json').read_text(encoding='utf-8'))
    cards = set(str(c.get('id')) for c in _cards)
    fora = [c for c in cat if (c.get('en_id') or f"{c.get('idE')}-{c.get('num')}") not in cards and c.get('img_liga')]
    if a.amostra:
        fora = fora[:a.amostra]
    print(f'candidatas a avaliar: {len(fora)}')
    res = {'coberta': [], 'gap': []}
    from collections import Counter
    gap_by_set = Counter()
    t0 = time.time()
    for i, c in enumerate(fora, 1):
        cid = c.get('en_id') or f"{c.get('idE')}-{c.get('num')}"
        dest = IMG_CACHE / f'{cid}.png'
        # se a imagem EN já está em cache, usa; senão baixa img_liga
        path, ok = baixa_img(c.get('img_liga'), dest)
        if not ok:
            print(f'  [{i}] {cid} download falhou')
            continue
        cos = embed_cosseno(path)
        cat_cls = 'coberta' if cos >= a.thresh else 'gap'
        res[cat_cls].append({'id': cid, 'nPT': c.get('nPT'), 'nEN': c.get('nome_en'),
                             'sigla': c.get('sigla'), 'cosseno': round(cos, 3)})
        if cat_cls == 'gap':
            gap_by_set[c.get('sigla') or c.get('sSigla') or '?'] += 1
        if i % 20 == 0 or i == len(fora):
            el = time.time()-t0
            print(f'  [{i}/{len(fora)}] coberta={len(res["coberta"])} gap={len(res["gap"])} ({el/60:.1f}min)')
    print(f'\n=== AMOSTRA (thresh {a.thresh}) ===')
    print(f'coberta (mesma arte já indexada): {len(res["coberta"])}')
    print(f'GAP (arte única fora do índice):  {len(res["gap"])}')
    print('gap por edição:', dict(gap_by_set.most_common(15)))
    import os
    ts = os.environ.get('GAP_TS', 'amostra')
    out = SC / f'gap_embedding_{ts}.json'
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'salvo {out.name}')

if __name__ == '__main__':
    main()