"""Valida recall do índice PCA128 (fp32 vs fp16) — 1000 cartas, 3 augs."""
import sys, json, random
from pathlib import Path
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import onnxruntime as ort

BASE = Path(__file__).resolve().parent.parent
IMG_CACHE = BASE / 'data' / 'img_cache'
OUT = BASE / 'data' / 'scanner'
MODEL = str(BASE / 'experiments' / 'models' / 'dv_model_uint8.onnx')
N = 1000
SEED = 42
AUGS = 3
random.seed(SEED); np.random.seed(SEED)

stats = np.load(OUT / 'pca128_stats.npy', allow_pickle=True).item()
mean = stats['mean']
comps = stats['components_whitened']  # já pré-escalada p/ whitening
ids = json.loads((OUT / 'ids.json').read_text(encoding='utf-8'))
idx_of = {cid: i for i, cid in enumerate(ids)}

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

# queries pré-computadas em 128d (fp32)
queries = []
for i, c in enumerate(amostra):
    img = Image.open(IMG_CACHE / f'{c["id"]}.png').convert('RGB')
    linha = idx_of[c['id']]
    for a in range(AUGS):
        q = augment(img, SEED + i*10 + a)
        hs = sess.run(None, {'pixel_values': preprocess(q)})[0][0]
        v = np.concatenate([hs[0], hs[1:].mean(axis=0)])
        vp = comps @ (v - mean)
        queries.append((linha, vp.astype(np.float32)))
print(f'Queries: {len(queries)}')

def recall(nome_arq, dtype):
    reduced = np.fromfile(OUT / nome_arq, dtype=dtype).reshape(-1, 128).astype(np.float32)
    mat = reduced / (np.linalg.norm(reduced, axis=1, keepdims=True) + 1e-9)
    h1 = h5 = 0
    for linha, vp in queries:
        sims = mat @ vp
        top5 = np.argsort(-sims)[:5]
        if top5[0] == linha: h1 += 1
        if linha in top5: h5 += 1
    return h1/len(queries), h5/len(queries)

for arq, dt, nome in [('index_pca128_fp32.bin', np.float32, 'PCA128 fp32 (10.5 MB)'),
                      ('index_pca128_fp16.bin', np.float16, 'PCA128 fp16 ( 5.2 MB)')]:
    r1, r5 = recall(arq, dt)
    print(f'{nome}: recall@1={r1:.4f} recall@5={r5:.4f}')
