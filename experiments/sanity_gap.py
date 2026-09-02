"""sanity_gap.py — valida a metodologia do gap_indice_embedding.

Pega cartas que JÁ estão no índice (cards.json), recalcula o embedding da
imagem delas (mesmo pipeline) e confere o cosseno máximo contra o índice.
Se a carta está no índice, o cosseno deve ser ~0.95+ (self-match). Se der
baixo, a projeção PCA está errada → os resultados de 'gap' são inválidos.
"""
import json, numpy as np, onnxruntime as ort
from pathlib import Path
from PIL import Image

BASE = Path(__file__).resolve().parent.parent
SC = BASE/'data'/'scanner'

def preprocess(path):
    im = Image.open(path).convert('RGB')
    w,h = im.size; s = 256/min(w,h)
    im = im.resize((round(w*s), round(h*s)), Image.BICUBIC)
    ww,hh = im.size; l,t = (ww-224)//2,(hh-224)//2
    im = im.crop((l,t,l+224,t+224))
    x = np.asarray(im,dtype=np.float32)/255.0
    m = np.array([0.485,0.456,0.406],dtype=np.float32).reshape(3,1,1)
    sd = np.array([0.229,0.224,0.225],dtype=np.float32).reshape(3,1,1)
    return ((x.transpose(2,0,1)-m)/sd)[None]

cards = json.loads((SC/'cards.json').read_text(encoding='utf-8'))
u16 = np.fromfile(SC/'index_pca128_fp16.bin', dtype=np.uint16)
idx = u16.view(np.float16).astype(np.float32).reshape(-1,128)
pca = np.fromfile(SC/'pca_bundle.bin', dtype=np.float32)
pca_mean = pca[:768]; comps = pca[768:].reshape(128,768)
sess = ort.InferenceSession(str(BASE/'experiments'/'models'/'dv_model_uint8.onnx'), providers=['CPUExecutionProvider'])

def cosseno_card(card):
    p = BASE/'data'/'img_cache'/f"{card['id']}.png"
    if not p.exists():
        return None, 'sem_img'
    x = preprocess(p)
    hs = sess.run(None, {'pixel_values':x})[0][0]
    v = np.concatenate([hs[0], hs[1:].mean(axis=0)]).astype(np.float32)
    proj = comps @ (v - pca_mean)
    q = proj/(np.linalg.norm(proj) or 1.0)
    cos = (idx @ q)
    # dedup por card: max por card = max sobre as 3 variantes
    return float(cos.max()), float(cos.max())

# testa 8 cartas no índice
print('sanity checks — cartas JÁ no índice (self-match deve ser ~0.95+):')
good = 0; tested = 0
for card in cards[:40]:
    cos, _ = cosseno_card(card)
    if cos is None: continue
    tested += 1
    if cos >= 0.90: good += 1
    if tested <= 6:
        print(f'  {card["id"]}: cosseno máximo = {cos:.3f}')
print(f'\nresumo: {good}/{tested} cartas do índice com cosseno>=0.90 (self-match)')
print('se a taxa for alta → metodologia OK; se baixa → projeção PCA errada')