'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Camera, Loader2, Search, CheckCircle2, AlertCircle, Download, ExternalLink, ImageOff, X, Type } from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import ScannerEngine, { ScanResult } from '@/app/lib/scannerEngine';
import { detectCardQuads, warpCard } from '@/app/lib/cardClip';
import { getBasePath } from '@/app/lib/basePath';
import { loadCards } from '@/app/lib/cardLookup';
import Image from 'next/image';

/** Carrega um dataURL em um elemento <img> (para processar no OpenCV). */
function loadImage(dataUrl: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = document.createElement('img');
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('Imagem inválida'));
    img.src = dataUrl;
  });
}

/** Resultado de carta (imagem ou texto) — mesmo layout da busca por imagem. */
function CardResult({ card, score, rank }: { card: any; score?: number; rank?: number }) {
  return (
    <div
      className={`flex gap-4 bg-white rounded-xl border p-4 ${
        rank === 1 ? 'border-indigo-300 ring-1 ring-indigo-100' : 'border-gray-100 opacity-90'
      }`}
    >
      <div className="relative w-20 h-28 bg-gray-100 rounded-lg overflow-hidden shrink-0">
        {card.img ? (
          <Image src={card.img} alt={card.n || card.nome} fill className="object-contain" unoptimized />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-gray-300">
            <ImageOff className="w-6 h-6" />
          </div>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <h4 className="font-bold text-gray-900 truncate">{card.n || card.nome}</h4>
          {score != null && (
            <span className={`text-xs font-mono px-2 py-0.5 rounded-full shrink-0 ${
              rank === 1 ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-600'
            }`}>
              {rank === 1 ? '✓ Melhor' : `#${rank}`} · {(score * 100).toFixed(1)}%
            </span>
          )}
        </div>
        <p className="text-sm text-gray-500 truncate">
          {card.sn || card.set_name} · {card.num || card.sNumber}
        </p>
        <div className="flex items-center justify-between mt-2 text-sm">
          <span className="text-xs text-gray-400">{card.r || '—'}</span>
          {card.p != null && (
            <span className="font-medium text-emerald-600">${card.p.toFixed(2)}</span>
          )}
        </div>
        {/* <a> com href prefixado manualmente — next/link duplica basePath em hrefs com query */}
        <a
          href={`${getBasePath()}/card?set=${encodeURIComponent(card.s || card.set_id)}&num=${encodeURIComponent(card.num || card.sNumber)}&nome=${encodeURIComponent(card.n || card.nome)}`}
          className="inline-flex items-center gap-1 mt-2 text-xs text-indigo-600 hover:underline"
        >
          <ExternalLink className="w-3 h-3" /> Ver detalhes e escoragem
        </a>
      </div>
    </div>
  );
}

/** Rank de busca por texto: 0 exato, 1 prefixo/número, 2 contém nome, 3 coleção/id, 4 raridade, -1 sem match. */
function rankCard(c: any, ql: string): number {
  const n = (c.n || '').toLowerCase();
  if (n === ql) return 0;
  if (n.startsWith(ql)) return 1;
  if ((c.num || '') === ql) return 1;
  if (n.includes(ql)) return 2;
  if ((c.sn || '').toLowerCase().includes(ql)) return 3;
  if ((c.id || '').toLowerCase().includes(ql)) return 3;
  if ((c.r || '').toLowerCase().includes(ql)) return 4;
  return -1;
}

// Limiar de confiança: abaixo disso a carta é marcada como 'não identificada'
const THRESH = 0.55;
// Cartas abaixo desta largura (px) na foto perdem qualidade no match
const LARGURA_MINIMA = 300;

/** Card de uma detecção multi-carta: thumbnail clicável + top-1 + similares expansíveis. */
function DeteccaoCard({ d, idx }: {
  d: { preview: string; larguraPx: number; matches: ScanResult[] };
  idx: number;
}) {
  const [aberta, setAberta] = useState(false);
  const melhor = d.matches[0];
  const identificada = melhor && melhor.score >= THRESH;
  const pequena = d.larguraPx > 0 && d.larguraPx < LARGURA_MINIMA;
  return (
    <div className={`bg-white rounded-xl border p-3 transition-colors ${aberta ? 'border-indigo-300 ring-1 ring-indigo-100' : 'border-gray-200'}`}>
      <div className="flex items-center justify-between gap-2 mb-2">
        <h4 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
          Carta {idx + 1}
          {d.larguraPx > 0 && (
            <span className="text-[10px] font-mono text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">
              {d.larguraPx}px
            </span>
          )}
        </h4>
        {pequena && (
          <span className="text-[10px] text-amber-600 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full" title="Cartas pequenas perdem detalhe no match — aproxime a câmera">
            ⚠ carta pequena
          </span>
        )}
      </div>
      <div className="flex gap-3">
        {/* Thumbnail da carta croppada — clicável: abre os similares */}
        <button
          onClick={() => setAberta(!aberta)}
          title={aberta ? 'Fechar similares' : 'Ver cartas similares'}
          className={`relative w-20 h-28 bg-gray-100 rounded-lg overflow-hidden shrink-0 border-2 transition-colors ${
            aberta ? 'border-indigo-400' : 'border-transparent hover:border-indigo-300'
          }`}
        >
          <Image src={d.preview} alt={`Carta ${idx + 1}`} fill className="object-contain" unoptimized />
          <span className="absolute bottom-0 inset-x-0 text-[9px] text-center text-indigo-700 bg-indigo-50/90 py-0.5">
            {aberta ? '− fechar' : '▸ similares'}
          </span>
        </button>
        <div className="min-w-0 flex-1 space-y-1">
          {identificada ? (
            <>
              <div className="text-xs font-bold text-green-700">
                ✓ {melhor.card.n}
                <span className="ml-2 text-[10px] font-mono text-gray-400">
                  {(melhor.score * 100).toFixed(1)}%
                </span>
              </div>
              <div className="text-[10px] text-gray-500 font-mono truncate">
                {melhor.card.sn} · {melhor.card.num}
              </div>
              <div className="flex flex-wrap gap-1 pt-0.5">
                {d.matches.slice(1, 3).map((r) => (
                  <span key={r.card.id} className="text-[10px] text-gray-400">
                    #{r.rank} {r.card.n} ({(r.score * 100).toFixed(0)}%)
                  </span>
                ))}
              </div>
              <button
                onClick={() => setAberta(!aberta)}
                className="inline-flex items-center gap-1 text-[10px] text-indigo-600 hover:underline"
              >
                {aberta ? '− Ocultar similares' : `▸ Ver ${d.matches.length} cartas similares`}
              </button>
            </>
          ) : (
            <div className="text-xs text-amber-700">
              ⚠ Não identificada (melhor match {(melhor ? melhor.score * 100 : 0).toFixed(1)}% &lt; 55%)
              <div className="text-[10px] text-gray-400 mt-0.5">
                Aproxime a câmera ou escaneie esta carta separadamente.
              </div>
              <button
                onClick={() => setAberta(!aberta)}
                className="inline-flex items-center gap-1 text-[10px] text-indigo-600 hover:underline mt-1"
              >
                {aberta ? '− Ocultar' : '▸ Ver candidatos mesmo assim'}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Lista de cartas similares (top-5 do match desta região) */}
      {aberta && (
        <div className="mt-3 pt-3 border-t border-gray-100 space-y-2">
          <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">
            Cartas similares à carta {idx + 1}
          </p>
          {d.matches.map((r) => (
            <CardResult key={r.card.id} card={r.card} score={r.score} rank={r.rank} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function Scanner() {
  const [phase, setPhase] = useState<'idle' | 'loading' | 'ready' | 'scanning' | 'error'>('idle');
  const [progress, setProgress] = useState(0);
  const [progressLabel, setProgressLabel] = useState('');
  const [results, setResults] = useState<ScanResult[] | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [clippedPreview, setClippedPreview] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [cardCount, setCardCount] = useState(0);
  const [clipped, setClipped] = useState<boolean | null>(null);

  // Multi-carta (Fase 1): uma detecção por quadrilátero encontrado
  const [deteccoes, setDeteccoes] = useState<{
    preview: string;
    larguraPx: number;
    matches: ScanResult[];
  }[] | null>(null);

  // Busca por texto (independe do scanner/modelo)
  const [textQuery, setTextQuery] = useState('');
  const [textResults, setTextResults] = useState<any[] | null>(null);
  const [textTotal, setTextTotal] = useState(0);
  const [textLoading, setTextLoading] = useState(false);

  // Auto crop (OpenCV)
  const [autoCrop, setAutoCrop] = useState(true);

  const loadRef = useRef<Promise<void> | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Cleanup preview URL
  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  // Busca por texto com debounce — procura em nome, número, coleção, id e raridade
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const q = textQuery.trim();
    if (q.length < 2) {
      setTextResults(null);
      setTextTotal(0);
      return;
    }
    setTextLoading(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const cards = await loadCards();
        const ql = q.toLowerCase();
        const hits: { c: any; rank: number }[] = [];
        for (const c of cards.values()) {
          const rk = rankCard(c, ql);
          if (rk >= 0) hits.push({ c, rank: rk });
        }
        hits.sort((a, b) => a.rank - b.rank);
        setTextTotal(hits.length);
        setTextResults(hits.slice(0, 10).map(h => h.c));
      } catch (e) {
        console.error('Busca por texto falhou:', e);
        setTextResults([]);
        setTextTotal(0);
      } finally {
        setTextLoading(false);
      }
    }, 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [textQuery]);

  const startLoad = useCallback(async () => {
    if (loadRef.current) return;
    setPhase('loading');
    setErrorMsg(null);
    setProgress(0);
    const engine = ScannerEngine.instance;
    loadRef.current = engine.load((pct, label) => {
      setProgress(pct);
      setProgressLabel(label);
    }).then(() => {
      setCardCount(engine.cardCount);
      setPhase('ready');
    }).catch((err) => {
      console.error(err);
      setErrorMsg('Falha ao carregar o scanner. Verifique sua conexão e tente novamente.');
      setPhase('error');
    }).finally(() => {
      loadRef.current = null;
    });
    return loadRef.current;
  }, []);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (e) => {
      const dataUrl = e.target?.result as string;
      setPreview(dataUrl);
      setClippedPreview(null);
      setResults(null);
      setDeteccoes(null);
      // BUG 3 (QA rodada 3): limpa a busca por texto — senão o resultado do
      // scan fica invisível atrás de 'Resultado da busca'
      setTextQuery('');
      setTextResults(null);
      setTextTotal(0);
      setErrorMsg(null);
      setClipped(null);
      setPhase('scanning');

      try {
        const engine = ScannerEngine.instance;

        // 1. Clipping (OpenCV) — detecta N cartas se o auto crop estiver ligado
        let quads: { points: { x: number; y: number }[]; area: number }[] = [];
        if (autoCrop) {
          try {
            const imgEl = await loadImage(dataUrl);
            quads = await detectCardQuads(imgEl, 10);
            setClipped(quads.length > 0);
          } catch (clipErr) {
            console.warn('Clipping falhou, usando imagem original:', clipErr);
            setClipped(false);
          }
        }

        // 2. Para cada carta detectada: warp + match. Sem detecção → imagem crua.
        const regioes: { preview: string; larguraPx: number; origem: string }[] = [];
        if (quads.length > 0) {
          const imgEl = await loadImage(dataUrl);
          for (const quad of quads) {
            const canvas = await warpCard(imgEl, quad);
            regioes.push({
              preview: canvas.toDataURL('image/jpeg', 0.92),
              // largura da carta na foto (px) — aviso se pequena
              larguraPx: Math.max(
                Math.hypot(quad.points[1].x - quad.points[0].x, quad.points[1].y - quad.points[0].y),
                Math.hypot(quad.points[2].x - quad.points[1].x, quad.points[2].y - quad.points[1].y),
              ),
              origem: 'clip',
            });
          }
        } else {
          regioes.push({ preview: dataUrl, larguraPx: 0, origem: 'crua' });
        }

        // 3. Match de cada região (sequencial — evita pico de memória)
        const deteccoes = [];
        for (let i = 0; i < regioes.length; i++) {
          const reg = regioes[i];
          const top = await engine.search(reg.preview, 5);
          deteccoes.push({ preview: reg.preview, larguraPx: reg.larguraPx, matches: top });
        }
        setDeteccoes(deteccoes);
        // compat: fluxo de 1 carta usa o primeiro resultado
        if (deteccoes.length === 1) {
          setResults(deteccoes[0].matches);
          setClippedPreview(regioes[0].origem === 'clip' ? regioes[0].preview : null);
        }
      } catch (err) {
        console.error(err);
        setErrorMsg('Falha ao analisar a imagem.');
      } finally {
        setPhase('ready');
      }
    };
    reader.onerror = () => {
      setErrorMsg('Falha ao ler o arquivo de imagem.');
      setPhase('ready');
    };
    reader.readAsDataURL(file);
  }, [autoCrop]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': [] },
    multiple: false,
    disabled: phase !== 'ready',
  });

  // Resultados ativos: busca por texto tem prioridade visual
  const mostrandoTexto = textResults !== null;
  const mostrandoResultados = mostrandoTexto ? textResults! : results;

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      {/* Status / Progress */}
      <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Search className="w-5 h-5 text-indigo-600" />
            Scanner
          </h2>
          <span className={`px-3 py-1 rounded-full text-xs font-medium uppercase tracking-wide ${
            phase === 'ready' ? 'bg-green-100 text-green-700' :
            phase === 'error' ? 'bg-red-100 text-red-700' :
            phase === 'scanning' ? 'bg-amber-100 text-amber-700' :
            'bg-indigo-100 text-indigo-700'
          }`}>
            {phase === 'idle' ? 'Descarregado' : phase === 'loading' ? 'Carregando' : phase === 'ready' ? 'Pronto' : phase === 'scanning' ? 'Analisando' : 'Erro'}
          </span>
        </div>

        {phase === 'idle' && (
          <div className="space-y-4">
            <div className="text-sm text-gray-600 leading-relaxed">
              O scanner roda 100% no seu navegador (nada é enviado a servidores). Para usar, é preciso
              baixar <strong>~53 MB</strong> na primeira vez (modelo de visão, detector de bordas e índice de
              20.4 mil cartas). Depois disso, tudo fica em cache.
            </div>
            <button
              onClick={startLoad}
              className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-medium px-5 py-2.5 rounded-xl transition-colors"
            >
              <Download className="w-4 h-4" />
              Carregar scanner (~40 MB)
            </button>
          </div>
        )}

        {phase === 'loading' && (
          <div className="space-y-2">
            <div className="flex justify-between text-sm text-gray-500">
              <span>{progressLabel}</span>
              <span>{Math.round(progress)}%</span>
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-indigo-600 transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {phase === 'ready' && (
          <div className="flex items-center gap-2 text-sm text-green-600">
            <CheckCircle2 className="w-4 h-4" />
            Scanner pronto. Índice com {cardCount.toLocaleString('pt-BR')} cartas.
          </div>
        )}

        {clipped !== null && phase === 'ready' && (
          <div className={`mt-3 text-xs px-3 py-2 rounded-lg ${
            clipped ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'
          }`}>
            {clipped
              ? '✓ Carta detectada: bordas encontradas e perspectiva corrigida antes do match.'
              : '⚠ Carta não detectada: usando a imagem original (fundo incluso).'}
          </div>
        )}

        {phase === 'error' && (
          <div className="flex items-center gap-2 text-sm text-red-600">
            <AlertCircle className="w-4 h-4" />
            {errorMsg}
            <button onClick={startLoad} className="ml-2 text-indigo-600 hover:underline font-medium">
              Tentar novamente
            </button>
          </div>
        )}

        {/* Auto crop (OpenCV) */}
        <div className="mt-4 pt-4 border-t border-gray-100">
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            Pré-processamento da imagem
          </div>
          <div className="flex flex-col sm:flex-row gap-2 sm:gap-4">
            <label className="inline-flex items-center gap-2 text-sm cursor-pointer min-w-0">
              <input
                type="radio"
                checked={autoCrop}
                onChange={() => setAutoCrop(true)}
                className="accent-indigo-600 shrink-0"
              />
              <span className="text-gray-700">Auto crop (OpenCV)</span>
              <span className="hidden lg:inline text-xs text-gray-400">detecta bordas e corrige perspectiva</span>
            </label>
            <label className="inline-flex items-center gap-2 text-sm cursor-pointer min-w-0">
              <input
                type="radio"
                checked={!autoCrop}
                onChange={() => setAutoCrop(false)}
                className="accent-indigo-600 shrink-0"
              />
              <span className="text-gray-700">Imagem original</span>
              <span className="hidden lg:inline text-xs text-gray-400">sem transformações</span>
            </label>
          </div>
        </div>
      </div>

      {/* Barra de busca por texto — funciona sem carregar o scanner */}
      <div className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100">
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <Type className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              value={textQuery}
              onChange={e => setTextQuery(e.target.value)}
              placeholder="Buscar carta por nome, número, coleção, raridade ou id..."
              className="w-full pl-9 pr-9 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            {textQuery && (
              <button
                onClick={() => setTextQuery('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                title="Limpar busca"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
          {textLoading && <Loader2 className="w-4 h-4 text-indigo-500 animate-spin" />}
        </div>
        {textTotal > 0 && (
          <div className="text-xs text-gray-500 mt-2">
            {textTotal.toLocaleString('pt-BR')} carta{textTotal !== 1 ? 's' : ''} encontrada{textTotal !== 1 ? 's' : ''}
            {textTotal > 10 && ' — mostrando as 10 primeiras'}
          </div>
        )}
      </div>

      <div className="grid md:grid-cols-2 gap-8">
        {/* Upload Area */}
        <div className="space-y-4">
          <div
            {...getRootProps()}
            className={`
              relative aspect-square rounded-2xl border-2 border-dashed transition-all cursor-pointer flex flex-col items-center justify-center p-8 text-center
              ${isDragActive ? 'border-indigo-500 bg-indigo-50' : 'border-gray-200 hover:border-indigo-300 hover:bg-gray-50'}
              ${phase !== 'ready' ? 'opacity-50 cursor-not-allowed' : ''}
            `}
          >
            <input {...getInputProps()} />

            {preview ? (
              <div className="w-full h-full grid grid-cols-2 gap-2 p-4">
                <div className="relative flex flex-col min-h-0">
                  <Image src={preview} alt="Foto original" fill className="object-contain" unoptimized />
                  <span className="absolute bottom-0 inset-x-0 text-[10px] text-center text-gray-500 bg-white/80 py-0.5">
                    Original
                  </span>
                </div>
                <div className="relative flex flex-col min-h-0">
                  {clippedPreview ? (
                    <>
                      <Image src={clippedPreview} alt="Após clipping" fill className="object-contain" unoptimized />
                      <span className="absolute bottom-0 inset-x-0 text-[10px] text-center text-emerald-700 bg-emerald-50/90 py-0.5">
                        Após clipping
                      </span>
                    </>
                  ) : (
                    <>
                      <div className="w-full h-full flex items-center justify-center text-gray-300">
                        <ImageOff className="w-8 h-8" />
                      </div>
                      <span className="absolute bottom-0 inset-x-0 text-[10px] text-center text-gray-400 bg-white/80 py-0.5">
                        {autoCrop ? 'Sem clipping' : 'Auto crop desligado'}
                      </span>
                    </>
                  )}
                </div>
              </div>
            ) : (
              <>
                <div className="w-16 h-16 bg-indigo-100 text-indigo-600 rounded-full flex items-center justify-center mb-4">
                  <Camera className="w-8 h-8" />
                </div>
                <p className="font-medium text-gray-900">Envie a foto de uma carta</p>
                <p className="text-sm text-gray-500 mt-1">ou clique para escolher o arquivo</p>
              </>
            )}

            {phase === 'scanning' && (
              <div className="absolute inset-0 bg-white/80 backdrop-blur-sm flex items-center justify-center rounded-2xl">
                <div className="flex flex-col items-center gap-3">
                  <Loader2 className="w-8 h-8 text-indigo-600 animate-spin" />
                  <span className="font-medium text-indigo-900">Analisando...</span>
                </div>
              </div>
            )}
          </div>

          <p className="text-xs text-center text-gray-400">
            JPG, PNG. Para melhores resultados, use uma imagem clara de uma única carta.
          </p>
        </div>

        {/* Results Area — busca por texto tem prioridade; senão, resultados do scanner */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900">
              {mostrandoTexto ? 'Resultado da busca' : 'Resultado'}
            </h3>
            {mostrandoTexto && textResults && textResults.length > 0 && (
              <button
                onClick={() => setTextQuery('')}
                className="text-xs text-indigo-600 hover:underline inline-flex items-center gap-1"
              >
                <X className="w-3 h-3" /> voltar ao scanner
              </button>
            )}
          </div>

          {mostrandoTexto ? (
            <div className="space-y-3">
              {(textResults as any[]).map((c, i) => (
                <CardResult key={c.id} card={c} rank={i + 1} />
              ))}
            </div>
          ) : deteccoes && deteccoes.length > 0 ? (
            /* Multi-carta: um card por detecção */
            <div className="space-y-3">
              {deteccoes.map((d, i) => (
                <DeteccaoCard key={i} d={d} idx={i} />
              ))}
            </div>
          ) : mostrandoResultados && mostrandoResultados.length > 0 ? (
            <div className="space-y-3">
              {(results as ScanResult[]).map((r) => (
                <CardResult key={r.card.id} card={r.card} score={r.score} rank={r.rank} />
              ))}
            </div>
          ) : mostrandoTexto && textQuery.trim().length >= 2 ? (
            <div className="h-full min-h-[300px] flex flex-col items-center justify-center text-gray-400 border border-gray-100 rounded-2xl bg-gray-50">
              <Search className="w-12 h-12 mb-3 opacity-20" />
              <p>Nenhuma carta encontrada para "{textQuery.trim()}"</p>
            </div>
          ) : preview ? (
            <div className="h-full min-h-[300px] flex flex-col items-center justify-center text-gray-400 border border-gray-100 rounded-2xl bg-gray-50">
              <Search className="w-12 h-12 mb-3 opacity-20" />
              <p>Nenhum resultado encontrado</p>
            </div>
          ) : (
            <div className="h-full min-h-[300px] flex flex-col items-center justify-center text-gray-400 border border-gray-100 rounded-2xl bg-gray-50">
              <Search className="w-12 h-12 mb-3 opacity-20" />
              <p>Nenhuma carta escaneada ainda</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
