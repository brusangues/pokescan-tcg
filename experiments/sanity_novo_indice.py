"""sanity_novo_indice.py — valida o índice reconstruído com as cartas da Liga.

Confere: (1) as novas cartas liga_only estão em cards.json; (2) self-match
(embed da imagem oficial -> top-1 == próprio id) para uma amostra das novas.
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
n = len(cards)
print('cards.json total:', n)
# contagem das novas (id com hifen set natureza {idE}-{num}, ex. 246-14)
novas = [c for c in cards if '-' in str(c.get('id','')) and not str(c.get('id','')).startswith(('base','sv','swsh','sm','xy','ex','bw','hgss','dp','pl','col','mcd','pop','det','pkm','prc','smp','sis' 'clv','blw','xyp','m','neo'))]
print('amostra de novas (id de numero):', len(novas))

# carrega índice e matriz de self-match
u16 = np.fromfile(SC/'index_pca128_fp16.bin', dtype=np.uint16)
idx = u16.view(np.float16).astype(np.float32).reshape(-1, 128)
pca = np.fromfile(SC/'pca_bundle.bin', dtype=np.float32)
pca_mean = pca[:768]; comps = pca[768:].reshape(128,768)
sess = ort.InferenceSession(str(BASE/'experiments'/'models'/'dv_model_uint8.onnx'), providers=['CPUExecutionProvider'])
row_cards = np.fromfile(SC/'row_cards.bin', dtype=np.uint16)

def top1(card):
    p = BASE/'data'/'img_cache'/f"{card['id']}.png"
    if not p.exists(): return None, 'sem_img'
    x = preprocess(p)
    hs = sess.run(None, {'pixel_values':x})[0][0]
    v = np.concatenate([hs[0], hs[1:].mean(axis=0)]).astype(np.float32)
    proj = comps @ (v - pca_mean)
    q = proj/(np.linalg.norm(proj) or 1.0)
    cos = (idx @ q)
    # dedup por card: para cada linha, atribui o cosseno; pega max por card
    # vetorizado: agrega max por row_cards
    best = np.zeros(n)
    np.maximum.at(best, row_cards, cos)
    order = int(np.argmax(best))
    return best[order], order

# testa algumas novas
test_ids = ['246-14','344-98','440-328','732-52','742-662']
import os
print('\nself-match (novas, devem dar top1==id e cosseno~0.95+):')
for cid in test_ids:
    card = next((c for c in cards if str(c.get('id'))==cid), None)
    if not card:
        print(f'  {cid}: NAO ESTA no novo cards.json')
        continue
    cos, top = top1(card)
    if top is None or isinstance(top, str):
        print(f'  {cid}: sem img')
        continue
    top_card = cards[top] if top < n else None
    tid = str(top_card.get('id')) if top_card else '?'
    ok = tid == cid
    print(f'  {cid}: top1={tid} cosseno={cos:.3f} {"✅" if ok else "❌"}')