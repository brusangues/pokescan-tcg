"""recall_deteccao_grid.py — P3.34: mede recall de DETECÇÃO (qds grandes) do
baseline vs baseline+célula(as grade candidata) nas fotos multi-carta.

Foco puro em DETECÇÃO: conta quads com área frac (≥~0.05 da imagem) e ratio de
carta. A grade por validação é usada como AUMENTO: testa grades naturais,
detecta por célula, e adiciona só quads que não se sobrepõem aos já achados
(nunca regride). Reporta melhor grade por foto e ganho.
"""
import sys, glob, json, math
import cv2, numpy as np
from pathlib import Path

sys.path.insert(0, 'experiments')
import debug_segmentacao as DS

BASE = Path(__file__).resolve().parent.parent
LABELS = json.loads((BASE/'experiments'/'base_labels.json').read_text(encoding='utf-8'))
GRADES = [(2,2),(2,3),(3,2),(3,3),(2,4),(4,2),(3,4),(4,3)]


def sobrepoe(pts_a, pts_b, imgw, imgh, frac=0.5):
    """Verdadeiro se os boundings se sobrepõem em >=frac da área menor."""
    def bb(pts):
        x=[p[0] for p in pts]; y=[p[1] for p in pts]
        return (min(x),min(y),max(x),max(y))
    ax0,ay0,ax1,ay1=bb(pts_a); bx0,by0,bx1,by1=bb(pts_b)
    ix=max(0,min(ax1,bx1)-max(ax0,bx0)); iy=max(0,min(ay1,by1)-max(ay0,by0))
    inter=ix*iy
    area_a=(ax1-ax0)*(ay1-ay0); area_b=(bx1-bx0)*(by1-by0)
    return inter >= frac*min(area_a,area_b)


def ratio_carta(pts):
    l1=math.hypot(pts[1][0]-pts[0][0],pts[1][1]-pts[0][1])
    l2=math.hypot(pts[2][0]-pts[1][0],pts[2][1]-pts[1][1])
    r=min(l1,l2)/max(l1,l2)
    return 0.45<=r<=0.95


def carta_na_celula(roi, min_frac=0.10):
    q,_=DS.detect_quads(roi,max_quads=2,params={'min_area_frac':min_frac})
    if not q:
        q,_=DS.detect_quads(roi,max_quads=2,params={'min_area_frac':min_frac*0.5})
    return q


def grid_aumento(img, N, M, existentes, min_frac=0.10):
    """Detecta por célula e retorna quads novos (ratio carta, não sobrepostos)."""
    W,H=img.shape[1],img.shape[0]
    xs=np.linspace(0,W,N+1); ys=np.linspace(0,H,M+1)
    novos=[]
    for i in range(N):
        for j in range(M):
            x0,x1=int(xs[i]),int(xs[i+1]); y0,y1=int(ys[j]),int(ys[j+1])
            if x1-x0<70 or y1-y0<70: continue
            roi=img[y0:y1,x0:x1]
            for q in carta_na_celula(roi,min_frac):
                pts=[(float(p[0])+x0,float(p[1])+y0) for p in q['pts']]
                if not ratio_carta(pts): continue
                area=q.get('area',0); frac=area/max(1.0,(x1-x0)*(y1-y0))
                if frac<0.10: continue  # célula quase vazia
                # sobreposição com existentes?
                dup=any(sobrepoe(pts, e, W, H) for e in existentes)
                if not dup:
                    novos.append({'pts':pts,'area':area,'frac':frac})
    return novos


def main():
    DS._load_index()
    res={'baseline':[],'malhor':[],'baseline_n':0,'melhor_n':0,'n_fotos':0}
    print(f'fotos multi-carta:')
    for fname,info in LABELS.items():
        if len(info.get('cartas',[]))<5: continue
        pat=glob.glob(str(BASE.parent/'pokescan-tcg-labels'/'**'/fname),recursive=True)
        if not pat: continue
        img=cv2.imread(pat[0]); W,H=img.shape[1],img.shape[0]
        qb,_=DS.detect_quads_adaptive(img)
        # baseline: quads grandes com ratio carta
        base=[q for q in qb if (q.get('area',0)/(W*H))>=0.05 and ratio_carta([(p[0],p[1]) for p in q.get('pts',[])])]
        nb=len(base)
        melhor=nb; melhor_g='baseline'
        best_quads=list(base)
        # pts dos quads baseline, em lista de listas
        base_pts = [[(float(p[0]),float(p[1])) for p in q['pts']] for q in base]
        for (N,M) in GRADES:
            novos=grid_aumento(img,N,M,base_pts)
            # só conta os que não sobrepõem entre si
            unicos=[novos[0]] if novos else []
            for q in novos[1:]:
                if not any(sobrepoe(q['pts'],u['pts'],W,H) for u in unicos): unicos.append(q)
            total=nb+len(unicos)
            if total>melhor:
                melhor=total; melhor_g=f'{N}x{M}'; best_quads=list(base)+unicos
        res['baseline_n']+=nb; res['melhor_n']+=melhor; res['n_fotos']+=1
        res['baseline'].append((fname,nb)); res['malhor'].append((fname,melhor,melhor_g))
        print(f'  {fname.split(".")[0][4:]}: {nb} -> {melhor} ({melhor_g})')
    print(f'\n=== AGRUPADO ({res["n_fotos"]} fotos) ===')
    print(f'quads baseline (grandes): {res["baseline_n"]}')
    print(f'quads baseline+célula (melhor grade): {res["melhor_n"]} (+{res["melhor_n"]-res["baseline_n"]})')
    (BASE/'experiments'/'recall_deteccao_grid.json').write_text(json.dumps(res,ensure_ascii=False,indent=1),encoding='utf-8')


if __name__=='__main__':
    main()