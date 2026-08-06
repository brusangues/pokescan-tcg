"""
Benchmark de modelos de busca (scanner) — MobileCLIP-S0 vs DINOv2-small.
Simula foto imperfeita: augmentações leves na imagem oficial servem de
query; o índice usa as imagens oficiais. Mede recall@1 e recall@5.
"""
import sys, json, random, time
from pathlib import Path
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import onnxruntime as ort

BASE = Path(__file__).resolve().parent.parent
IMG_CACHE = BASE / 'data' / 'img_cache'
N = 1000          # cartas no benchmark
SEED = 42
AUGS = 3          # augmentações por carta (query)

random.seed(SEED)
np.random.seed(SEED)

# ── 1. Seleciona 1000 cartas com imagem ────────────────────────────
cards = json.loads((BASE / 'data' / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
com_imagem = [c for c in cards if (IMG_CACHE / f'{c["id"]}.png').exists()]
amostra = random.sample(com_imagem, N)
print(f'Cartas: {len(amostra)} (de {len(com_imagem)} com imagem)')

# ── 2. Preprocessamento (replica Transformers.js) ──────────────────
def center_crop(img, size):
    w, h = img.size
    left = (w - size) // 2
    top = (h - size) // 2
    return img.crop((left, top, left + size, top + size))

def preprocess_mobileclip(img, crop=256):
    # resize shortest_edge=256 (bicubic), center_crop 256, /255, sem normalize
    w, h = img.size
    scale = 256 / min(w, h)
    img = img.resize((round(w * scale), round(h * scale)), Image.BICUBIC)
    img = center_crop(img, crop)
    x = np.asarray(img, dtype=np.float32) / 255.0
    return x.transpose(2, 0, 1)[None]  # 1,3,256,256

def preprocess_dinov2(img, crop=224):
    # resize shortest_edge=256 (bicubic), center_crop 224, /255, normalize
    w, h = img.size
    scale = 256 / min(w, h)
    img = img.resize((round(w * scale), round(h * scale)), Image.BICUBIC)
    img = center_crop(img, crop)
    x = np.asarray(img, dtype=np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(3, 1, 1)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(3, 1, 1)
    x = (x.transpose(2, 0, 1) - mean) / std
    return x[None]

def augment(img, seed):
    """Fotos imperfeitas: brilho/contraste/rotação leve/blur."""
    rng = random.Random(seed)
    out = img
    if rng.random() < 0.7:
        out = ImageEnhance.Brightness(out).enhance(rng.uniform(0.85, 1.15))
    if rng.random() < 0.7:
        out = ImageEnhance.Contrast(out).enhance(rng.uniform(0.85, 1.15))
    if rng.random() < 0.5:
        out = out.rotate(rng.uniform(-4, 4), resample=Image.BICUBIC, expand=False)
    if rng.random() < 0.3:
        out = out.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 1.0)))
    return out

# ── 3. Extração via ONNX (com batch — muito mais rápido) ───────────
def load_sess(path):
    return ort.InferenceSession(path, providers=['CPUExecutionProvider'])

sess_mc = load_sess(str(BASE / 'experiments' / 'models' / 'mobileclip_s0_int8.onnx'))
sess_dv = load_sess(str(BASE / 'experiments' / 'models' / 'dinov2_small_q4f16.onnx'))
BATCH = 32

def emb_mobileclip_batch(imgs):
    xs = np.concatenate([preprocess_mobileclip(img) for img in imgs])  # B,3,256,256
    outs = []
    for i in range(0, len(xs), BATCH):
        o = sess_mc.run(None, {'pixel_values': xs[i:i + BATCH]})[0]
        outs.append(o)
    out = np.concatenate(outs)  # B,512
    return out / (np.linalg.norm(out, axis=1, keepdims=True) + 1e-9)

def emb_dinov2_batch(imgs):
    xs = np.concatenate([preprocess_dinov2(img) for img in imgs])  # B,3,224,224
    outs = []
    for i in range(0, len(xs), BATCH):
        o = sess_dv.run(None, {'pixel_values': xs[i:i + BATCH]})[0]
        outs.append(o)
    hs = np.concatenate(outs)  # B,257,384
    cls = hs[:, 0]
    mean = hs[:, 1:].mean(axis=1)
    v = np.concatenate([cls, mean], axis=1)  # B,768
    return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)

def run_benchmark(extract_batch_fn, nome):
    print(f'\n=== {nome} ===')
    t0 = time.time()
    # Monta lista de (id, imagem_original, [imagens_aug])
    itens = []
    for i, c in enumerate(amostra):
        img = Image.open(IMG_CACHE / f'{c["id"]}.png').convert('RGB')
        augs = [augment(img, seed=SEED + i * 10 + a) for a in range(AUGS)]
        itens.append((c['id'], img, augs))

    # Extrai índice (originais) em batch
    idx = {}
    for i in range(0, len(itens), BATCH):
        chunk = itens[i:i + BATCH]
        embs = extract_batch_fn([x[1] for x in chunk])
        for (cid, _, _), e in zip(chunk, embs):
            idx[cid] = e
    print(f'  índice: {len(idx)} ({time.time()-t0:.0f}s)')

    # Extrai queries (augmentadas) em batch
    queries = []
    for i in range(0, len(itens), BATCH):
        chunk = itens[i:i + BATCH]
        aug_flat = [a for x in chunk for a in x[2]]
        embs = extract_batch_fn(aug_flat)
        k = 0
        for cid, _, augs in chunk:
            for a in range(AUGS):
                queries.append((cid, embs[k])); k += 1
    print(f'  queries: {len(queries)} ({time.time()-t0:.0f}s total extração)')

    ids = list(idx.keys())
    mat = np.stack([idx[i] for i in ids])
    mat_n = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)

    hits1 = hits5 = 0
    t0 = time.time()
    for id_certo, emb in queries:
        sims = mat_n @ emb
        top5 = np.argsort(-sims)[:5]
        top5_ids = {ids[j] for j in top5}
        if ids[top5[0]] == id_certo:
            hits1 += 1
        if id_certo in top5_ids:
            hits5 += 1
    total = len(queries)
    print(f'  busca: {time.time()-t0:.0f}s')
    print(f'  recall@1: {hits1/total:.4f} ({hits1}/{total})')
    print(f'  recall@5: {hits5/total:.4f} ({hits5}/{total})')
    return hits1 / total, hits5 / total

# ── 4. Roda ambos ──────────────────────────────────────────────────
r1_mc, r5_mc = run_benchmark(emb_mobileclip_batch, 'MobileCLIP-S0 (512d)')
r1_dv, r5_dv = run_benchmark(emb_dinov2_batch, 'DINOv2-small cls+mean (768d)')

print('\n' + '=' * 50)
print('RESULTADO FINAL')
print('=' * 50)
print(f'  MobileCLIP-S0: recall@1={r1_mc:.4f} | recall@5={r5_mc:.4f}')
print(f'  DINOv2-small:  recall@1={r1_dv:.4f} | recall@5={r5_dv:.4f}')
vencedor = 'MobileCLIP-S0' if r1_mc > r1_dv else 'DINOv2-small'
print(f'  → Vencedor recall@1: {vencedor}')
