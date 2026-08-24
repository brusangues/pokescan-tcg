"""debug_segmentacao.py — réplica FIEL do pipeline do scanner (cardClip.ts +
scannerEngine.ts) em Python/cv2, para debug visual e calibração de parâmetros
da segmentação SEM rebuild do site.

Réplica de cardClip.ts detectCardQuads():
- working canvas ~1000px maior lado
- 8 passadas Canny (ksize,low,high) + dilate 3x3 iter=2
- Fase 2-B: Otsu (direção pelo brilho médio) + close iter=2 + dilate iter=1
- _coletarQuads: RETR_EXTERNAL, area>=minArea(2%), não-tocar-borda,
  approxPolyDP eps 0.02..0.10 -> 4 pts -> orderPoints -> ratio 0.45..0.95;
  fallback minAreaRect
- dedup por centro (< 15% da diagonal da imagem ORIGINAL), maior área vence,
  max N quads por área

Match: mesmo preprocess/embed do build_search_index (dv_model_uint8.onnx,
cls+mean 768d) + projeção PCA (pca_bundle.bin) + cosseno contra index
(fp16) com máximo por carta (row_cards.bin).

Saídas por foto em experiments/debug_crops/<foto>/:
  overlay.jpg   — quads numerados na foto (verde=match na label, vermelho=não)
  crops/*.jpg   — cartas warpingadas 440x615 com borda colorida pelo status
  mask_otsu.jpg — máscara da fase B
Uso: python debug_segmentacao.py [--max-quads N] [--fotos nome1,nome2]
"""
import json, os, sys, unicodedata, math
from pathlib import Path
import numpy as np
import cv2
import onnxruntime as ort
from PIL import Image

BASE = Path(__file__).resolve().parent.parent
LABELS_DIR = Path(r'C:\Projects\pokescan-tcg-labels')
BASE_JSON = BASE / 'experiments' / 'base_labels.json'
OUTDIR = BASE / 'experiments' / 'debug_crops'

MODEL = str(BASE / 'experiments' / 'models' / 'dv_model_uint8.onnx')
SC = BASE / 'data' / 'scanner'

# ───────────────────────── segmentação (réplica cardClip.ts) ─────────────────────────
PASSES = [(5,30,100),(5,50,150),(5,80,200),(7,50,150),(7,80,200),(9,50,150),(9,80,200),(9,100,220)]
MIN_AREA_FRAC = 0.02
RATIO_MIN, RATIO_MAX = 0.45, 0.95
DEDUP_FRAC = 0.15
EPS_LIST = [0.02,0.03,0.04,0.05,0.06,0.08,0.10]

def order_points(pts):
    pts = np.array(pts, dtype=np.float32)
    s = pts.sum(axis=1); d = (pts[:,1] - pts[:,0])
    i_s = np.argsort(s); i_d = np.argsort(d)
    return [tuple(pts[i_s[0]]), tuple(pts[i_d[0]]), tuple(pts[i_s[3]]), tuple(pts[i_d[3]])]

def aspect_ratio(o):
    (x0,y0),(x1,y1),(x2,y2),_ = o[0],o[1],o[2],o[3]
    l1 = math.hypot(x1-x0, y1-y0); l2 = math.hypot(x2-x1, y2-y1)
    return min(l1,l2)/max(l1,l2)

def coletar_quads(mask, min_area, scale, cols, rows, quads):
    cnts,_ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in cnts:
        area = cv2.contourArea(cnt)
        if area < min_area: continue
        x,y,w,h = cv2.boundingRect(cnt)
        if x<=2 or y<=2 or x+w>=cols-2 or y+h>=rows-2: continue
        peri = cv2.arcLength(cnt, True)
        quad=None
        for eps in EPS_LIST:
            approx = cv2.approxPolyDP(cnt, eps*peri, True)
            if len(approx)==4:
                pts=[(approx[p][0][0]/scale, approx[p][0][1]/scale) for p in range(4)]
                o=order_points(pts)
                r=aspect_ratio(o)
                if RATIO_MIN<=r<=RATIO_MAX: quad=o; break
        if quad is None:
            try:
                rrect=cv2.minAreaRect(cnt)
                (cx,cy),(rw,rh),ang=rrect
                th=math.radians(ang); cs,sn=math.cos(th),math.sin(th)
                pts=[]
                for ox,oy in [(-rw/2,-rh/2),(rw/2,-rh/2),(rw/2,rh/2),(-rw/2,rh/2)]:
                    pts.append(((cx+ox*cs-oy*sn)/scale,(cy+ox*sn+oy*cs)/scale))
                o=order_points(pts)
                if RATIO_MIN<=aspect_ratio(o)<=RATIO_MAX: quad=o
            except Exception: pass
        if quad: quads.append({'pts':quad,'area':area/(scale*scale)})
    return quads

def detect_quads(img_bgr, max_quads=10, params=None):
    """params: dict opcional p/ sweep: min_area_frac, passes, dedup_frac, otsu(bool)"""
    P = params or {}
    passes = P.get('passes', PASSES)
    min_frac = P.get('min_area_frac', MIN_AREA_FRAC)
    use_otsu = P.get('otsu', True)
    h,w = img_bgr.shape[:2]
    scale = min(1.0, 1000/max(w,h))
    work = cv2.resize(img_bgr,(round(w*scale),round(h*scale))) if scale<1 else img_bgr.copy()
    cols,rows = work.shape[1], work.shape[0]
    min_area = cols*rows*min_frac
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT,(3,3))
    gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
    quads=[]
    dbg = {}
    for i,(k,lo,hi) in enumerate(passes):
        blur = cv2.GaussianBlur(gray,(k,k),0)
        edges = cv2.Canny(blur, lo, hi)
        edges = cv2.dilate(edges, kernel, iterations=2)
        coletar_quads(edges, min_area, scale, cols, rows, quads)
        if i==1: dbg['canny_p2']=edges
    if use_otsu:
        mean = float(gray.mean())
        ttype = cv2.THRESH_BINARY if mean<128 else cv2.THRESH_BINARY_INV
        _,mask = cv2.threshold(gray,0,255,ttype|cv2.THRESH_OTSU)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.dilate(mask, kernel, iterations=1)
        coletar_quads(mask, min_area, scale, cols, rows, quads)
        dbg['mask_otsu']=mask
    # dedup por centro (coords originais)
    diag = math.hypot(w,h)
    dedup=[]
    for q in quads:
        cx=sum(p[0] for p in q['pts'])/4; cy=sum(p[1] for p in q['pts'])/4
        hit=-1
        for j,dq in enumerate(dedup):
            dx=sum(p[0] for p in dq['pts'])/4; dy=sum(p[1] for p in dq['pts'])/4
            if math.hypot(dx-cx,dy-cy)<DEDUP_FRAC*diag: hit=j;break
        if hit==-1: dedup.append(q)
        elif q['area']>dedup[hit]['area']: dedup[hit]=q
    return sorted(dedup,key=lambda q:-q['area'])[:max_quads], dbg

def dedup_global(quads, w, h):
    diag = math.hypot(w,h); out=[]
    for q in quads:
        cx=sum(p[0] for p in q['pts'])/4; cy=sum(p[1] for p in q['pts'])/4
        hit=-1
        for j,dq in enumerate(out):
            dx=sum(p[0] for p in dq['pts'])/4; dy=sum(p[1] for p in dq['pts'])/4
            if math.hypot(dx-cx,dy-cy) < DEDUP_FRAC*diag: hit=j; break
        if hit==-1: out.append(q)
        elif q['area']>out[hit]['area']: out[hit]=q
    return sorted(out, key=lambda q:-q['area'])

def detect_quads_adaptive(img_bgr, max_quads=10):
    """Adaptativo: detecta com minArea .02 (solitária/sem falso). Se achar MUITOS
    (>=4 → multi-carta densa), re-detecta com .008 e une (recupera cartas pequenas
    de mesa que .02 perdeu), com dedup global único."""
    q2,dbg2 = detect_quads(img_bgr, max_quads=max_quads, params={'min_area_frac':0.02})
    if len(q2) < 4:
        return q2, dbg2
    q8,_ = detect_quads(img_bgr, max_quads=max_quads, params={'min_area_frac':0.008})
    h,w = img_bgr.shape[:2]
    return dedup_global(q2+q8, w, h)[:max_quads], dbg2

def warp_card(img_bgr, quad):
    outW,outH=440, round(440*88/63)
    src=np.float32([quad[0],quad[1],quad[3],quad[2]])
    dst=np.float32([[0,0],[outW-1,0],[0,outH-1],[outW-1,outH-1]])
    M=cv2.getPerspectiveTransform(src,dst)
    return cv2.warpPerspective(img_bgr,M,(outW,outH),borderMode=cv2.BORDER_CONSTANT,borderValue=(255,255,255))

# ───────────────────────── match (réplica scannerEngine.ts) ─────────────────────────
_sess=None; _idx=None; _rc=None; _pca_mean=None; _comps=None; _cards=None

def _load_index():
    global _sess,_idx,_rc,_pca_mean,_comps,_cards
    if _idx is not None: return
    _sess = ort.InferenceSession(MODEL, providers=['CPUExecutionProvider'])
    u16=np.fromfile(SC/'index_pca128_fp16.bin',dtype=np.uint16)
    _idx=u16.view(np.float16).astype(np.float32).reshape(-1,128)
    _rc=np.fromfile(SC/'row_cards.bin',dtype=np.uint16)
    pca=np.fromfile(SC/'pca_bundle.bin',dtype=np.float32)
    _pca_mean=pca[:768]; _comps=pca[768:].reshape(128,768)
    _cards=json.loads((SC/'cards.json').read_text(encoding='utf-8'))

def _preprocess(bgr):
    im=Image.fromarray(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB))
    w,h=im.size; s=256/min(w,h)
    im=im.resize((round(w*s),round(h*s)),Image.BICUBIC)
    ww,hh=im.size; l,t=(ww-224)//2,(hh-224)//2
    im=im.crop((l,t,l+224,t+224))
    x=np.asarray(im,dtype=np.float32)/255.0
    m=np.array([0.485,0.456,0.406],dtype=np.float32).reshape(3,1,1)
    sd=np.array([0.229,0.224,0.225],dtype=np.float32).reshape(3,1,1)
    return ((x.transpose(2,0,1)-m)/sd)[None]

def match_crop(bgr,topk=5):
    """Retorna [(nome, score, margin12, card_idx)] top-k."""
    _load_index()
    x=_preprocess(bgr)
    hs=_sess.run(None,{'pixel_values':x})[0][0]
    v=np.concatenate([hs[0],hs[1:].mean(axis=0)]).astype(np.float32)
    p=_comps@(v-_pca_mean)
    n=np.linalg.norm(p) or 1.0
    q=p/n
    s=_idx@q
    s=np.clip(s,0,1)
    best=np.full(len(_cards),-np.inf,dtype=np.float32)
    np.maximum.at(best,_rc,s)
    order=np.argsort(-best)[:topk]
    out=[]
    for rank,i in enumerate(order):
        out.append((_cards[int(i)]['n'],float(best[int(i)]),
                    float(best[order[0]]-best[order[1]]) if rank==0 and len(order)>1 else None,int(i)))
    return out

# ───────────────────────── avaliação vs labels ─────────────────────────
def tok(s):
    t=unicodedata.normalize('NFD',s or '').encode('ascii','ignore').decode().lower()
    t=re.sub(r'[^a-z0-9]',' ',t).split()
    return t[0] if t else ''
import re
TRAD={'juiz':'judge','lilian':'lillie','energia':'fire','fragmento':'mysterious'}
def eh_acerto(nome_match, label_tokens):
    mt=tok(nome_match)
    if mt in label_tokens: return True
    for lt in label_tokens:
        if TRAD.get(lt,'')==mt: return True
    return False

# ───────────────────────── main ─────────────────────────
def localiza(arq):
    for r in (LABELS_DIR/'done', LABELS_DIR):
        p=r/arq
        if p.exists(): return p
    return None

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument('--fotos',default='')
    ap.add_argument('--max-quads',type=int,default=10)
    ap.add_argument('--min-area',type=float,default=0.02)
    ap.add_argument('--dedup',type=float,default=0.15)
    ap.add_argument('--adaptive',action='store_true')
    args=ap.parse_args()
    params={'min_area_frac':args.min_area,'dedup_frac':args.dedup}
    base=json.loads(BASE_JSON.read_text(encoding='utf-8'))
    alvos=[f for f,v in base.items() if v['cartas']]
    if args.fotos: alvos=[f for f in alvos if f in args.fotos.split(',')]
    OUTDIR.mkdir(exist_ok=True)
    tot_lab=tot_hit=0
    resumo={}
    for foto in alvos:
        path=localiza(foto)
        if not path: print('sem arquivo',foto); continue
        d=out=OUTDIR/foto.replace('.jpg',''); d.mkdir(exist_ok=True)
        img=cv2.imread(str(path))
        if args.adaptive:
            quads,dbg=detect_quads_adaptive(img,max_quads=args.max_quads)
        else:
            quads,dbg=detect_quads(img,max_quads=args.max_quads,params=params)
        lab_tokens=list(dict.fromkeys(tok(c['nome']) for c in base[foto]['cartas']))
        ov=img.copy()
        hits=set(); linhas=[]
        for i,q in enumerate(quads,1):
            warp=warp_card(img,q['pts'])
            nome,score,marg,idx=match_crop(warp)[0]
            ok=eh_acerto(nome,set(lab_tokens)) and marg is not None and marg>=0.03
            if eh_acerto(nome,set(lab_tokens)): hits.add(tok(nome))
            cor=(0,180,0) if ok else ((0,165,255) if eh_acerto(nome,set(lab_tokens)) else (0,0,230))
            cv2.polylines(ov,[np.array([[int(x),int(y)] for x,y in q['pts']])],True,cor,14)
            cv2.putText(ov,f'{i}',(int(q["pts"][0][0]),int(q["pts"][0][1])-8),
                        cv2.FONT_HERSHEY_SIMPLEX,4,(0,0,0),10)
            cv2.putText(ov,f'{i}',(int(q["pts"][0][0]),int(q["pts"][0][1])-8),
                        cv2.FONT_HERSHEY_SIMPLEX,3.4,(255,255,255),6)
            w2=cv2.resize(warp,(146,204))
            b=8
            w2[:b]=cor;w2[-b:]=cor;w2[:,:b]=cor;w2[:,-b:]=cor
            cv2.imwrite(str(d/f'crop_{i:02d}.jpg'),warp)
            linhas.append(f'{i:02d} {nome[:26]:26s} {score*100:5.1f}% marg={"-" if marg is None else format(marg*100,".1f")} {"OK" if ok else ("amb" if eh_acerto(nome,set(lab_tokens)) else "ERRO")}')
        cv2.imwrite(str(d/'overlay.jpg'),ov)
        if 'mask_otsu' in dbg: cv2.imwrite(str(d/'mask_otsu.jpg'),dbg['mask_otsu'])
        if 'canny_p2' in dbg: cv2.imwrite(str(d/'canny_p2.jpg'),dbg['canny_p2'])
        faltas=[t for t in lab_tokens if t not in hits]
        tot_lab+=len(set(lab_tokens)); tot_hit+=len(hits & set(lab_tokens))
        resumo[foto]={'quads':len(quads),'labels':lab_tokens,'hits':sorted(hits),'faltas':faltas}
        print(f'\n=== {foto}: {len(quads)} quads | labels {len(set(lab_tokens))} | acertos {len(hits&set(lab_tokens))} | faltas={faltas}')
        for l in linhas: print('   ',l)
    print(f'\n########## TOTAL: acertos {tot_hit}/{tot_lab} ({100*tot_hit/max(tot_lab,1):.0f}%) ##########')
    (OUTDIR/'resumo.json').write_text(json.dumps(resumo,ensure_ascii=False,indent=1),encoding='utf-8')

if __name__=='__main__':
    main()