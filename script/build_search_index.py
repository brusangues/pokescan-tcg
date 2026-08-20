"""
Gera o índice de busca do scanner no espaço do DINOv2-small q4f16 ONNX
(mesmo engine do browser — consistência por construção).

AUGMENTAÇÃO (3x): além da imagem oficial de cada carta, adiciona ao índice
embedding de VARIANTES determinísticas (rotação leve + perspectiva leve),
geradas SOMENTE a partir da imagem oficial salva (data/img_cache/{id}.png) —
NUNCA de fotos da base (sem risco de rótulo errado). O objetivo é que uma foto
real de uma carta (leve ângulo/inclinação) case melhor com uma das variantes →
cosseno maior, top-1 correto mais robusto.

Saídas em data/scanner/:
- embeddings_raw.npy      (N x 768)             — ORIGINAIS (p/ PCA fit)
- embeddings_aug_raw.npy  (N*(K) x 768)         — todas as variantes (cache)
- index_pca128_fp32.bin   (N*K x 128)           — índice aumentado normalizado
- index_pca128_fp16.bin   (N*K x 128, fp16)     — p/ o browser
- row_cards.npy           (N*K uint16)          — card de cada linha (dedup)
- pca128_stats.npy, pca_bundle.bin, ids.json, cards.json

K = 1 (base) + len(VARIANTS) cópias por carta. PCA fitado só nos ORIGINAIS.
"""
import sys, json, time
from pathlib import Path
import numpy as np
from PIL import Image
import cv2
import onnxruntime as ort

BASE = Path(__file__).resolve().parent.parent
IMG_CACHE = BASE / 'data' / 'img_cache'
OUT = BASE / 'data' / 'scanner'
OUT.mkdir(parents=True, exist_ok=True)

MODEL = str(BASE / 'experiments' / 'models' / 'dv_model_uint8.onnx')
BATCH = 32
N_COMP = 128

# ── Augmentation: variantes DETERMINÍSTICAS da imagem oficial (imita foto real) ──
VARIANTS = ['rot_2', 'persp2']   # + base = 3 cópias por carta

def var_img(img, name):
    """img: PIL RGB da carta cheia (imagem oficial). Devolve a variante."""
    W, H = img.size
    if name == 'rot_2':
        return img.rotate(2, fillcolor=(20, 20, 20))
    if name == 'persp2':
        k = 0.07
        src = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
        dst = np.float32([[W*k, 0], [W-W*k*0.4, 0], [W-W*k*0.1, H-k*H*0.2], [W*k, H+k*H*0.4]])
        M = cv2.getPerspectiveTransform(src, dst)
        return Image.fromarray(cv2.warpPerspective(np.array(img), M, (W, H),
                                borderMode=cv2.BORDER_CONSTANT, borderValue=(20, 20, 20)))
    raise ValueError(name)

def center_crop(img, size):
    w, h = img.size
    l, t = (w - size)//2, (h - size)//2
    return img.crop((l, t, l+size, t+size))

def variants_of(img):
    """PIL imagens: [base, var1, var2, ...] da carta."""
    return [img] + [var_img(img, v) for v in VARIANTS]

def preprocess(img):
    w, h = img.size
    s = 256 / min(w, h)
    img = img.resize((round(w*s), round(h*s)), Image.BICUBIC)
    img = center_crop(img, 224)
    x = np.asarray(img, dtype=np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(3, 1, 1)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(3, 1, 1)
    return ((x.transpose(2, 0, 1) - mean) / std)[None]

sess = ort.InferenceSession(MODEL, providers=['CPUExecutionProvider'])

def embed_batch(imgs):
    xs = np.concatenate([preprocess(im) for im in imgs])
    hs = sess.run(None, {'pixel_values': xs})[0]  # B,257,384
    cls = hs[:, 0]; mean = hs[:, 1:].mean(axis=1)
    return np.concatenate([cls, mean], axis=1).astype(np.float32)  # B,768

# 1. Lista cartas com imagem
cards = json.loads((BASE / 'data' / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
com_img = [c for c in cards if (IMG_CACHE / f'{c["id"]}.png').exists()]
print(f'Cartas com imagem: {len(com_img)} | K={1+len(VARIANTS)} (base + {VARIANTS})')

# 2. Embeddings ORIGINAIS (p/ PCA fit) — pula se já extraiu
RAW_PATH = OUT / 'embeddings_raw.npy'
if RAW_PATH.exists():
    raw = np.load(RAW_PATH)
    print(f'embeddings_raw.npy já existe — carregado: {raw.shape}')
else:
    t0 = time.time(); rows = []
    for i in range(0, len(com_img), BATCH):
        chunk = com_img[i:i+BATCH]
        vs = [Image.open(IMG_CACHE/f'{c["id"]}.png').convert('RGB') for c in chunk]
        rows.append(embed_batch(vs))
        if (i // BATCH) % 20 == 0: print(f'  orig {i+len(chunk)}/{len(com_img)} ({time.time()-t0:.0f}s)', flush=True)
    raw = np.concatenate(rows)
    np.save(RAW_PATH, raw)
    print(f'Extração original: {raw.shape} em {time.time()-t0:.0f}s')

# 3. PCA (128 comps, fit SOMENTE nos originais — espaço estável)
from sklearn.decomposition import PCA
pca = PCA(n_components=N_COMP, whiten=True)
_ = pca.fit_transform(raw)
print(f'PCA fit ok — variância: {pca.explained_variance_ratio_.sum():.4f}')

# 4. Embeddings das VARIANTES (cache p/ retomar) + montagem do índice aumentado
AUG_PATH = OUT / 'embeddings_aug_raw.npy'
N_AUG = len(com_img) * len(VARIANTS)
if AUG_PATH.exists():
    aug_raw = np.load(AUG_PATH)
    print(f'embeddings_aug_raw.npy já existe — carregado: {aug_raw.shape}')
else:
    t0 = time.time(); rows = []
    for i in range(0, len(com_img), BATCH):
        chunk = com_img[i:i+BATCH]
        vs = []
        for c in chunk:
            base = Image.open(IMG_CACHE/f'{c["id"]}.png').convert('RGB')
            vs += [Image.open(IMG_CACHE/f'{c["id"]}.png').convert('RGB'), *variants_of(base)[1:]]
        rows.append(embed_batch(vs))
        if (i // BATCH) % 10 == 0: print(f'  aug  {i*(len(VARIANTS))}/{N_AUG} ({time.time()-t0:.0f}s)', flush=True)
    aug_raw = np.concatenate(rows)
    np.save(AUG_PATH, aug_raw)
    print(f'Extração variantes: {aug_raw.shape} em {time.time()-t0:.0f}s')

# 5. Index aumentado: projeta originais + variantes, L2-normaliza
# aug_raw tem (1+len(VARIANTS)) linhas por carta: [base, rot, persp] — stride fixo
STRIDE_AUG = len(VARIANTS) + 1   # 3
all_raw = []
for i in range(len(com_img)):
    all_raw.append(raw[i])                       # base (embedding oficial)
    for v in range(1, STRIDE_AUG):               # variantes (rot, persp)
        all_raw.append(aug_raw[i*STRIDE_AUG + v])
full = np.stack(all_raw).astype(np.float32)   # N*K x 768, agrupado por carta
reduced = pca.transform(full).astype(np.float32)
print(f'Índice aumentado: {reduced.shape} ({(full.shape[0]/len(com_img)):.1f}x por carta)')

norms = np.linalg.norm(reduced, axis=1, keepdims=True) + 1e-9
reduced_n = (reduced / norms).astype(np.float32)
reduced_n.tofile(OUT / 'index_pca128_fp32.bin')
reduced_n.astype(np.float16).tofile(OUT / 'index_pca128_fp16.bin')

# 6. row_cards: card (índice em com_img) de cada linha — para dedup no browser
K = 1 + len(VARIANTS)
row_cards = np.repeat(np.arange(len(com_img), dtype=np.uint16), K)
np.save(OUT / 'row_cards.npy', row_cards)
row_cards.tofile(OUT / 'row_cards.bin')   # uint16 p/ o browser

comps_scaled = (pca.components_ / np.sqrt(pca.explained_variance_)[:, None]).astype(np.float32)
np.save(OUT / 'pca128_stats.npy', {
    'mean': pca.mean_.astype(np.float32),
    'components': pca.components_.astype(np.float32),
    'components_whitened': comps_scaled,
    'explained_variance_ratio': pca.explained_variance_ratio_.astype(np.float32),
})
with open(OUT / 'pca_bundle.bin', 'wb') as f:
    pca.mean_.astype(np.float32).tofile(f); comps_scaled.tofile(f)

ids = [c['id'] for c in com_img]
with open(OUT / 'ids.json', 'w', encoding='utf-8') as f:
    json.dump(ids, f)

meta = []
for c in com_img:
    prices = c.get('tcgplayer') or {}
    price = (prices.get('prices') or {}).get('market') if isinstance(prices, dict) else None
    meta.append({'id': c['id'], 'n': c.get('name', ''), 's': c['set']['id'],
                 'sn': c['set']['name'], 'num': c.get('number', ''), 'r': c.get('rarity', ''),
                 'p': round(price, 2) if isinstance(price, (int, float)) else None,
                 'img': (c.get('images') or {}).get('small', '')})
with open(OUT / 'cards.json', 'w', encoding='utf-8') as f:
    json.dump(meta, f, ensure_ascii=False)

print('\n✅ Índice aumentado gerado:')
for p in ['embeddings_raw.npy', 'embeddings_aug_raw.npy', 'index_pca128_fp16.bin',
          'pca_bundle.bin', 'row_cards.npy', 'ids.json', 'cards.json']:
    fp = OUT / p
    print(f'  {p:26s} {fp.stat().st_size/1e6:8.1f} MB')
