// Scanner engine: DINOv2-small q4f16 (ONNX local) + índice PCA128 fp16.
// Tudo roda no browser — nenhum servidor envolvido. O carregamento é
// explícito (botão "Carregar") e o modelo/índice ficam em public/scanner/.

import { env, pipeline } from '@xenova/transformers';
import { getBasePath } from '@/app/lib/basePath';

export interface ScannerCard {
  id: string;
  n: string;    // name
  s: string;    // set id
  sn: string;   // set name
  num: string;  // number
  r: string;    // rarity
  p: number | null; // tcgplayer market price (USD)
  img: string;  // small image URL
}

export interface ScanResult {
  card: ScannerCard;
  score: number;
  rank: number;
  /** Margem top-1 vs top-2 (ambiguidade). Só no rank 1. */
  margin?: number;
}

const MODEL_ID = 'dinov2-small';
const HIDDEN = 384;      // dinov2-small hidden size
const N_PATCH = 256;     // 16x16 patches (sem CLS)
const D_RAW = HIDDEN * 2; // cls + mean = 768
const N_COMP = 128;      // PCA components

const BASE = `${getBasePath()}/scanner/`;

function halfToFloat(h: number): number {
  const s = (h & 0x8000) >> 15;
  const e = (h & 0x7c00) >> 10;
  const m = h & 0x03ff;
  let f: number;
  if (e === 0) {
    if (m === 0) f = 0;
    else {
      const v = m / 1024;
      f = v * 2 ** -14;
    }
  } else if (e === 0x1f) {
    f = m ? NaN : Infinity;
  } else {
    f = (1 + m / 1024) * 2 ** (e - 15);
  }
  return s ? -f : f;
}

class ScannerEngine {
  private static _instance: ScannerEngine | null = null;
  static get instance(): ScannerEngine {
    if (!this._instance) this._instance = new ScannerEngine();
    return this._instance;
  }

  private extractor: any = null;
  private index: Float32Array | null = null;   // N_rows x 128 (fp16->fp32)
  private rowCards: Uint16Array | null = null; // card (0..nCards-1) de cada linha — dedup das variantes
  private pcaMean: Float32Array | null = null; // 768
  private pcaComps: Float32Array | null = null; // 128 x 768 (whitened)
  private cards: ScannerCard[] = [];
  private loaded = false;
  private loading: Promise<void> | null = null;

  get isLoaded() { return this.loaded; }
  get cardCount() { return this.cards.length; }

  /** Carrega modelo + índice + PCA + metadados. Idempotente. */
  load(onProgress: (pct: number, label: string) => void): Promise<void> {
    if (this.loading) return this.loading;
    this.loading = this._load(onProgress).then(() => {
      this.loaded = true;
    });
    return this.loading;
  }

  private async _load(onProgress: (pct: number, label: string) => void): Promise<void> {
    // 1. Modelo (Transformers.js baixa do local /scanner/model/)
    env.allowLocalModels = true;
    env.localModelPath = BASE + 'model/';
    env.backends.onnx.wasm.wasmPaths = BASE + 'wasm/';

    onProgress(2, 'Baixando modelo de visão (12.9 MB)...');
    this.extractor = await pipeline('image-feature-extraction', MODEL_ID, {
      progress_callback: (p: any) => {
        if (p.status === 'progress' && p.total) {
          const pct = 2 + (p.loaded / p.total) * 48;
          onProgress(Math.min(50, pct), `Baixando modelo... ${(p.loaded / 1e6).toFixed(1)}/${(p.total / 1e6).toFixed(1)} MB`);
        }
      },
    });

    // 2. Índice PCA128 fp16 (5.2 MB)
    onProgress(52, 'Baixando índice (5.2 MB)...');
    const idxBuf = await this.fetchWithProgress(`${BASE}index.bin`, (pct) => {
      onProgress(52 + pct * 0.4, 'Baixando índice...');
    });
    const idxU16 = new Uint16Array(idxBuf);
    const nRows = idxU16.length / N_COMP;
    const idxF32 = new Float32Array(idxU16.length);
    for (let i = 0; i < idxU16.length; i++) idxF32[i] = halfToFloat(idxU16[i]);
    this.index = idxF32;

    // row_cards: card (0..nCards-1) de cada linha — o índice é aumentado
    // (K variantes/carta), então várias linhas pertencem ao mesmo card;
    // na busca computa-se o MÁXIMO de similaridade por card.
    onProgress(60, 'Carregando índices...');
    const rcBuf = await (await fetch(`${BASE}row_cards.bin`)).arrayBuffer();
    this.rowCards = new Uint16Array(rcBuf);

    // 3. PCA bundle: [mean(768) | comps_whitened(128x768)] fp32
    onProgress(94, 'Carregando PCA...');
    const pcaBuf = await (await fetch(`${BASE}pca.bin`)).arrayBuffer();
    const pcaF32 = new Float32Array(pcaBuf);
    this.pcaMean = pcaF32.slice(0, D_RAW);
    this.pcaComps = pcaF32.slice(D_RAW, D_RAW + N_COMP * D_RAW);

    // 4. Metadados
    onProgress(98, 'Carregando metadados...');
    const res = await fetch(`${BASE}cards.json`);
    this.cards = await res.json();
    onProgress(100, 'Pronto');
  }

  private async fetchWithProgress(url: string, onPct: (pct: number) => void): Promise<ArrayBuffer> {
    const resp = await fetch(url);
    const total = Number(resp.headers.get('content-length') || 0);
    if (!resp.body || !total) return resp.arrayBuffer();
    const reader = resp.body.getReader();
    const chunks: Uint8Array[] = [];
    let received = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      received += value.length;
      onPct(received / total);
    }
    const out = new Uint8Array(received);
    let off = 0;
    for (const c of chunks) { out.set(c, off); off += c.length; }
    return out.buffer;
  }

  /** Embedding 768d (cls + mean) da imagem. */
  private async embed(imgUrl: string): Promise<Float32Array> {
    const out = await this.extractor(imgUrl);
    const data: Float32Array = out.data; // 1 x 257 x 384 achatado
    const v = new Float32Array(D_RAW);
    // CLS token
    for (let d = 0; d < HIDDEN; d++) v[d] = data[d];
    // Mean dos patch tokens
    const sum = new Float32Array(HIDDEN);
    for (let t = 1; t <= N_PATCH; t++) {
      const off = t * HIDDEN;
      for (let d = 0; d < HIDDEN; d++) sum[d] += data[off + d];
    }
    for (let d = 0; d < HIDDEN; d++) v[HIDDEN + d] = sum[d] / N_PATCH;
    return v;
  }

  /** Projeta 768d → 128d PCA whitened + L2 normalize. */
  private project(v: Float32Array): Float32Array {
    const p = new Float32Array(N_COMP);
    for (let i = 0; i < N_COMP; i++) {
      let s = 0;
      const row = i * D_RAW;
      for (let j = 0; j < D_RAW; j++) {
        s += (this.pcaComps![row + j]) * (v[j] - this.pcaMean![j]);
      }
      p[i] = s;
    }
    let norm = 0;
    for (let i = 0; i < N_COMP; i++) norm += p[i] * p[i];
    norm = Math.sqrt(norm) || 1;
    for (let i = 0; i < N_COMP; i++) p[i] /= norm;
    return p;
  }

  /** Busca top-K por similaridade de cosseno. Índice aumentado: várias linhas
   * por carta → ache se o MÁXIMO de similaridade por card. */
  async search(imgUrl: string, topK = 5): Promise<ScanResult[]> {
    if (!this.loaded) throw new Error('Scanner não carregado');
    const q = this.project(await this.embed(imgUrl));
    const idx = this.index!;
    const rc = this.rowCards!;
    const nCards = this.cards.length;
    // melhor score por card (max sobre as variantes de cada carta)
    // CLAMP a [0,1] e descarta NaN/Inf: crops degenerados podem dar produto
    // interno >1 (query corrompido) — clamp impede que um score anômalo domine o rank.
    const clamp1 = (x: number) => (Number.isFinite(x) ? Math.max(0, Math.min(1, x)) : 0);
    const best = new Float32Array(nCards).fill(-Infinity);
    const nRows = rc.length;
    for (let i = 0; i < nRows; i++) {
      let s = 0;
      const off = i * N_COMP;
      for (let j = 0; j < N_COMP; j++) s += idx[off + j] * q[j];
      if (!Number.isFinite(s)) continue;
      const c = rc[i];
      const sC = clamp1(s);
      if (sC > best[c]) best[c] = sC;
    }
    const order = Array.from({ length: nCards }, (_, i) => i);
    order.sort((a, b) => best[b] - best[a]);
    const top = order.slice(0, topK);
    const s0 = clamp1(best[top[0]]);
    const s1 = top.length > 1 ? clamp1(best[top[1]]) : 0;
    return top.map((i, rank) => ({
      card: this.cards[i],
      score: clamp1(best[i]),
      rank: rank + 1,
      margin: rank === 0 ? s0 - s1 : undefined,
    }));
  }
}

export default ScannerEngine;
