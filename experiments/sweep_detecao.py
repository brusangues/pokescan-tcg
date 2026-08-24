"""sweep_detecao.py — mede RECALL de detecção (n_quads vs n_labels) por configuração
de segmentação, SEM rodar o match (rápido). Orienta a calibração: reduzir minArea
deve recuperar cartas de mesa pequenas; reduzir dedup deve separar cartas próximas.
"""
import json, sys
from pathlib import Path
import cv2
sys.path.insert(0, str(Path(__file__).resolve().parent))
import debug_segmentacao as ds

BASE = Path(__file__).resolve().parent.parent
base = json.loads((BASE/'experiments'/'base_labels.json').read_text(encoding='utf-8'))
alvos = [f for f,v in base.items() if len(v['cartas']) >= 4]   # multi-carta (onde a detecção importa)

configs = [
    (0.02, 0.15, 'baseline'),
    (0.012, 0.15, 'minArea .012'),
    (0.008, 0.15, 'minArea .008'),
    (0.006, 0.15, 'minArea .006'),
    (0.004, 0.15, 'minArea .004'),
    (0.008, 0.10, 'minArea .008 / dedup .10'),
    (0.008, 0.06, 'minArea .008 / dedup .06'),
]

print(f"{'config':28s} {'quads':>6} {'labels':>6} {'dif(±)':>6}  por-foto-quads excesso")
for mf, df, nome in configs:
    tot_q = tot_l = 0
    excess = []
    for foto in alvos:
        p = ds.localiza(foto)
        if not p: continue
        img = cv2.imread(str(p))
        q, _ = ds.detect_quads(img, max_quads=14, params={'min_area_frac': mf, 'dedup_frac': df})
        nlab = len(set(ds.tok(c['nome']) for c in base[foto]['cartas']))
        tot_q += len(q); tot_l += nlab
        excess.append(len(q) - nlab)
    print(f"{nome:28s} {tot_q:6d} {tot_l:6d} {tot_q-tot_l:+6d}  {sorted(excess)}")