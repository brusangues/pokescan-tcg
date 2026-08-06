"""Compara recall PCA32/64/128 + raw fp32/fp16 (1000 cartas, 3 augs)."""
import sys, json, random
from pathlib import Path
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import onnxruntime as ort
from sklearn.decomposition import PCA

BASE = Path(__file__).resolve().parent.parent
IMG_CACHE = BASE / 'data' / 'img_cache'
OUT = BASE / 'data' / 'scanner'
MODEL = str(BASE / 'experiments' / 'models' / 'dinov2_small_q4f16.onnx')
N = 1000
SEED = 42
AUGS = 3
random.seed(SEED); np.random.seed(SEED)

raw = np.load(OUT / 'embeddings_raw.npy')
ids = json.loads((OUT / 'ids.json').read_text(encoding='utf-8'))
idx_of = {cid: i for i, cid in enumerate(ids)}
print(f'Raw: {raw.shape}')

com_imagem = [c for c in json.loads((BASE/'data'/'ptcg_cards_cache.json').read_text(encoding='utf-8'))
              if (IMG_CACHE / f'{c["id"]}.png').exists()]
amostra = random.sample(com_imagem, N)

def center_crop(img, size):
    w, h = img.size
    l, t = (w-size)//2, (h-size)//2
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

def augment(img, seed):
    rng = random.Random(seed)
    out = img
    if rng.random() < 0.7: out = ImageEnhance.Brightness(out).enhance(rng.uniform(0.85, 1.15))
    if rng.random() < 0.7: out = ImageEnhance.Contrast(out).enhance(rng.uniform(0.85, 1.15))
    if rng.random() < 0.5: out = out.rotate(rng.uniform(-4, 4), resample=Image.BICUBIC)
    if rng.random() < 0.3: out = out.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 1.0)))
    return out

sess = ort.InferenceSession(MODEL, providers=['CPUExecutionProvider'])

# embeddings das queries (augs) — extrai 1x, reusa em todos os testes
queries = []  # (linha, emb 768d)
for i, c in enumerate(amostra):
    img = Image.open(IMG_CACHE / f'{c["id"]}.png').convert('RGB')
    linha = idx_of[c['id']]
    for a in range(AUGS):
        q = augment(img, SEED + i*10 + a)
        hs = sess.run(None, {'pixel_values': preprocess(q)})[0][0]
        v = np.concatenate([hs[0], hs[1:].mean(axis=0)])
        queries.append((linha, v.astype(np.float32)))
print(f'Queries: {len(queries)}')

def recall(transf_idx, transf_query):
    mat = transf_idx / (np.linalg.norm(transf_idx, axis=1, keepdims=True) + 1e-9)
    h1 = h5 = 0
    for linha, v in queries:
        vp = transf_query(v)
        vp = vp / (np.linalg.norm(vp) + 1e-9)
        sims = mat @ vp
        top5 = np.argsort(-sims)[:5]
        if top5[0] == linha: h1 += 1
        if linha in top5: h5 += 1
    return h1/len(queries), h5/len(queries)

# ── 1. Raw fp32 e fp16
r1, r5 = recall(raw, lambda v: v)
print(f'raw fp32 (62.7 MB):  recall@1={r1:.4f} recall@5={r5:.4f}')
raw16 = raw.astype(np.float16)
r1, r5 = recall(raw16.astype(np.float32), lambda v: v.astype(np.float16).astype(np.float32))
print(f'raw fp16 (31.4 MB):  recall@1={r1:.4f} recall@5={r5:.4f}')

# ── 2. PCA com vários componentes
for k in [32, 48, 64, 96, 128, 192, 256]:
    pca = PCA(n_components=k, whiten=True).fit(raw)
    idx_r = pca.transform(raw).astype(np.float32)
    def q(v, pca=pca):
        return pca.transform(v.reshape(1, -1))[0].astype(np.float32)
    r1, r5 = recall(idx_r, q)
    mb = idx_r.nbytes / 1e6
    print(f'PCA{k:3d} ({mb:5.1f} MB, var={pca.explained_variance_ratio_.sum():.3f}): recall@1={r1:.4f} recall@5={r5:.4f}')
