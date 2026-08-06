// Clipping de carta TCG: detecta o quadrilátero (contorno + aprox. poligonal),
// valida pela razão de aspecto da carta (63×88 ≈ 0.716) e aplica transformação
// de perspectiva. Roda no browser via OpenCV.js (WASM embutido em /scanner/opencv.js).
//
// Retorna um canvas com a carta reta, ou null se não encontrar quadrilátero
// confiável (o chamador usa a imagem original como fallback).

import { getBasePath } from '@/app/lib/basePath';

let cvPromise: Promise<any> | null = null;

/** Carrega o OpenCV.js uma única vez (script tag + window.cv — Promise). */
export function loadOpenCV(): Promise<any> {
  if (cvPromise) return cvPromise;
  cvPromise = new Promise((resolve, reject) => {
    if (typeof window === 'undefined') return reject(new Error('browser only'));
    const w = window as any;
    const ready = async () => {
      try {
        // opencv.js 5.0 (techstark): window.cv é uma Promise que resolve
        // com o módulo completo (cv.Mat, cv.imread, ...)
        const mod = w.cv instanceof Promise ? await w.cv : w.cv;
        if (mod && mod.Mat) return resolve(mod);
        // fallback: aguarda o runtime inicializar
        const tryGet = () => {
          if (w.cv && w.cv.Mat) resolve(w.cv);
          else if (mod && mod.Mat) resolve(mod);
          else setTimeout(tryGet, 100);
        };
        setTimeout(tryGet, 100);
      } catch (err) {
        reject(err);
      }
    };

    if (w.cv) return ready();
    const script = document.createElement('script');
    script.src = `${getBasePath()}/scanner/opencv.js`;
    script.async = true;
    script.onload = ready;
    script.onerror = () => reject(new Error('Falha ao carregar OpenCV.js'));
    document.head.appendChild(script);
  });
  return cvPromise;
}

export interface Quad {
  points: { x: number; y: number }[]; // TL, TR, BR, BL
  area: number;
}

/** Escala a imagem para ~1000px no maior lado (acelera a detecção). */
function toWorkingCanvas(cv: any, img: HTMLCanvasElement | HTMLImageElement) {
  const maxSide = 1000;
  const w = img.width || (img as HTMLImageElement).naturalWidth;
  const h = img.height || (img as HTMLImageElement).naturalHeight;
  const scale = Math.min(1, maxSide / Math.max(w, h));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(w * scale);
  canvas.height = Math.round(h * scale);
  const ctx = canvas.getContext('2d')!;
  ctx.drawImage(img as any, 0, 0, canvas.width, canvas.height);
  return { canvas, scale };
}

/**
 * Detecta o quadrilátero da carta na imagem.
 * Estratégia multi-passada (blur/Canny progressivos) — robusta a fundos
 * lisos/ruidosos e cartas escuras. Valida por área mínima, não tocar a
 * borda e razão de aspecto da carta TCG (63×88 ≈ 0.716).
 */
export async function detectCardQuad(img: HTMLCanvasElement | HTMLImageElement): Promise<Quad | null> {
  const cv = await loadOpenCV();
  const { canvas, scale } = toWorkingCanvas(cv, img);
  const src = cv.imread(canvas);

  const minArea = src.rows * src.cols * 0.05;
  const passes: [number, number, number][] = [
    [5, 50, 150], [5, 80, 200], [7, 50, 150], [9, 50, 150], [9, 80, 200],
  ];
  const kernel = cv.getStructuringElement(cv.MORPH_RECT, new cv.Size(3, 3));
  const gray = new cv.Mat();
  const edges = new cv.Mat();
  let contours = new cv.MatVector();
  const hierarchy = new cv.Mat();

  let best: Quad | null = null;

  for (const [ksize, low, high] of passes) {
    cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY);
    cv.GaussianBlur(gray, gray, new cv.Size(ksize, ksize), 0);
    cv.Canny(gray, edges, low, high);
    cv.dilate(edges, edges, kernel, new cv.Point(-1, -1), 2);
    cv.findContours(edges, contours, hierarchy, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE);

    for (let i = 0; i < contours.size(); i++) {
      const cnt = contours.get(i);
      const area = cv.contourArea(cnt);
      if (area < minArea) { cnt.delete(); continue; }
      const rect = cv.boundingRect(cnt);
      const touchesBorder =
        rect.x <= 2 || rect.y <= 2 ||
        rect.x + rect.width >= src.cols - 2 ||
        rect.y + rect.height >= src.rows - 2;
      if (touchesBorder) { cnt.delete(); continue; }
      const peri = cv.arcLength(cnt, true);
      let approx = new cv.Mat();
      let quadPts: { x: number; y: number }[] | null = null;
      // múltiplos epsilons: bordas curvas (lente/perspectiva) e diferenças
      // WASM float32 vs CPU precisam de eps maior no browser
      for (const eps of [0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10]) {
        cv.approxPolyDP(cnt, approx, eps * peri, true);
        if (approx.rows === 4) {
          const pts = [];
          for (let p = 0; p < 4; p++) {
            pts.push({
              x: Math.round(approx.data32S[p * 2] / scale),
              y: Math.round(approx.data32S[p * 2 + 1] / scale),
            });
          }
          const o = orderPoints(pts);
          const ratio = aspectRatio(o);
          if (ratio >= 0.45 && ratio <= 0.95) {
            quadPts = o;
            break;
          }
        }
      }
      // fallback: caixa rotacionada mínima (robusto a ângulos e bordas curvas)
      if (!quadPts) {
        try {
          const rect = cv.minAreaRect(cnt);
          // cv.boxPoints NÃO funciona no OpenCV.js 5.0 — calcula os 4 cantos na mão
          const cx = rect.center.x, cy = rect.center.y;
          const w = rect.size.width, h = rect.size.height;
          const theta = (rect.angle * Math.PI) / 180;
          const cos = Math.cos(theta), sin = Math.sin(theta);
          const pts = [];
          for (const [ox, oy] of [[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]]) {
            pts.push({
              x: Math.round((cx + ox * cos - oy * sin) / scale),
              y: Math.round((cy + ox * sin + oy * cos) / scale),
            });
          }
          const o = orderPoints(pts);
          const ratio = aspectRatio(o);
          if (ratio >= 0.45 && ratio <= 0.95) {
            quadPts = o;
          }
        } catch (e) {
          console.warn('minAreaRect fallback falhou', e);
        }
      }
      approx.delete();
      if (quadPts) {
        best = { points: quadPts, area: area / (scale * scale) };
        cnt.delete();
        contours.delete();
        src.delete(); gray.delete(); edges.delete();
        kernel.delete(); hierarchy.delete();
        return best;
      }
      cnt.delete();
    }
    contours.delete();
    contours = new cv.MatVector();
  }

  src.delete(); gray.delete(); edges.delete();
  kernel.delete(); contours.delete(); hierarchy.delete();
  return best;
}

/** Ordena 4 pontos: TL, TR, BR, BL (soma/diferença — robusto p/ rotação). */
function orderPoints(pts: { x: number; y: number }[]): { x: number; y: number }[] {
  const sum = pts.map((p) => p.x + p.y);
  const diff = pts.map((p) => p.y - p.x);
  const idxSum = sum.map((v, i) => i).sort((a, b) => sum[a] - sum[b]);
  const idxDiff = diff.map((v, i) => i).sort((a, b) => diff[a] - diff[b]);
  return [
    pts[idxSum[0]],  // TL (menor soma)
    pts[idxDiff[0]], // TR (menor y-x)
    pts[idxSum[3]],  // BR (maior soma)
    pts[idxDiff[3]], // BL (maior y-x)
  ];
}

/** Razão de aspecto (menor lado / maior lado) de um quadrilátero ordenado. */
function aspectRatio(o: { x: number; y: number }[]): number {
  const l1 = Math.hypot(o[1].x - o[0].x, o[1].y - o[0].y);
  const l2 = Math.hypot(o[2].x - o[1].x, o[2].y - o[1].y);
  return Math.min(l1, l2) / Math.max(l1, l2);
}

/**
 * Aplica a transformação de perspectiva: retorna canvas com a carta reta
 * (440×615 — razão 63:88), padding branco. Requer detectCardQuad antes.
 */
export async function warpCard(img: HTMLCanvasElement | HTMLImageElement, quad: Quad): Promise<HTMLCanvasElement> {
  const cv = await loadOpenCV();
  const src = cv.imread(img);
  const outW = 440;
  const outH = Math.round((outW * 88) / 63);

  const srcTri = cv.matFromArray(4, 1, cv.CV_32FC2, [
    quad.points[0].x, quad.points[0].y,
    quad.points[1].x, quad.points[1].y,
    quad.points[3].x, quad.points[3].y,
    quad.points[2].x, quad.points[2].y,
  ]);
  const dstTri = cv.matFromArray(4, 1, cv.CV_32FC2, [
    0, 0,
    outW - 1, 0,
    0, outH - 1,
    outW - 1, outH - 1,
  ]);
  const M = cv.getPerspectiveTransform(srcTri, dstTri);
  const warped = new cv.Mat();
  cv.warpPerspective(src, warped, M, new cv.Size(outW, outH), cv.INTER_LINEAR, cv.BORDER_CONSTANT, new cv.Scalar(255, 255, 255, 255));

  const canvas = document.createElement('canvas');
  canvas.width = outW;
  canvas.height = outH;
  cv.imshow(canvas, warped);

  src.delete(); warped.delete(); M.delete();
  srcTri.delete(); dstTri.delete();
  return canvas;
}

/** Helper: image element → canvas (para processar o upload). */
export function imageToCanvas(img: HTMLImageElement): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  canvas.getContext('2d')!.drawImage(img, 0, 0);
  return canvas;
}
