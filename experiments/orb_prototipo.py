"""orb_prototipo.py — P2.32: verificação ORB nos top-3 do DINOv2.

Métrica fiel ao PRODUTO (acerto agregado por carta, como avaliacao_margem):
para cada foto, conta-se a fração de CARTAS-única (labels) que apareceram como
top-1 escolhido em ALGUM crop.

Lógica do proposto (igual ao que vai no browser):
  - match_crop → top-k (DINOv2): nome, score, MARGEM top1−top2, card_idx
  - se MARGEM >= 0.03 (confiante) → mantém top-1 DINOv2
  - se MARGEM < 0.03 (ambíguo) → VERIFICAÇÃO ORB: compara o crop real com a
    imagem oficial dos top-3 via ORB; escolhe o candidato de MAIOR nº inliers
    (a arte correta é a que mais casa geometricamente).

Compara baseline (top-1 puro) vs proposto (top-1 + ORB p/ ambíguos) na
MESMA coleção de fotos → para saber se o ORB recupera ambiguidades.
"""
import argparse, glob, json, os
import cv2
import numpy as np
import sys

BASE = __import__('pathlib').Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / 'experiments'))
import debug_segmentacao as DS

ORB = cv2.ORB_create(nfeatures=1000, scaleFactor=1.2, nlevels=8,
                     edgeThreshold=31, firstLevel=0, WTA_K=2,
                     scoreType=cv2.ORB_HARRIS_SCORE, patchSize=31, fastThreshold=20)
BF = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
IMG_CACHE = BASE / 'data' / 'img_cache'


def _resize(bgr, maxdim=360):
    h, w = bgr.shape[:2]
    s = min(1.0, maxdim / max(w, h))
    return bgr if s >= 1 else cv2.resize(bgr, (round(w * s), round(h * s)))


def orb_inliers(q_bgr, ref_bgr):
    try:
        kp1, d1 = ORB.detectAndCompute(_resize(q_bgr), None)
        kp2, d2 = ORB.detectAndCompute(_resize(ref_bgr), None)
        if d1 is None or d2 is None or len(d1) < 5 or len(d2) < 5:
            return 0.0
        m = BF.knnMatch(d1, d2, k=2)
        g = 0
        for p in m:
            if len(p) == 2:
                mm, nn = p
                if mm.distance < 0.75 * nn.distance:
                    g += 1
        return float(g)
    except Exception:
        return 0.0


def img_oficial(card_idx):
    cards = DS._cards
    if not (0 <= int(card_idx) < len(cards)):
        return None
    cid = str(cards[int(card_idx)].get('id') or '')
    p = IMG_CACHE / f'{cid}.png'
    return cv2.imread(str(p)) if p.exists() else None


def main(topk=3, margem_min=0.03):
    DS._load_index()
    raw = json.loads((BASE / 'experiments' / 'base_labels.json').read_text(encoding='utf-8'))
    base_dir = BASE.parent / 'pokescan-tcg-labels'
    fotos = []  # (path, {token_primerio_de_cada_carta})
    for fname, info in raw.items():
        if not (info.get('cartas') or []):
            continue
        alt = glob.glob(str(base_dir / '**' / os.path.basename(fname)), recursive=True)
        if not alt:
            alt = [fname] if os.path.exists(fname) else []
        if not alt:
            continue
        tokens = list(dict.fromkeys(DS.tok(c['nome']) for c in info['cartas']))
        fotos.append((alt[0], set(tokens)))

    # acumula por foto: cartas achadas (baseline) e cartas achadas (proposto)
    stat_b = {'total': 0, 'ach': 0}
    stat_p = {'total': 0, 'ach': 0}
    det_fora = 0  # crops cujo top-3 não tinha ref oficial (exclusão do proposto)
    cases = {'amb': 0, 'amb_orb_acertou': 0, 'amb_top1_ja_acertava': 0,
             'amb_tinha_certa_topk': 0, 'conf': 0}
    nao_verificaveis = {'amb': 0}
    for fi, (path, lab_tokens) in enumerate(fotos, 1):
        img = cv2.imread(path)
        if img is None:
            continue
        quads, _ = DS.detect_quads_adaptive(img)
        hits_b = set(); hits_p = set()
        for quad in quads:
            pts = quad['pts'] if isinstance(quad, dict) and 'pts' in quad else quad
            warp = DS.warp_card(img, pts)
            if warp is None or warp.size == 0:
                continue
            topm = DS.match_crop(warp, topk=topk)  # (nome, score, marg, idx)
            b_nome, b_scr, b_marg, b_idx = topm[0]
            certa_no_topk = any(DS.eh_acerto(nm, lab_tokens) for nm, *_ in topm)
            if DS.eh_acerto(b_nome, lab_tokens):
                hits_b.add(DS.tok(b_nome))
            if b_marg is not None and b_marg >= margem_min:
                cases['conf'] += 1
                hits_p.add(DS.tok(b_nome) if DS.eh_acerto(b_nome, lab_tokens) else '')
                if DS.eh_acerto(b_nome, lab_tokens):
                    hits_p.discard(''); hits_p.add(DS.tok(b_nome))
            else:
                cases['amb'] += 1
                if certa_no_topk:
                    cases['amb_tinha_certa_topk'] += 1
                best_cand, best_n = None, -1.0
                for nome, scr, marg, cidx in topm:
                    ref = img_oficial(cidx)
                    if ref is None:
                        continue
                    ni = orb_inliers(warp, ref)
                    if ni > best_n:
                        best_n, best_cand = ni, (nome, scr, marg, cidx)
                if best_cand is None:
                    det_fora += 1
                    nao_verificaveis['amb'] += 1
                    escolhido = topm[0]
                else:
                    escolhido = best_cand
                acertou_orb = DS.eh_acerto(escolhido[0], lab_tokens)
                if acertou_orb:
                    cases['amb_orb_acertou'] += 1
                    hits_p.add(DS.tok(escolhido[0]))
                else:
                    # ORB não achou a certa: mantém nada (não soma)
                    pass
        stat_b['total'] += len(lab_tokens); stat_b['ach'] += len(hits_b & lab_tokens)
        stat_p['total'] += len(lab_tokens); stat_p['ach'] += len(hits_p & lab_tokens)
        print(f'[{fi}/{len(fotos)}] {os.path.basename(path)}: B={len(hits_b&lab_tokens)}/{len(lab_tokens)} P={len(hits_p&lab_tokens)}/{len(lab_tokens)}')

    print(f'\n===== P2.32 ORB top-{topk} (margem_min={margem_min}) — métrica agregada por carta =====')
    print(f'baseline (DINOv2 top-1):  {stat_b["ach"]}/{stat_b["total"]} = {stat_b["ach"]/stat_b["total"]:.3f}')
    print(f'proposto (+ORB ambíguos): {stat_p["ach"]}/{stat_p["total"]} = {stat_p["ach"]/stat_p["total"]:.3f}')
    print(f'crops sem ref oficial (não verificáveis): {det_fora}')
    print(f'ganho: {stat_p["ach"]-stat_b["ach"]:+d} cartas ({(stat_p["ach"]-stat_b["ach"])/stat_b["ach"]*100:+.1f}% rel)')
    print(f'\n--- inferência por crop ---')
    print(f'confiantes (margem>=min): {cases["conf"]}')
    print(f'ambíguos (ORB acionado):  {cases["amb"]} | desses, certa estava no top-{topk}: {cases["amb_tinha_certa_topk"]}')
    print(f'  → ORB escolheu a certa: {cases["amb_orb_acertou"]}')
    print(f'  → não verificáveis (sem img oficial): {nao_verificaveis["amb"]}')
    (BASE / 'experiments' / 'orb_resultado_v2.json').write_text(
        json.dumps({'baseline': stat_b, 'proposto': stat_p, 'ganho': stat_p['ach']-stat_b['ach'],
                    'topk': topk, 'margem_min': margem_min, 'n_fotos': len(fotos), 'cases': cases},
                   ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--topk', type=int, default=3)
    ap.add_argument('--margem-min', type=float, default=0.03)
    a = ap.parse_args()
    main(topk=a.topk, margem_min=a.margem_min)