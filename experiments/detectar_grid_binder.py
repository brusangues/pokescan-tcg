"""detectar_grid_binder.py — P3.34: grade do binder por BUSCA POR VALIDAÇÃO.

Em vez de detectar costuras (frágil com cartas escuras), testa as grades
naturais de binder NxM (ex. 1x1..4x4) e escolhe a que MAXIMIZA cartas grandes
encontradas: recorta cada célula da grade, roda detecção local com min_area
alto (0.12) → carta ocupa ~90% da célula; grade errada divide cartas em
fragmentos rejeitados. Retorna os quads pontuados nas coordenadas originais.

Invocações: python -u experiments/detectar_grid_binder.py <foto.jpg>.
"""
import sys, glob, argparse, math
import cv2, numpy as np
from pathlib import Path

sys.path.insert(0, 'experiments')
import debug_segmentacao as DS

GRADES = [(1,1),(1,2),(2,1),(2,2),(2,3),(3,2),(3,3),(2,4),(4,2),(3,4),(4,3),(4,4)]


def carta_na_celula(roi, min_frac=0.12):
    q,_ = DS.detect_quads(roi, max_quads=2, params={'min_area_frac':min_frac})
    if not q:
        q,_ = DS.detect_quads(roi, max_quads=2, params={'min_area_frac':min_frac*0.5})
    return q


def tentar_grade(img, N, M, min_frac=0.12):
    W,H = img.shape[1], img.shape[0]
    xs = np.linspace(0, W, N+1)
    ys = np.linspace(0, H, M+1)
    quads=[]; 
    for i in range(N):
        for j in range(M):
            x0,x1 = int(xs[i]), int(xs[i+1]); y0,y1=int(ys[j]),int(ys[j+1])
            if x1-x0<80 or y1-y0<80: continue
            roi = img[y0:y1, x0:x1]
            q = carta_na_celula(roi, min_frac)
            for quad in q:
                pts=[(float(p[0])+x0, float(p[1])+y0) for p in quad['pts']]
                area = quad.get('area',0)
                # pontua cartas por área razoável (frac da célula ~0.3-0.4 a 0.85)
                frac = area/max(1.0,(x1-x0)*(y1-y0))
                quads.append({'pts':pts,'area':area,'frac':frac,'cel':(i,j)})
    return quads


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('foto')
    ap.add_argument('--min-frac',type=float,default=0.12)
    ap.add_argument('--thr-frac',type=float,default=0.25)  # frac mínima p/ contar carta
    a=ap.parse_args()
    img=cv2.imread(a.foto)
    if img is None: print('foto invalida'); return
    W,H=img.shape[1],img.shape[0]
    # baseline p/ comparação
    qb,_=DS.detect_quads_adaptive(img)
    ncarta_baseline=sum(1 for q in qb if q.get('area',0)/(W*H)>=0.08)
    print(f'{Path(a.foto).name}: {W}x{H} | baseline cartas(grande): {ncarta_baseline}')
    for (N,M) in GRADES:
        quads=tentar_grade(img,N,M,a.min_frac)
        # conta cartas com área frac razoável (>0.15 célula) e ratio de carta
        cartas=0
        for q in quads:
            if q['frac']<a.thr_frac: continue
            # ratio de aspecto do quad
            pts=q['pts']; 
            l1=math.hypot(pts[1][0]-pts[0][0], pts[1][1]-pts[0][1])
            l2=math.hypot(pts[2][0]-pts[1][0], pts[2][1]-pts[1][1])
            r=min(l1,l2)/max(l1,l2)
            if 0.45<=r<=0.95: cartas+=1
        print(f'  grade {N}x{M}: {len(quads)} quads, {cartas} carta(s-ratio)')
    print('\n(dica: escolher a grade com mais cartas-ratio e células cobrindo toda imagem)')


if __name__=='__main__':
    main()