"""
Gera o índice de busca do scanner no espaço do DINOv2-small q4f16 ONNX
(mesmo engine do browser — consistência por construção).

Saídas em data/scanner/:
- embeddings_raw.npy    (N x 768, float32) — cls+mean
- pca32.bin             (32 x 768, float32) — matriz PCA (aplicada no browser)
- index_pca32.bin       (N x 32, float32)   — índice pronto p/ dot product
- cards.json            (metadados: id, name, set, imagem, preços)
- pca_stats.npy         (mean, components, explained_variance — p/ aplicar no browser)
"""
import sys, json, time
from pathlib import Path
import numpy as np
from PIL import Image
import onnxruntime as ort

BASE = Path(__file__).resolve().parent.parent
IMG_CACHE = BASE / 'data' / 'img_cache'
OUT = BASE / 'data' / 'scanner'
OUT.mkdir(parents=True, exist_ok=True)

MODEL = str(BASE / 'experiments' / 'models' / 'dv_model_uint8.onnx')
BATCH = 64
N_COMP = 32

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

sess = ort.InferenceSession(MODEL, providers=['CPUExecutionProvider'])

# 1. Lista cartas com imagem
cards = json.loads((BASE / 'data' / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
com_img = [c for c in cards if (IMG_CACHE / f'{c["id"]}.png').exists()]
print(f'Cartas com imagem: {len(com_img)}')

# 2. Extrai embeddings em batch (pula se já extraiu)
RAW_PATH = OUT / 'embeddings_raw.npy'
if RAW_PATH.exists():
    raw = np.load(RAW_PATH)
    print(f'embeddings_raw.npy já existe — carregado: {raw.shape}')
else:
    t0 = time.time()
    embs = []
    for i in range(0, len(com_img), BATCH):
        chunk = com_img[i:i+BATCH]
        xs = np.concatenate([preprocess(Image.open(IMG_CACHE/f'{c["id"]}.png').convert('RGB')) for c in chunk])
        hs = sess.run(None, {'pixel_values': xs})[0]  # B,257,384
        cls = hs[:, 0]
        mean = hs[:, 1:].mean(axis=1)
        v = np.concatenate([cls, mean], axis=1)  # B,768
        embs.append(v)
        if (i // BATCH) % 20 == 0:
            print(f'  {i+len(chunk)}/{len(com_img)} ({time.time()-t0:.0f}s)', flush=True)

    raw = np.concatenate(embs).astype(np.float32)
    print(f'Extração: {raw.shape} em {time.time()-t0:.0f}s')

# 3. PCA (128 comps — joelho da curva recall×tamanho)
# whiten=True é o melhor (96.3% vs 88.9% sem) — equaliza a escala dos
# componentes. Para o browser: guardamos components pré-escaladas
# (comps / sqrt(ev)) para que vp = comps_scaled @ (v - mean) reproduza
# exatamente o pca.transform do sklearn (mesmo espaço do índice).
from sklearn.decomposition import PCA
t0 = time.time()
N_COMP = 128
pca = PCA(n_components=N_COMP, whiten=True)
reduced = pca.fit_transform(raw).astype(np.float32)
print(f'PCA: {reduced.shape} em {time.time()-t0:.0f}s | variância explicada: {pca.explained_variance_ratio_.sum():.4f}')

# 4. Salva (fp32 e fp16) — índice SEMPRE L2-normalizado (dot product = cosseno)
np.save(OUT / 'embeddings_raw.npy', raw)
norms = np.linalg.norm(reduced, axis=1, keepdims=True) + 1e-9
reduced_n = (reduced / norms).astype(np.float32)
reduced_n.tofile(OUT / 'index_pca128_fp32.bin')
reduced_n.astype(np.float16).tofile(OUT / 'index_pca128_fp16.bin')
pca.components_.astype(np.float32).tofile(OUT / 'pca128.bin')
# components pré-escaladas p/ whitening — o que o browser aplica:
# vp = comps_scaled @ (v - mean), reproduzindo pca.transform exato.
comps_scaled = (pca.components_ / np.sqrt(pca.explained_variance_)[:, None]).astype(np.float32)
comps_scaled.tofile(OUT / 'pca128_whitened.bin')
np.save(OUT / 'pca128_stats.npy', {
    'mean': pca.mean_.astype(np.float32),
    'components': pca.components_.astype(np.float32),
    'components_whitened': comps_scaled,
    'explained_variance_ratio': pca.explained_variance_ratio_.astype(np.float32),
})
ids = [c['id'] for c in com_img]
with open(OUT / 'ids.json', 'w', encoding='utf-8') as f:
    json.dump(ids, f)

# 5. Metadados compactos (id, nome, set, número, raridade, preço, imagem)
meta = []
for c in com_img:
    prices = c.get('tcgplayer') or {}
    price = (prices.get('prices') or {}).get('market') if isinstance(prices, dict) else None
    meta.append({
        'id': c['id'],
        'n': c.get('name', ''),
        's': c['set']['id'],
        'sn': c['set']['name'],
        'num': c.get('number', ''),
        'r': c.get('rarity', ''),
        'p': round(price, 2) if isinstance(price, (int, float)) else None,
        'img': (c.get('images') or {}).get('small', ''),
    })
with open(OUT / 'cards.json', 'w', encoding='utf-8') as f:
    json.dump(meta, f, ensure_ascii=False)

# 6. Bundle PCA para o browser: [mean(768) | comps_whitened(128x768)] fp32
with open(OUT / 'pca_bundle.bin', 'wb') as f:
    pca.mean_.astype(np.float32).tofile(f)
    comps_scaled.tofile(f)

print('\n✅ Índice gerado:')
for p in ['embeddings_raw.npy', 'index_pca128_fp32.bin', 'index_pca128_fp16.bin',
          'pca128.bin', 'pca128_stats.npy', 'ids.json', 'cards.json']:
    fp = OUT / p
    print(f'  {p:24s} {fp.stat().st_size/1e6:8.1f} MB')
