"""medir_deteccao_115216.py — P3.34: métrica PURA de detecção na foto do binder.
Conta quantos quads largos (cobrem ~célula) que retornam um crop não-degenerado
o baseline atual encontra, e compara com variantes até os 8 esperados.
Sem matching (rápido) — foco no recall de DETECÇÃO.
"""
import sys, glob
import cv2, numpy as np
sys.path.insert(0, 'experiments')
import debug_segmentacao as DS

f = glob.glob('C:/projects/pokescan-tcg-labels/**/20260822_115216.jpg', recursive=True)[0]
img = cv2.imread(f)
W, H = img.shape[1], img.shape[0]

# baseline
q2, _ = DS.detect_quads_adaptive(img)
print(f'baseline detect_quads_adaptive: {len(q2)} quads')
for i, q in enumerate(q2, 1):
    pts = q['pts']; cx=sum(p[0] for p in pts)/4; cy=sum(p[1] for p in pts)/4
    a=q.get('area',0)
    print(f'  {i}: ({cx:.0f},{cy:.0f}) area={a:.0f} (W*H={9e6}) frac={a/9e6:.3f}')

# célula da grade 3x3 (limites fixos das costuras reais)
cols = [0, 1010, 2025, 3000]
rows = [0, 1300, 2700, 4000]
print(f'\ngrid 3x3: cols={cols} rows={rows}')
quads_cel = []
for j in range(3):
    for i in range(3):
        cx0,cx1 = cols[i], cols[i+1]
        cy0,cy1 = rows[j], rows[j+1]
        roi = img[cy0:cy1, cx0:cx1]
        q,_ = DS.detect_quads(roi, max_quads=2, params={'min_area_frac':0.12})
        if not q:
            q,_ = DS.detect_quads(roi, max_quads=2, params={'min_area_frac':0.04})
        for quad in q:
            pts=[(float(p[0])+cx0,float(p[1])+cy0) for p in quad['pts']]
            quads_cel.append({'pts':pts,'area':quad.get('area',0)})
print(f'detecção por célula 3x3 fixa: {len(quads_cel)} quads')
for i,q in enumerate(quads_cel,1):
    pts=q['pts']; cx=sum(p[0] for p in pts)/4; cy=sum(p[1] for p in pts)/4
    print(f'  {i}: ({cx:.0f},{cy:.0f})')