"""matching_gain_grid.py — P3.34: ganho no MATCHING (cartas únicas acertadas) do
baseline vs baseline+célula nas fotos multi-carta. Reusa o grid_aumento.
"""
import sys, glob, json
import cv2, numpy as np
from pathlib import Path

sys.path.insert(0, 'experiments')
import debug_segmentacao as DS
import recall_deteccao_grid as R

BASE = Path(__file__).resolve().parent.parent
LABELS = json.loads((BASE/'experiments'/'base_labels.json').read_text(encoding='utf-8'))


def avaliar(img, lab_tks, include_grid):
    DS._load_index()
    qb,_=DS.detect_quads_adaptive(img)
    W,H=img.shape[1],img.shape[0]
    base=[q for q in qb if (q.get('area',0)/(W*H))>=0.04]
    quads=list(base)
    if include_grid:
        base_pts=[[(float(p[0]),float(p[1])) for p in q['pts']] for q in base]
        # usa as grades que ajudam; percorre todas e acumula não-sobrepostos
        for (N,M) in R.GRADES:
            novos=R.grid_aumento(img,N,M,base_pts)
            for q in novos:
                if not any(R.sobrepoe(q['pts'],u['pts'],W,H) for u in quads):
                    quads.append(q)
    ach=set()
    for q in quads:
        pts=q['pts']; warp=DS.warp_card(img,pts)
        if warp is None: continue
        nome,score,marg,idx=DS.match_crop(warp)[0]
        if marg is not None and marg>=0.03 and DS.eh_acerto(nome,lab_tks):
            ach.add(DS.tok(nome))
    return ach


def main():
    DS._load_index()
    res={'tot':0,'base_ach':0,'grid_ach':0}
    for fname,info in LABELS.items():
        if len(info.get('cartas',[]))<5: continue
        pat=glob.glob(str(BASE.parent/'pokescan-tcg-labels'/'**'/fname),recursive=True)
        if not pat: continue
        img=cv2.imread(pat[0])
        lab=set(DS.tok(c['nome']) for c in info['cartas'])
        a_b=avaliar(img,lab,False); a_g=avaliar(img,lab,True)
        res['tot']+=len(lab); res['base_ach']+=len(a_b); res['grid_ach']+=len(a_g)
        d=len(a_g)-len(a_b)
        print(f'  {fname.split(".")[0][4:]}: base={len(a_b)}/{len(lab)} grid={len(a_g)}/{len(lab)} (Δ{d:+d})')
    print(f'\n=== MATCHING (cartas únicas) ===')
    print(f'baseline: {res["base_ach"]}/{res["tot"]} = {res["base_ach"]/res["tot"]:.1%}')
    print(f'+célula:  {res["grid_ach"]}/{res["tot"]} = {res["grid_ach"]/res["tot"]:.1%}')
    print(f'ganho: {res["grid_ach"]-res["base_ach"]:+d} cartas')
    (BASE/'experiments'/'matching_gain_grid.json').write_text(json.dumps(res,ensure_ascii=False,indent=1),encoding='utf-8')


if __name__=='__main__':
    main()