"""comparar_segmentacao.py — P3.34: mede recall de matching por foto p/ várias
estratégias de segmentação (na réplica fiel debug_segmentacao). Roda nas fotos
multi-carta da base rotulada e compara:
  - baseline  = detect_quads_adaptive (atual)
  - sem_borda = global mas SEM descartar contornos na borda (remove o 'continue')
  - clahe     = mesmo global, mas com CLAHE antes (aumenta contraste no fundo preto)
Métrica: fração de cartas-label únicas cujo top-1 (margem>=.03) acerta.
"""
import sys, glob, json
from pathlib import Path
import cv2, numpy as np, math
import copy

sys.path.insert(0, 'experiments')
import debug_segmentacao as DS

BASE = Path(__file__).resolve().parent.parent
LABELS = json.loads((BASE/'experiments'/'base_labels.json').read_text(encoding='utf-8'))


def _coletar_sem_borda(mask, min_area, scale, cols, rows, quads):
    cnts,_ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in cnts:
        area = cv2.contourArea(cnt)
        if area < min_area: continue
        peri = cv2.arcLength(cnt, True)
        quad=None
        for eps in DS.EPS_LIST:
            approx=cv2.approxPolyDP(cnt,eps*peri,True)
            if len(approx)==4:
                pts=[(approx[p][0][0]/scale,approx[p][0][1]/scale) for p in range(4)]
                o=DS.order_points(pts); r=DS.aspect_ratio(o)
                if DS.RATIO_MIN<=r<=DS.RATIO_MAX: quad=o; break
        if quad is None:
            try:
                rrect=cv2.minAreaRect(cnt); (cx,cy),(rw,rh),ang=rrect
                th=math.radians(ang); cs,sn=math.cos(th),math.sin(th)
                pts=[]
                for ox,oy in [(-rw/2,-rh/2),(rw/2,-rh/2),(rw/2,rh/2),(-rw/2,rh/2)]:
                    pts.append(((cx+ox*cs-oy*sn)/scale,(cx+ox*sn+oy*cs)/scale))
                o=DS.order_points(pts)
                if DS.RATIO_MIN<=DS.aspect_ratio(o)<=DS.RATIO_MAX: quad=o
            except Exception: pass
        if quad is not None: quads.append({'pts':quad,'area':area})

def _dedup(quads, w, h, maxq=15):
    diag=math.hypot(w,h); dedup=[]
    for q in quads:
        cx=sum(p[0] for p in q['pts'])/4; cy=sum(p[1] for p in q['pts'])/4
        hit=-1
        for j,dq in enumerate(dedup):
            dx=sum(p[0] for p in dq['pts'])/4; dy=sum(p[1] for p in dq['pts'])/4
            if math.hypot(dx-cx,dy-cy)<DS.DEDUP_FRAC*diag: hit=j; break
        if hit==-1: dedup.append(q)
        elif q['area']>dedup[hit]['area']: dedup[hit]=q
    return sorted(dedup,key=lambda q:-q['area'])[:maxq]


def detectar_variante(img, nome):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if nome == 'baseline':
        return DS.detect_quads_adaptive(img)
    if nome == 'sem_borda':
        h,w = img.shape[:2]; scale=min(1.0,1000/max(w,h))
        work=cv2.resize(img,(round(w*scale),round(h*scale))) if scale<1 else img.copy()
        c_,r_=work.shape[1],work.shape[0]; min_area=c_*r_*0.008
        kernel=cv2.getStructuringElement(cv2.MORPH_RECT,(3,3))
        g2=cv2.cvtColor(work,cv2.COLOR_BGR2GRAY); quads=[]
        for k,lo,hi in DS.PASSES:
            blur=cv2.GaussianBlur(g2,(k,k),0); edges=cv2.Canny(blur,lo,hi)
            edges=cv2.dilate(edges,kernel,iterations=2)
            _coletar_sem_borda(edges,min_area,scale,c_,r_,quads)
        mean=float(g2.mean()); ttype=cv2.THRESH_BINARY if mean<128 else cv2.THRESH_BINARY_INV
        _,mask=cv2.threshold(g2,0,255,ttype|cv2.THRESH_OTSU)
        mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,kernel,iterations=2)
        mask=cv2.dilate(mask,kernel,iterations=1)
        _coletar_sem_borda(mask,min_area,scale,c_,r_,quads)
        return _dedup(quads, w, h), {}
    if nome == 'clahe':
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        h,w = img.shape[:2]; scale=min(1.0,1000/max(w,h))
        work=cv2.resize(img,(round(w*scale),round(h*scale))) if scale<1 else img.copy()
        c_,r_=work.shape[1],work.shape[0]; min_area=c_*r_*0.008
        kernel=cv2.getStructuringElement(cv2.MORPH_RECT,(3,3))
        g2w=clahe.apply(cv2.cvtColor(work,cv2.COLOR_BGR2GRAY)); quads=[]
        for k,lo,hi in DS.PASSES:
            blur=cv2.GaussianBlur(g2w,(k,k),0); edges=cv2.Canny(blur,lo,hi)
            edges=cv2.dilate(edges,kernel,iterations=2)
            _coletar_sem_borda(edges,min_area,scale,c_,r_,quads)
        mean=float(g2w.mean()); ttype=cv2.THRESH_BINARY if mean<128 else cv2.THRESH_BINARY_INV
        _,mask=cv2.threshold(g2w,0,255,ttype|cv2.THRESH_OTSU)
        mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,kernel,iterations=2)
        mask=cv2.dilate(mask,kernel,iterations=1)
        _coletar_sem_borda(mask,min_area,scale,c_,r_,quads)
        return _dedup(quads, w, h), {}


def avaliar_foto(path, img, lab_tks, estrategia):
    quads,_ = detectar_variante(img, estrategia)
    ach = set()
    for quad in quads:
        pts = quad['pts'] if isinstance(quad,dict) and 'pts' in quad else quad
        warp = DS.warp_card(img, pts)
        if warp is None: continue
        nome, score, marg, idx = DS.match_crop(warp)[0]
        if marg is not None and marg >= 0.03 and DS.eh_acerto(nome, lab_tks):
            ach.add(DS.tok(nome))
    return ach


def main():
    DS._load_index()
    fotos = []
    for fname, info in LABELS.items():
        if len(info.get('cartas',[])) < 4: continue  # só multi-carta
        pat = glob.glob(str(BASE.parent/'pokescan-tcg-labels'/'**'/fname), recursive=True)
        if not pat: continue
        fotos.append((fname, pat[0], set(DS.tok(c['nome']) for c in info['cartas'])))
    est = ['baseline','sem_borda','clahe']
    res = {e: {'tot':0,'ach':0} for e in est}
    print(f'{len(fotos)} fotos multi-carta\n')
    for fname, path, lab in fotos:
        img = cv2.imread(path)
        linha = [fname.split('.')[0][4:]]
        for e in est:
            ach = avaliar_foto(path, img, lab, e)
            res[e]['tot'] += len(lab); res[e]['ach'] += len(ach)
            linha.append(f'{e}:{len(ach)}')
        print(' | '.join([fname] + [f'{es}={len(avaliar_foto(path,img,lab,es))}' for es in est]))
    print('\n===== AGRUPADO =====')
    for e in est:
        r=res[e]
        print(f'{e}: {r["ach"]}/{r["tot"]} = {r["ach"]/r["tot"]:.1%}')
    (BASE/'experiments'/'segmentacao_comparacao.json').write_text(
        json.dumps({e:{'tot':res[e]['tot'],'ach':res[e]['ach']} for e in est}), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()