"""
_analisar_multicartas.py — analisa UMA imagem (possivelmente com N cartas)
usando o pipeline real do scanner (Canny multi-passada + warp + DINOv2 PCA128).

Uso: python experiments/_analisar_multicartas.py <imagem> [--top 3] [--min-area 0.03]
"""
import json
import sys
from pathlib import Path

import numpy as np
import cv2
from PIL import Image
import onnxruntime as ort

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / 'data' / 'scanner'
MODEL = str(BASE / 'experiments' / 'models' / 'dv_model_uint8.onnx')

reduced = np.fromfile(OUT / 'index_pca128_fp32.bin', dtype=np.float32).reshape(-1, 128)
ids = json.loads((OUT / 'ids.json').read_text(encoding='utf-8'))
stats = np.load(OUT / 'pca128_stats.npy', allow_pickle=True).item()
MEAN = stats['mean']; COMPS = stats['components_whitened']
mat = reduced / (np.linalg.norm(reduced, axis=1, keepdims=True) + 1e-9)
cards = json.loads((BASE / 'data' / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
id2name = {c['id']: c['name'] for c in cards}

sess = ort.InferenceSession(MODEL, providers=['CPUExecutionProvider'])


def center_crop(img, size):
    w, h = img.size
    l, t = (w - size) // 2, (h - size) // 2
    return img.crop((l, t, l + size, t + size))


def preprocess(img):
    w, h = img.size
    s = 256 / min(w, h)
    img = img.resize((round(w * s), round(h * s)), Image.BICUBIC)
    img = center_crop(img, 224)
    x = np.asarray(img, dtype=np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(3, 1, 1)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(3, 1, 1)
    return ((x.transpose(2, 0, 1) - mean) / std)[None]


def emb_pca(img_pil):
    hs = sess.run(None, {'pixel_values': preprocess(img_pil)})[0][0]
    v = np.concatenate([hs[0], hs[1:].mean(axis=0)])
    vp = COMPS @ (v - MEAN)
    return vp / (np.linalg.norm(vp) + 1e-9)


def top_k(q, k=3):
    scores = mat @ q
    idx = np.argsort(-scores)[:k]
    return [(ids[i], float(scores[i]), id2name.get(ids[i], '?')) for i in idx]


def order(pts):
    pts = np.array(pts, np.float32)
    ssum = pts.sum(axis=1); diff = np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(ssum)], pts[np.argmin(diff)], pts[np.argmax(ssum)], pts[np.argmax(diff)]], np.float32)


PASSADAS = [((5,5), 30, 100), ((5,5), 50, 150), ((5,5), 80, 200),
            ((7,7), 50, 150), ((7,7), 80, 200),
            ((9,9), 50, 150), ((9,9), 80, 200), ((9,9), 100, 220)]
EPS = [0.02, 0.03, 0.04, 0.05, 0.06, 0.08]
RATIOS = [(0.45, 0.95), (0.50, 0.93), (0.55, 0.90)]


def warp_card(img_bgr, quad, out_w=440):
    out_h = int(out_w * 88 / 63)
    dst = np.array([[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]], np.float32)
    M = cv2.getPerspectiveTransform(quad, dst)
    return cv2.warpPerspective(img_bgr, M, (out_w, out_h))


def main():
    path = sys.argv[1]
    top_k_n = int(sys.argv[sys.argv.index('--top') + 1]) if '--top' in sys.argv else 3
    min_area = float(sys.argv[sys.argv.index('--min-area') + 1]) if '--min-area' in sys.argv else 0.03

    img = cv2.imread(path)
    if img is None:
        print('ERRO: não consegui ler a imagem', path)
        return
    h, w = img.shape[:2]
    print(f'Imagem: {w}x{h}')

    # ── Baseline cru (imagem inteira) ──
    q = emb_pca(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
    print('\n── Baseline CRUA (imagem inteira) ──')
    for i, (cid, sc, nome) in enumerate(top_k(q, top_k_n), 1):
        print(f'  #{i} {cid:14s} {sc*100:5.1f}%  {nome}')

    # ── Detecção de quadriláteros (cartas) ──
    s = 1000 / max(h, w)
    img_r = cv2.resize(img, (int(w * s), int(h * s))) if s < 1 else img
    h2, w2 = img_r.shape[:2]
    gray0 = cv2.cvtColor(img_r, cv2.COLOR_BGR2GRAY)

    quads = []  # (quad em coords originais, area_frac)
    for k, low, high in PASSADAS:
        gray = cv2.GaussianBlur(gray0, k, 0)
        edges = cv2.Canny(gray, low, high)
        edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < h2 * w2 * 0.03:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            if x <= 2 or y <= 2 or x + bw >= w2 - 2 or y + bh >= h2 - 2:
                continue
            peri = cv2.arcLength(cnt, True)
            for eps in EPS:
                approx = cv2.approxPolyDP(cnt, eps * peri, True)
                if len(approx) != 4:
                    continue
                qq = order(approx.reshape(4, 2))
                l1 = np.linalg.norm(qq[1] - qq[0]); l2 = np.linalg.norm(qq[2] - qq[1])
                ratio = min(l1, l2) / max(l1, l2)
                for (rmin, rmax) in RATIOS:
                    if rmin <= ratio <= rmax:
                        quads.append((qq / s, area / (h * w)))
                        break
                break

    # dedup: agrupa quads com centro próximo (< 15% da diagonal)
    dedup = []
    diag = (w * w + h * h) ** 0.5
    for qq, af in quads:
        c = qq.mean(axis=0)
        if all(np.linalg.norm(c - dd[0].mean(axis=0)) > 0.15 * diag for dd in dedup):
            dedup.append((qq, af))
        else:
            # mantém o de maior área
            for i, dd in enumerate(dedup):
                if np.linalg.norm(c - dd[0].mean(axis=0)) <= 0.15 * diag and af > dd[1]:
                    dedup[i] = (qq, af)

    print(f'\n── Quadriláteros detectados (min-area {min_area:.0%}): {len(dedup)} ──')
    for i, (qq, af) in enumerate(sorted(dedup, key=lambda d: -d[1]), 1):
        warp = warp_card(img, qq)
        qe = emb_pca(Image.fromarray(cv2.cvtColor(warp, cv2.COLOR_BGR2RGB)))
        print(f'\n  Carta {i} (área {af:.0%} da imagem):')
        for j, (cid, sc, nome) in enumerate(top_k(qe, top_k_n), 1):
            print(f'    #{j} {cid:14s} {sc*100:5.1f}%  {nome}')
        # salva o warp p/ inspeção
        out_p = BASE / 'experiments' / f'warp_carta_{i}.png'
        cv2.imwrite(str(out_p), warp)
        print(f'    (warp salvo em {out_p})')


if __name__ == '__main__':
    main()
