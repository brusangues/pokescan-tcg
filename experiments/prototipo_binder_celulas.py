"""prototipo_binder_celulas.py — P3.34: detecção por células da grade do binder.

Hipótese: cartas em binder fundo preto que tocam a borda da imagem (topo/base)
são perdidas pelo detect_quads global (linha 64 DESCARTa contorno na borda) e
pela fusão com o fundo preto. 

Ideia: detectar as costuras do binder (linhas escuras de vinil → grade NxM) e
rodar a detecção DENTRO de cada célula (ROI recortado). A carta preenche ~90%
da célula, o vinil deixa margem → contorno fecha dentro do ROI e não toca a
borda do ROI. Mapeia os pontos de volta às coordenadas originais.

Mede recall por célula vs as labels e procura regressão na base inteira.
"""
import sys, glob, json
from pathlib import Path
import cv2, numpy as np, math

sys.path.insert(0, 'experiments')
import debug_segmentacao as DS

BASE = Path(__file__).resolve().parent.parent
LABELS = json.loads((BASE/'experiments'/'base_labels.json').read_text(encoding='utf-8'))


def costuras(gray):
    """Faixas de costura (pico de escuridão) vertical (X) e horizontal (Y)."""
    h, w = gray.shape
    dark = (255 - gray).astype(np.float32)
    def picos(sig, minh):
        s = cv2.GaussianBlur(sig.reshape(-1,1).astype(np.float32),(1,15),0).ravel()
        m=s.mean(); th=m+1.1*s.std()
        pk=[]; inb=False
        for i,v in enumerate(s):
            if v>th and not inb: st=i; inb=True
            elif v<=th and inb:
                if i-st>=minh: pk.append((st,i))
                inb=False
        if inb and len(s)-st>=minh: pk.append((st,len(s)))
        return pk
    vc = picos(dark.mean(axis=0), 4)
    hc = picos(dark.mean(axis=1), 4)
    return vc, hc


def grade_real(vc, hc, W, H):
    """Cols/rows centrais reais: remove costuras de borda (primeira/última). Retorna
    limites de cada célula. Só constrói se houver 3+ colunas e 2+ linhas reais."""
    vx = [(a+b)/2 for a,b in vc]
    hx = [(a+b)/2 for a,b in hc]
    vx = [v for v in vx if 0.02*W < v < 0.98*W]
    hx = [h for h in hx if 0.02*H < h < 0.98*H]
    # células: borderline esquerda=0 entre costuras, direita=W
    xs = [0.0] + vx + [float(W)]
    ys = [0.0] + hx + [float(H)]
    return xs, ys


def detect_por_celulas(img_bgr, vc, hc, max_quads=12):
    """Percorre cada célula, detecta ROI local, mapeia pts p/ coords originais."""
    W, H = img_bgr.shape[1], img_bgr.shape[0]
    xs, ys = grade_real(vc, hc, W, H)
    out = []
    for i in range(len(xs)-1):
        for j in range(len(ys)-1):
            x0,x1 = int(xs[i]), int(xs[i+1])
            y0,y1 = int(ys[j]), int(ys[j+1])
            cx0,cx1 = max(0,x0), min(W,x1)
            cy0,cy1 = max(0,y0), min(H,y1)
            if cx1-cx0 < 80 or cy1-cy0 < 80: continue
            roi = img_bgr[cy0:cy1, cx0:cx1]
            # célula quase toda carta: min_area .12 rel ao ROI p/ só a carta, 2º passe .04
            q,_ = DS.detect_quads(roi, max_quads=2, params={'min_area_frac':0.12})
            if not q:
                q,_ = DS.detect_quads(roi, max_quads=2, params={'min_area_frac':0.04})
            for quad in q:
                pts = [(float(p[0])+cx0, float(p[1])+cy0) for p in quad['pts']]
                out.append({'pts': pts, 'area': quad.get('area',0)})
    return out


def main():
    alvos = [(k,v) for k,v in LABELS.items() if v.get('cartas')]
    tot_cel = tot_cel_ok = 0
    perdidas_opt1 = {}   # foto -> lista de nomes esperados não achados
    erros_por_foto = {}
    for fname, info in alvos:
        if '115216' not in fname and '115504' not in fname:
            continue  # foco nesta sessão: fotos de binder
        pat = glob.glob(str(BASE.parent/'pokescan-tcg-labels'/'**'/fname), recursive=True)
        if not pat: continue
        img = cv2.imread(pat[0])
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        vc, hc = costuras(g)
        quads = detect_por_celulas(img, vc, hc)
        lab_toks = set(DS.tok(c['nome']) for c in info['cartas'])
        achados = set()
        for quad in quads:
            warp = DS.warp_card(img, quad['pts'])
            if warp is None: continue
            nome, score, marg, idx = DS.match_crop(warp)[0]
            if DS.eh_acerto(nome, lab_toks):
                achados.add(DS.tok(nome))
        perdidas = lab_toks - achados
        erros_por_foto[fname] = {'esperadas':len(lab_toks),'achadas':len(achados),'perdidas':sorted(perdidas)}
        print(f'{fname}: costuras V={len([v for v in vc if 0.02*img.shape[1]<(v[0]+v[1])/2<0.98*img.shape[1]])} H={len([h for h in hc if 0.02*img.shape[0]<(h[0]+h[1])/2<0.98*img.shape[0]])} | '+
              f'{len(achados)}/{len(lab_toks)} ({len(achados)/len(lab_toks):.0%}) | perdidas: {sorted(perdidas)}')
    (BASE/'experiments'/'binder_celulas_resultado.json').write_text(
        json.dumps(erros_por_foto, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()