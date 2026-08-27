"""diag_grid_binder.py — P3.34: detecta a grade de células do binder a partir
das costuras (linhas escuras de vinil) e mapeia qual célula tem/mão tem carta.
Dado: foto 20260822_115216 (8 cartas, fundo preto, 3x3)."""
import sys, glob
import cv2, numpy as np

sys.path.insert(0, 'experiments')
import debug_segmentacao as DS

def achar_costuras(gray):
    """Costuras = linhas escuras (baixo brilho) persistentes em toda a largura/altura.
    Detecção: para cada linha, média de escuridão; costuras verticais = faixas colunares
    com mínimo de média. Usa a média do gradiente de escuridão ao longo de eixo."""
    h, w = gray.shape
    dark = (255 - gray).astype(np.float32)
    # perfil por coluna (média vertical) -> costuras verticais aparecem como picos
    col = dark.mean(axis=0)
    row = dark.mean(axis=1)
    # suaviza e acha vales/picos
    def picos(sig, minh):
        s = cv2.GaussianBlur(sig.reshape(-1,1).astype(np.float32),(1,11),0).ravel()
        m = s.mean(); std = s.std()
        th = m + 1.2*std
        peaks=[]; inb=False
        for i,v in enumerate(s):
            if v>th and not inb: st=i; inb=True
            elif v<=th and inb:
                if i-st>=minh: peaks.append((st,i))
                inb=False
        if inb and len(s)-st>=minh: peaks.append((st,len(s)))
        return peaks
    vcost = picos(col, 4)     # faixas X de costura vertical (colunas)
    hcost = picos(row, 4)     # faixas Y de costura horizontal (linhas)
    return vcost, hcost

f = glob.glob('C:/projects/pokescan-tcg-labels/**/20260822_115216.jpg', recursive=True)[0]
img = cv2.imread(f)
g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
vc, hc = achar_costuras(g)
print('costuras verticais (x0-x1):', vc)
print('costuras horizontais (y0-y1):', hc)

# quads detectados
quads, dbg = DS.detect_quads_adaptive(img)
centros = []
for q in quads:
    pts=q['pts']; cx=sum(p[0] for p in pts)/4; cy=sum(p[1] for p in pts)/4
    centros.append((cx,cy))
print('quads detectados:', len(centros))

# se tivermos >=3 costuras vert e 2 costuras horiz => define grid
def grid_centros(vc,hc):
    # coordenadas médias das costuras verticais -> limites X das colunas
    vx = [ (a+b)/2 for a,b in vc ]
    hx = [ (a+b)/2 for a,b in hc ]
    if len(vx)>=2 and len(hx)>=2:
        xs = [0]+vx+[img.shape[1]]
        ys = [0]+hx+[img.shape[0]]
        cx=[ (xs[i]+xs[i+1])/2 for i in range(len(xs)-1)]
        cy=[ (ys[j]+ys[j+1])/2 for j in range(len(ys)-1)]
        return cx,cy
    return None

gc = grid_centros(vc,hc)
if gc:
    cx,cy = gc
    print('grid células: cols cx=', [int(x) for x in cx], 'rows cy=', [int(y) for y in cy])
    # mapeia cada centro detectado à célula
    mat = [['·']*len(cx) for _ in cy]
    for (qx,qy) in centros:
        i=np.argmin([abs(qy-cy[j]) for j in range(len(cy))])
        j=np.argmin([abs(qx-cx[k]) for k in range(len(cx))])
        mat[i][j]='X'
    print('mapa detecção (· = vaga sem carta detectada, X = carta detectada):')
    for r in mat: print('  '+' '.join(r))
else:
    print('grade não detectada pelas costuras — tentar outro método')