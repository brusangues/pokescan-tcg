"""rerank_sinais.py — estudo OFFLINE de sinais de re-rank sobre a base rotulada.

Para cada detecção (segmentação adaptativa da réplica fiel):
  - embed FULL do crop + embed CENTER-CROP (zoom 18% — remove fundo/borda)
  - top-5 candidatos pelo cosseno global (como o site)
  - para cada candidato: imagem oficial (img_cache / mep_cards) ->
      * interseção de histograma HSV (query center vs oficial)
  - ground truth: token da label da foto

Perguntas respondidas:
  1. qual % de detecções tem a carta certa no top-5 (teto de qualquer re-rank)?
  2. cada sinal sozinho moveria o acerto@1 quanto?
  3. combinação linear simples (grid pequeno de pesos) chega a quanto?

Saída: experiments/rerank_pares.json (dataset de pares p/ CatBoost futuro)
"""
import json, sys, unicodedata, math
from pathlib import Path
import numpy as np
import cv2

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / 'experiments'))
import debug_segmentacao as ds

IMG_CACHE = BASE / 'data' / 'img_cache'
MEP_DIR = BASE / 'data' / 'mep_cards'
SAIDA = BASE / 'experiments' / 'rerank_pares.json'

TRAD = {'juiz': 'judge', 'lilian': 'lillie', 'energia': 'fire', 'fragmento': 'mysterious'}

def tok(s):
    t = unicodedata.normalize('NFD', s or '').encode('ascii', 'ignore').decode().lower()
    t = re.sub(r'[^a-z0-9]', ' ', t).split()
    return t[0] if t else ''
import re

def center_zoom(bgr, frac=0.18):
    """Corta frac de cada borda (remove fundo do quad)."""
    h, w = bgr.shape[:2]
    dx, dy = int(w*frac), int(h*frac)
    return bgr[dy:h-dy, dx:w-dx]

def hsv_sim(bgr_q, img_cand):
    """Interseção de histograma HSV (H-S) entre query center e imagem oficial."""
    def hist(bgr):
        im = cv2.resize(bgr, (110, 154))
        hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
        h = cv2.calcHist([hsv], [0, 1], None, [24, 24], [0, 180, 0, 256])
        cv2.normalize(h, h)
        return h
    return float(cv2.compareHist(hist(bgr_q), hist(img_cand), cv2.HISTCMP_INTERSECT))

def img_oficial(card):
    """Carrega a imagem oficial do candidato (EN cache ou pt-BR mep_cards)."""
    cid = card['id']
    p = IMG_CACHE / f'{cid}.png'
    if p.exists():
        return cv2.imread(str(p))
    # pt-BR (733-N / 732-N): mask MEP_PT-BR_{num}.png com zero-pad 3
    try:
        idE, num = cid.split('-')
        num_i = int(num)
        for pref in ('MEP_PT-BR_', 'MEPR_PT-BR_'):
            for pad in range(1, 4):
                cand = MEP_DIR / f'{pref}{str(num_i).zfill(pad)}.png'
                if cand.exists():
                    return cv2.imread(str(cand))
    except Exception:
        pass
    return None

def main():
    base = json.loads((BASE/'experiments'/'base_labels.json').read_text(encoding='utf-8'))
    alvos = [f for f, v in base.items() if v['cartas']]
    ds._load_index()
    pares = []
    n_det = 0
    for foto in alvos:
        path = ds.localiza(foto)
        if not path:
            continue
        img = cv2.imread(str(path))
        quads, _ = ds.detect_quads_adaptive(img, max_quads=10)
        lab_tokens = list(dict.fromkeys(tok(c['nome']) for c in base[foto]['cartas']))
        lab_set = set(lab_tokens)
        for qi, q in enumerate(quads, 1):
            warp = ds.warp_card(img, q['pts'])
            wz = center_zoom(warp)
            x_full = ds._preprocess(warp); x_cent = ds._preprocess(wz)
            hs_f = ds._sess.run(None, {'pixel_values': x_full})[0][0]
            hs_c = ds._sess.run(None, {'pixel_values': x_cent})[0][0]
            vf = np.concatenate([hs_f[0], hs_f[1:].mean(axis=0)]).astype(np.float32)
            vc = np.concatenate([hs_c[0], hs_c[1:].mean(axis=0)]).astype(np.float32)
            pf = ds._comps @ (vf - ds._pca_mean); pf /= (np.linalg.norm(pf) or 1)
            pc = ds._comps @ (vc - ds._pca_mean); pc /= (np.linalg.norm(pc) or 1)
            sf = np.clip(ds._idx @ pf, 0, 1); sc = np.clip(ds._idx @ pc, 0, 1)
            best_f = np.full(len(ds._cards), -np.inf); best_c = np.full(len(ds._cards), -np.inf)
            np.maximum.at(best_f, ds._rc, sf); np.maximum.at(best_c, ds._rc, sc)
            order = np.argsort(-best_f)[:5]
            cands = []
            for r, ci in enumerate(order):
                ci = int(ci)
                card = ds._cards[ci]
                imgo = img_oficial(card)
                hsv = hsv_sim(wz, imgo) if imgo is not None else None
                tokc = tok(card['n'])
                ok = tokc in lab_set or any(TRAD.get(lt, '') == tokc for lt in lab_set)
                cands.append({
                    'rank': r + 1, 'id': card['id'], 'nome': card['n'], 'token': tokc,
                    'cos_full': round(float(best_f[ci]), 4),
                    'cos_centro': round(float(best_c[ci]), 4),
                    'hsv': round(hsv, 4) if hsv is not None else None,
                    'correto': bool(ok),
                })
            # margens do top-1
            m_f = float(best_f[order[0]] - best_f[order[1]])
            m_c = float(best_c[order[0]] - best_c[order[1]])
            pares.append({'foto': foto, 'quad': qi, 'labels': lab_tokens,
                          'margem_full': round(m_f, 4), 'margem_centro': round(m_c, 4),
                          'top5': cands})
            n_det += 1
        print(f'{foto}: {len(quads)} quads')
    SAIDA.write_text(json.dumps(pares, ensure_ascii=False, indent=1), encoding='utf-8')

    # ── avaliação ──
    def acc(score_fn):
        hit = tot = 0
        for p in pares:
            c = p['top5']
            vals = [score_fn(x, p) for x in c]
            best = max(range(5), key=lambda i: vals[i])
            tot += 1
            hit += 1 if c[best]['correto'] else 0
        return hit, tot

    print(f'\n=== {n_det} detecções ===')
    h, t = acc(lambda x, p: x['cos_full']); print(f'baseline cos_full      : {h}/{t} ({100*h/t:.0f}%)')
    h, t = acc(lambda x, p: x['cos_centro']); print(f'centro só             : {h}/{t} ({100*h/t:.0f}%)')
    h, t = acc(lambda x, p: max(x['cos_full'], x['cos_centro'])); print(f'max(full,centro)      : {h}/{t} ({100*h/t:.0f}%)')
    h, t = acc(lambda x, p: (x['hsv'] if x['hsv'] is not None else 0)); print(f'hsv só                : {h}/{t} ({100*h/t:.0f}%)')
    # teto: correto está no top-5?
    teto = sum(1 for p in pares if any(x['correto'] for x in p['top5'][:1]))  # rank1 já contado
    no5 = sum(1 for p in pares if any(x['correto'] for x in p['top5']))
    print(f'teto top-5 (correto presente): {no5}/{len(pares)} ({100*no5/max(len(pares),1):.0f}%)')
    # grid de pesos simples: a*cos_full + b*cos_centro + c*hsv
    print('\ngrid pesos (a,b,c):')
    melhor = (None, 0)
    for a in (1.0, 0.7, 0.5):
        for b in (0.0, 0.3, 0.5):
            for cc in (0.0, 0.2, 0.4):
                if a + b + cc == 0: continue
                hh, tt = acc(lambda x, p, a=a, b=b, cc=cc: a*x['cos_full'] + b*x['cos_centro'] +
                             cc*(x['hsv'] if x['hsv'] is not None else np.median([y['hsv'] or .3 for y in p['top5']])))
                pct = 100*hh/tt
                if pct > melhor[1]: melhor = ((a, b, cc), pct)
                if pct >= 66: print(f'  ({a},{b},{cc}): {hh}/{tt} ({pct:.0f}%)')
    print(f'melhor grid: {melhor}')

if __name__ == '__main__':
    main()