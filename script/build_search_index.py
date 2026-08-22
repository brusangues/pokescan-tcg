"""
Gera o índice de busca do scanner no espaço do DINOv2-small q4f16 ONNX
(mesmo engine do browser — consistência por construção).

AUGMENTAÇÃO (3x): além da imagem oficial de cada carta, adiciona ao índice
embedding de VARIANTES determinísticas (rotação leve + perspectiva leve),
geradas SOMENTE a partir da imagem oficial salva — NUNCA de fotos da base.
Várias linhas/carta, mesmo card_id; busca = MÁXIMO por carta (row_cards).

CARTAS EXTRAS (MEP pt-BR): anexa as cartas da "Coleção Ilustração Parceiro
Inicial" (data/mep_cards/mep_extra.json) ao final do índice, isoladas do
catálogo de preços. Cache INCREMENTAL: se embeddings_raw/aug já existem,
extrai só as cartas novas anexadas (as existentes não são reprocessadas).

Saídas em data/scanner/:
- embeddings_raw.npy (N x 768), embeddings_aug_raw.npy (N*K x 768) [cache]
- index_pca128_fp32.bin (N*K x 128), index_pca128_fp16.bin (idem fp16)
- row_cards.npy/.bin, pca128_stats.npy, pca_bundle.bin, ids.json, cards.json
"""
import sys, json, time
from pathlib import Path
import numpy as np
from PIL import Image
import cv2
import onnxruntime as ort

BASE = Path(__file__).resolve().parent.parent
IMG_CACHE = BASE / 'data' / 'img_cache'
MEP_DIR = BASE / 'data' / 'mep_cards'
OUT = BASE / 'data' / 'scanner'
OUT.mkdir(parents=True, exist_ok=True)

MODEL = str(BASE / 'experiments' / 'models' / 'dv_model_uint8.onnx')
BATCH = 32
N_COMP = 128

VARIANTS = ['rot_2', 'persp2']   # + base = 3 cópias por carta
STRIDE_AUG = len(VARIANTS) + 1   # 3

def var_img(img, name):
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
    hs = sess.run(None, {'pixel_values': xs})[0]
    cls = hs[:, 0]; mean = hs[:, 1:].mean(axis=1)
    return np.concatenate([cls, mean], axis=1).astype(np.float32)

# ── 0. Cartas: catálogo EN + coleções pt-BR da LIGA (fonte primária pt-BR) ──
cards = json.loads((BASE / 'data' / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
com_img = [c for c in cards if (IMG_CACHE / f'{c["id"]}.png').exists()]

# Coleções pt-BR exclusivas: nomes (nPT) e números (sN) vêm da LIGA via
# data/liga/set_{idE}.json (config data/liga/ptbr_edicoes.json). Imagem local em
# data/mep_cards/{mask}; cartas sem imagem são puladas (pendentes de download).
PTBR_CFG = BASE / 'data' / 'liga' / 'ptbr_edicoes.json'
n_ptbr = 0
if PTBR_CFG.exists():
    cfg = json.loads(PTBR_CFG.read_text(encoding='utf-8'))
    img_dir = BASE / cfg.get('imagens_dir', 'data/mep_cards')
    for idE, meta in cfg.get('edicoes', {}).items():
        set_path = BASE / 'data' / 'liga' / f'set_{idE}.json'
        if not set_path.exists():
            print(f'  ⚠ pt-BR edição {idE} ({meta.get("sigla")}): set_{idE}.json não existe')
            continue
        for carta in json.loads(set_path.read_text(encoding='utf-8')):
            sN = carta.get('sN')
            if not (isinstance(sN, str) and sN.isdigit()):
                continue  # pula variantes Staff/promo (ex: "001b")
            num = str(int(sN))
            mask = meta.get('imagem_mask')
            local = img_dir / mask.format(num=num) if mask else None
            if local is None or not local.exists():
                continue  # sem imagem local = não dá p/ embedding (pending download)
            com_img.append({
                'id': f'{idE}-{num}',
                'name': (carta.get('nPT') or '').strip() or carta.get('nEN', '').split('(')[0].strip(),
                'number': num,
                'rarity': 'Promocional', 'supertype': 'Pokémon',
                'subtypes': ['Promotional'],
                'set': {'id': (meta.get('sigla') or '').lower(), 'name': meta.get('nome', meta.get('sigla', ''))},
                'tcgplayer': None,
                'images': {'small': (f"https://www.pokemon.com/static-assets/content-assets/cms2-pt-br/img/cards/full/MEP/MEP_PT-BR_{num}.png"
                                     if 'MEP_PT-BR' in (mask or '') else carta.get('sP', ''))},
                '_local_img': str(local),
            })
            n_ptbr += 1
print(f'Cartas totais: {len(com_img)} (catálogo {len(com_img)-n_ptbr} + pt-BR da Liga {n_ptbr})')

def open_img(card):
    if '_local_img' in card:
        return Image.open(card['_local_img']).convert('RGB')
    return Image.open(IMG_CACHE / f'{card["id"]}.png').convert('RGB')

# ── 1. Embeddings ORIGINAIS (cache incremental) ──
RAW_PATH = OUT / 'embeddings_raw.npy'
raw = None
if RAW_PATH.exists():
    raw = np.load(RAW_PATH)
    if raw.shape[0] > len(com_img):   # catálogo encolheu? descarta
        raw = None
if raw is None:
    t0 = time.time(); rows = []
    for i in range(0, len(com_img), BATCH):
        rows.append(embed_batch([open_img(c) for c in com_img[i:i+BATCH]]))
        if (i//BATCH) % 20 == 0: print(f'  orig {i+min(BATCH,len(com_img))}/{len(com_img)} ({time.time()-t0:.0f}s)', flush=True)
    raw = np.concatenate(rows); np.save(RAW_PATH, raw)
    print(f'Extração original (novo): {raw.shape}')
elif raw.shape[0] < len(com_img):
    t0 = time.time()
    novos = com_img[raw.shape[0]:]
    rows = [embed_batch([open_img(c) for c in novos[i:i+BATCH]]) for i in range(0, len(novos), BATCH)]
    raw = np.concatenate([raw] + rows)
    np.save(RAW_PATH, raw)
    print(f'Originais INCREMENTAIS: +{len(novos)} -> {raw.shape} em {time.time()-t0:.0f}s')
else:
    print(f'embeddings_raw.npy já atual: {raw.shape}')

# ── 2. PCA fit (conjunto completo) ──
from sklearn.decomposition import PCA
pca = PCA(n_components=N_COMP, whiten=True)
_ = pca.fit_transform(raw)
print(f'PCA fit ok — variância: {pca.explained_variance_ratio_.sum():.4f}')

# ── 3. Embeddings das VARIANTES (cache incremental) ──
AUG_PATH = OUT / 'embeddings_aug_raw.npy'
def build_aug_slice(cs):
    rows = []
    for i in range(0, len(cs), BATCH):
        vs = []
        for c in cs[i:i+BATCH]:
            base = open_img(c)
            vs += [base, *[var_img(base, v) for v in VARIANTS]]
        rows.append(embed_batch(vs))
    return np.concatenate(rows)

aug = None
if AUG_PATH.exists():
    aug = np.load(AUG_PATH)
if aug is None or aug.shape[0] != (len(com_img) * STRIDE_AUG):
    t0 = time.time()
    target = len(com_img) * STRIDE_AUG
    if aug is not None and aug.shape[0] < target:
        # anexa variantes das cartas novas
        n_old_cards = aug.shape[0] // STRIDE_AUG
        novos = com_img[n_old_cards:]
        chunk = build_aug_slice(novos)
        aug = np.concatenate([aug, chunk])
        print(f'Variantes INCREMENTAIS: +{novos.__len__()} cartas -> {aug.shape} em {time.time()-t0:.0f}s')
    else:
        t0 = time.time()
        aug = build_aug_slice(com_img)
        print(f'Extras variantes (novo): {aug.shape} em {time.time()-t0:.0f}s')
    np.save(AUG_PATH, aug)
else:
    print(f'embeddings_aug_raw.npy já atual: {aug.shape}')

# ── 4. Montagem do índice aumentado (base + variantes, agrupado por carta) ──
all_raw = []
for i in range(len(com_img)):
    all_raw.append(raw[i])
    for v in range(1, STRIDE_AUG):
        all_raw.append(aug[i*STRIDE_AUG + v])
full = np.stack(all_raw).astype(np.float32)
reduced = pca.transform(full).astype(np.float32)
print(f'Índice aumentado: {reduced.shape} ({(full.shape[0]/len(com_img)):.1f}x por carta)')

norms = np.linalg.norm(reduced, axis=1, keepdims=True) + 1e-9
reduced_n = (reduced / norms).astype(np.float32)
reduced_n.tofile(OUT / 'index_pca128_fp32.bin')
reduced_n.astype(np.float16).tofile(OUT / 'index_pca128_fp16.bin')

K = STRIDE_AUG
row_cards = np.repeat(np.arange(len(com_img), dtype=np.uint16), K)
np.save(OUT / 'row_cards.npy', row_cards)
row_cards.tofile(OUT / 'row_cards.bin')

comps_scaled = (pca.components_ / np.sqrt(pca.explained_variance_)[:, None]).astype(np.float32)
np.save(OUT / 'pca128_stats.npy', {
    'mean': pca.mean_.astype(np.float32), 'components': pca.components_.astype(np.float32),
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
          'pca_bundle.bin', 'row_cards.bin', 'cards.json']:
    fp = OUT / p
    print(f'  {p:26s} {fp.stat().st_size/1e6:8.1f} MB')
print(f'  cartas: {len(ids)} (catálogo {len(com_img)-n_ptbr} + pt-BR da Liga {n_ptbr})')
