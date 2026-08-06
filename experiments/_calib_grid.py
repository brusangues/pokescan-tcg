"""
Calibração dos parâmetros do clipping com as 8 fotos reais do usuário.
Ground truth: img 1-5 = Judge, 6-7 = Mareep, 8 = Power Tablet (nome do top-1
deve CONTER o alvo — qualquer print da mesma carta conta).

Varre grid (passada, eps, minArea, ratio) e reporta acertos por combinação.
Baseline: match com a imagem CRUA.
"""
import json, sys
from pathlib import Path
import numpy as np
import cv2
from PIL import Image
import onnxruntime as ort

BASE = Path(__file__).resolve().parent.parent
CAL = BASE / 'experiments' / 'calibracao'
OUT = BASE / 'data' / 'scanner'
MODEL = str(BASE / 'experiments' / 'models' / 'dv_model_uint8.onnx')

ALVOS = {1: 'judge', 2: 'judge', 3: 'judge', 4: 'judge', 5: 'judge',
         6: 'mareep', 7: 'mareep', 8: 'tablet'}

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
    l, t = (w - size)//2, (h - size)//2
    return img.crop((l, t, l+size, t+size))

def preprocess(img):
    w, h = img.size
    s = 256 / min(w, h)
    img = img.resize((round(w*s), round(h*s)), Image.BICUBIC)
    img = center_crop(img, 224)
    x = np.asarray(img, dtype=np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(3,1,1)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(3,1,1)
    return ((x.transpose(2,0,1) - mean) / std)[None]

def emb_pca(img_pil):
    hs = sess.run(None, {'pixel_values': preprocess(img_pil)})[0][0]
    v = np.concatenate([hs[0], hs[1:].mean(axis=0)])
    vp = COMPS @ (v - MEAN)
    return vp / (np.linalg.norm(vp) + 1e-9)

def top1_name(q):
    return id2name[ids[int(np.argmax(mat @ q))]]

def order(pts):
    pts = np.array(pts, np.float32)
    ssum = pts.sum(axis=1); diff = np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(ssum)], pts[np.argmin(diff)], pts[np.argmax(ssum)], pts[np.argmax(diff)]], np.float32)

PASSADAS = [((5,5), 30, 100), ((5,5), 50, 150), ((5,5), 80, 200),
            ((7,7), 50, 150), ((7,7), 80, 200),
            ((9,9), 50, 150), ((9,9), 80, 200), ((9,9), 100, 220)]
EPS = [0.02, 0.03, 0.04, 0.05, 0.06, 0.08]
MINAREAS = [0.03, 0.05, 0.08]
RATIOS = [(0.45, 0.95), (0.50, 0.93), (0.55, 0.90)]

def warp_card(img_bgr, quad, out_w=440):
    out_h = int(out_w * 88/63)
    dst = np.array([[0,0],[out_w-1,0],[out_w-1,out_h-1],[0,out_h-1]], np.float32)
    M = cv2.getPerspectiveTransform(quad, dst)
    return cv2.warpPerspective(img_bgr, M, (out_w, out_h))

# ── baseline: match cru ──
cru_acertos = 0
for n in sorted(ALVOS):
    img = cv2.imread(str(CAL / f'img_{n:02d}.jpg'))
    q = emb_pca(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
    nome = top1_name(q)
    ok = ALVOS[n] in nome.lower()
    cru_acertos += ok
    print(f'  cru img_{n:02d}: {nome} {"✓" if ok else "✗"}')
print(f'Baseline CRUA: {cru_acertos}/8\n')

# ── grid de calibração ──
from collections import defaultdict
acertos_por_cfg = defaultdict(int)
detalhe = {}

for n in sorted(ALVOS):
    img = cv2.imread(str(CAL / f'img_{n:02d}.jpg'))
    h, w = img.shape[:2]
    s = 1000 / max(h, w)
    img_r = cv2.resize(img, (int(w*s), int(h*s))) if s < 1 else img
    h, w = img_r.shape[:2]
    gray0 = cv2.cvtColor(img_r, cv2.COLOR_BGR2GRAY)

    candidatos = []  # (contorno, area_frac)
    for k, low, high in PASSADAS:
        gray = cv2.GaussianBlur(gray0, k, 0)
        edges = cv2.Canny(gray, low, high)
        edges = cv2.dilate(edges, np.ones((3,3), np.uint8), iterations=2)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < h*w*0.03:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            if x <= 2 or y <= 2 or x+bw >= w-2 or y+bh >= h-2:
                continue
            candidatos.append((cnt, area/(h*w), k, low, high))
    # dedup por contorno idêntico? não — cada passada é um contorno distinto

    for (cnt, area_frac, k, low, high) in candidatos:
        peri = cv2.arcLength(cnt, True)
        for eps in EPS:
            approx = cv2.approxPolyDP(cnt, eps*peri, True)
            if len(approx) != 4:
                continue
            q = order(approx.reshape(4, 2))
            l1 = np.linalg.norm(q[1]-q[0]); l2 = np.linalg.norm(q[2]-q[1])
            ratio = min(l1, l2)/max(l1, l2)
            for mina in MINAREAS:
                if area_frac < mina:
                    continue
                for (rmin, rmax) in RATIOS:
                    if not (rmin <= ratio <= rmax):
                        continue
                    cfg = (k, low, high, eps, mina, rmin, rmax)
                    warp = warp_card(img, q / s)
                    qe = emb_pca(Image.fromarray(cv2.cvtColor(warp, cv2.COLOR_BGR2RGB)))
                    nome = top1_name(qe)
                    ok = ALVOS[n] in nome.lower()
                    if ok:
                        acertos_por_cfg[cfg] += 1
                        detalhe.setdefault(cfg, {})[n] = nome

print('Top-25 configurações por acertos:')
for cfg, ac in sorted(acertos_por_cfg.items(), key=lambda x: -x[1])[:25]:
    k, low, high, eps, mina, rmin, rmax = cfg
    print(f'  {ac}/8  blur={k[0]} Canny({low},{high}) eps={eps} minArea={mina} ratio=({rmin},{rmax})')
    print(f'       acertos: {detalhe[cfg]}')
