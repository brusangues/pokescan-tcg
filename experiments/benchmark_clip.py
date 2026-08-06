"""
Benchmark REAL do clipping: cartas 63:88 sobre fundos variados.
Mede recall@1: (1) imagem CRUA (com fundo); (2) imagem CLIPADA via warp do
quadrilátero DETECTADO pelo pipeline multi-passada (não o GT).

Uso: python experiments/benchmark_clip.py
"""
import json, random
from pathlib import Path
import numpy as np
import cv2
from PIL import Image
import onnxruntime as ort

BASE = Path(__file__).resolve().parent.parent
IMG = BASE / 'data' / 'img_cache'
OUT = BASE / 'data' / 'scanner'
MODEL = str(BASE / 'experiments' / 'models' / 'dv_model_uint8.onnx')

N = 120
SEED = 11
RATIO = 88 / 63
random.seed(SEED); np.random.seed(SEED)

reduced = np.fromfile(OUT / 'index_pca128_fp32.bin', dtype=np.float32).reshape(-1, 128)
ids = json.loads((OUT / 'ids.json').read_text(encoding='utf-8'))
idx_of = {cid: i for i, cid in enumerate(ids)}
stats = np.load(OUT / 'pca128_stats.npy', allow_pickle=True).item()
MEAN = stats['mean']; COMPS = stats['components_whitened']
mat = reduced / (np.linalg.norm(reduced, axis=1, keepdims=True) + 1e-9)

cards = json.loads((BASE / 'data' / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
com_img = [c for c in cards if (IMG / f'{c["id"]}.png').exists() and c['id'] in idx_of]
amostra = random.sample(com_img, N)

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
    vp = vp / (np.linalg.norm(vp) + 1e-9)
    return vp

def make_card(art_pil, largura=420):
    art_w = int(largura * 0.86)
    art = art_pil.resize((art_w, art_w), Image.LANCZOS)
    altura = int(largura * RATIO)
    card = Image.new('RGB', (largura, altura), (245, 245, 245))
    card.paste(art, ((largura - art_w)//2, (altura - art_w)//2))
    return np.array(card)

def compose(card_np, fundo, ang):
    h, w = fundo.shape[:2]
    ch, cw = card_np.shape[:2]
    pad = int(max(cw, ch) * 0.17)
    canvas_c = np.zeros((ch + 2*pad, cw + 2*pad, 3), np.uint8)
    canvas_c[pad:pad+ch, pad:pad+cw] = card_np
    cch, ccw = canvas_c.shape[:2]
    rad = np.deg2rad(ang)
    M = cv2.getRotationMatrix2D((ccw/2, cch/2), ang, 1.0)
    rot = cv2.warpAffine(canvas_c, M, (ccw, cch), borderValue=(0, 0, 0))
    corners = np.array([[pad,pad],[pad+cw-1,pad],[pad+cw-1,pad+ch-1],[pad,pad+ch-1]], np.float32)
    corners = cv2.transform(corners.reshape(1,-1,2), M).reshape(-1,2)
    mask = np.zeros((cch, ccw), np.uint8)
    cv2.fillConvexPoly(mask, corners.astype(np.int32), 255)
    x0 = random.randint(40, max(40, w - ccw - 40))
    y0 = random.randint(40, max(40, h - cch - 40))
    canvas = fundo.copy()
    canvas[y0:y0+cch, x0:x0+ccw] = np.where(mask[..., None] == 255, rot, canvas[y0:y0+cch, x0:x0+ccw])
    sh = np.zeros_like(canvas)
    cv2.fillConvexPoly(sh, (corners + np.array([x0+6, y0+8])).astype(np.int32), (15, 15, 15))
    sh = cv2.GaussianBlur(sh, (31, 31), 0)
    canvas = cv2.addWeighted(canvas, 1, sh, 0.4, 0)
    canvas[y0:y0+cch, x0:x0+ccw] = np.where(mask[..., None] == 255, rot, canvas[y0:y0+cch, x0:x0+ccw])
    return canvas, corners + np.array([x0, y0])

PASSADAS = [((5,5), 50, 150), ((5,5), 80, 200), ((7,7), 50, 150), ((9,9), 50, 150), ((9,9), 80, 200)]

def order(pts):
    s = pts.sum(axis=1); d = np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], np.float32)

def detect(img_bgr):
    h, w = img_bgr.shape[:2]
    s = 1000 / max(h, w)
    img = cv2.resize(img_bgr, (int(w*s), int(h*s))) if s < 1 else img_bgr
    h, w = img.shape[:2]
    gray0 = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    for k, low, high in PASSADAS:
        gray = cv2.GaussianBlur(gray0, k, 0)
        edges = cv2.Canny(gray, low, high)
        edges = cv2.dilate(edges, np.ones((3,3), np.uint8), iterations=2)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < h*w*0.05: continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            if x <= 2 or y <= 2 or x+bw >= w-2 or y+bh >= h-2: continue
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02*peri, True)
            if len(approx) == 4:
                quad = approx.reshape(4, 2).astype(np.float32) / s
                q = order(quad)
                l1 = np.linalg.norm(q[1]-q[0]); l2 = np.linalg.norm(q[2]-q[1])
                ratio = min(l1, l2) / max(l1, l2)
                if 0.50 <= ratio <= 0.93:
                    return q
    return None

def warp_card(img_bgr, quad, out_w=440):
    out_h = int(out_w * RATIO)
    dst = np.array([[0,0],[out_w-1,0],[out_w-1,out_h-1],[0,out_h-1]], np.float32)
    M = cv2.getPerspectiveTransform(quad, dst)
    return cv2.warpPerspective(img_bgr, M, (out_w, out_h))

det_ok = 0
hits_cru = hits_clip = 0
tipos = ['mesa_clara', 'mesa_escura', 'listrada', 'lisa_escura']

for i, c in enumerate(amostra):
    art = Image.open(IMG / f'{c["id"]}.png').convert('RGB')
    card_np = make_card(art)
    tipo = i % 4
    if tipo == 0:
        fundo = np.full((900, 1200, 3), np.random.randint(180, 220, 3), np.uint8)
        fundo = np.clip(fundo.astype(np.int16) + np.random.randint(-15, 15, fundo.shape, np.int16), 0, 255).astype(np.uint8)
    elif tipo == 1:
        fundo = np.full((900, 1200, 3), np.random.randint(35, 70, 3), np.uint8)
    elif tipo == 2:
        fundo = np.full((900, 1200, 3), 140, np.uint8)
        for x in range(0, 1200, 50):
            cv2.line(fundo, (x, 0), (x - 70, 900), (np.random.randint(80, 130),)*3, 4)
    else:
        fundo = np.full((900, 1200, 3), (60, 75, 68), np.uint8)
    ang = random.uniform(-22, 22)
    canvas, _ = compose(card_np, fundo, ang)
    linha = idx_of[c['id']]

    quad = detect(canvas)
    if quad is not None:
        det_ok += 1
        warp = warp_card(canvas, quad)
        q_clip = emb_pca(Image.fromarray(cv2.cvtColor(warp, cv2.COLOR_BGR2RGB)))
    else:
        q_clip = None
    q_cru = emb_pca(Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)))

    def recall(q):
        return int(np.argmax(mat @ q)) == linha
    if recall(q_cru): hits_cru += 1
    if q_clip is not None and recall(q_clip): hits_clip += 1
    if i < 10:
        print(f'  [{i}] {c["id"]:16s} fundo={tipos[tipo]:14s} ang={ang:5.1f} quad={"OK" if quad is not None else "FALHOU"}')

print(f'\nDetecção quadrilátero: {det_ok}/{N} ({det_ok/N:.1%})')
print(f'recall@1 CRUA (com fundo): {hits_cru/N:.3f} ({hits_cru}/{N})')
print(f'recall@1 CLIPADA (warp real): {hits_clip/N:.3f} ({hits_clip}/{N})')
