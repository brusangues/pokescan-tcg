"""Gera imagens sintéticas REALISTAS: carta 63:88 (arte + borda) sobre fundos."""
import json
import random
import sys
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

BASE = Path(__file__).resolve().parent.parent
IMG = BASE / 'data' / 'img_cache'
OUT = BASE / 'experiments'

cards = json.loads((BASE / 'data' / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
com_img = [c for c in cards if (IMG / f'{c["id"]}.png').exists()]
random.seed(7)
alvos = random.sample(com_img, 4)

RATIO = 88 / 63  # altura/largura da carta real

def make_card(art_pil, largura=420):
    """Arte + borda branca de carta → imagem 63:88."""
    art_w = int(largura * 0.86)
    art = art_pil.resize((art_w, int(art_w)), Image.LANCZOS)  # arte quadrada centralizada
    altura = int(largura * RATIO)
    card = Image.new('RGB', (largura, altura), (245, 245, 245))
    # borda interna colorida estilo carta (dourada/azul)
    card.paste(art, ((largura - art_w) // 2, (altura - art_w) // 2))
    return np.array(card)

def compose(card_np, fundo, ang):
    h, w = fundo.shape[:2]
    ch, cw = card_np.shape[:2]
    # padding p/ a carta rotacionada caber inteira
    pad = int(max(cw, ch) * 0.17)
    canvas_c = np.zeros((ch + 2*pad, cw + 2*pad, 3), np.uint8)
    canvas_c[pad:pad+ch, pad:pad+cw] = card_np
    cch, ccw = canvas_c.shape[:2]
    rad = np.deg2rad(ang)
    M = cv2.getRotationMatrix2D((ccw/2, cch/2), ang, 1.0)
    rot = cv2.warpAffine(canvas_c, M, (ccw, cch), borderValue=(0, 0, 0), flags=cv2.INTER_LINEAR)
    # máscara exata do quadrilátero da carta rotacionada
    corners = np.array([[pad,pad],[pad+cw-1,pad],[pad+cw-1,pad+ch-1],[pad,pad+ch-1]], np.float32)
    corners = cv2.transform(corners.reshape(1,-1,2), M).reshape(-1,2)
    mask = np.zeros((cch, ccw), np.uint8)
    cv2.fillConvexPoly(mask, corners.astype(np.int32), 255)
    # posição com margem fixa de 40px
    x0 = random.randint(40, max(40, w - ccw - 40))
    y0 = random.randint(40, max(40, h - cch - 40))
    canvas = fundo.copy()
    canvas[y0:y0+cch, x0:x0+ccw] = np.where(mask[..., None] == 255, rot, canvas[y0:y0+cch, x0:x0+ccw])
    # sombra
    sh = np.zeros_like(canvas)
    shadow_pts = corners + np.array([x0, y0]) + np.array([6, 8])
    cv2.fillConvexPoly(sh, shadow_pts.astype(np.int32), (15, 15, 15))
    sh = cv2.GaussianBlur(sh, (31, 31), 0)
    canvas = cv2.addWeighted(canvas, 1, sh, 0.4, 0)
    canvas[y0:y0+cch, x0:x0+ccw] = np.where(mask[..., None] == 255, rot, canvas[y0:y0+cch, x0:x0+ccw])
    return canvas, corners + np.array([x0, y0]), (x0, y0, ccw, cch)

for i, c in enumerate(alvos):
    art = Image.open(IMG / f'{c["id"]}.png').convert('RGB')
    card_np = make_card(art)
    # fundo: mesa clara, escura, textura, listrada
    tipo = i % 4
    if tipo == 0:
        fundo = np.full((900, 1200, 3), np.random.randint(180, 220, 3), np.uint8)
        fundo = cv2.add(fundo, np.random.randint(-15, 15, fundo.shape, np.int16).astype(np.int16).clip(0, 255).astype(np.uint8))
    elif tipo == 1:
        fundo = np.full((900, 1200, 3), np.random.randint(35, 70, 3), np.uint8)
    elif tipo == 2:
        fundo = np.full((900, 1200, 3), 140, np.uint8)
        for x in range(0, 1200, 50):
            cv2.line(fundo, (x, 0), (x - 70, 900), (np.random.randint(80, 130),) * 3, 4)
    else:
        fundo = np.full((900, 1200, 3), (90, 110, 100), np.uint8)
        cv2.rectangle(fundo, (0, 0), (1200, 900), (60, 75, 68), -1)

    ang = random.uniform(-22, 22)
    canvas, corners, box = compose(card_np, fundo, ang)
    p = OUT / f'_clip2_{i}.jpg'
    cv2.imwrite(str(p), canvas, [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(f'{p.name}: {c["id"]} {c["name"]} ang={ang:.0f} carta={box[2]}x{box[3]} cantos={corners.tolist()}')
