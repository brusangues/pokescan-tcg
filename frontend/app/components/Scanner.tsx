'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Camera, Loader2, Search, CheckCircle2, AlertCircle, Download, ExternalLink, ImageOff } from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import ScannerEngine, { ScanResult } from '@/app/lib/scannerEngine';
import Image from 'next/image';

export default function Scanner() {
  const [phase, setPhase] = useState<'idle' | 'loading' | 'ready' | 'scanning' | 'error'>('idle');
  const [progress, setProgress] = useState(0);
  const [progressLabel, setProgressLabel] = useState('');
  const [results, setResults] = useState<ScanResult[] | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [cardCount, setCardCount] = useState(0);
  const loadRef = useRef<Promise<void> | null>(null);

  // Cleanup preview URL
  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

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
      setResults(null);
      setErrorMsg(null);
      setPhase('scanning');

      try {
        const engine = ScannerEngine.instance;
        const top = await engine.search(dataUrl, 5);
        setResults(top);
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
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': [] },
    multiple: false,
    disabled: phase !== 'ready',
  });

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
              baixar <strong>~40 MB</strong> na primeira vez (modelo de visão + índice de 20.4 mil cartas).
              Depois disso, tudo fica em cache.
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

        {phase === 'error' && (
          <div className="flex items-center gap-2 text-sm text-red-600">
            <AlertCircle className="w-4 h-4" />
            {errorMsg}
            <button onClick={startLoad} className="ml-2 text-indigo-600 hover:underline font-medium">
              Tentar novamente
            </button>
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
              <Image src={preview} alt="Preview" fill className="object-contain p-4" unoptimized />
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

        {/* Results Area */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-900">Resultado</h3>
          {results && results.length > 0 ? (
            <div className="space-y-3">
              {results.map((r) => (
                <div
                  key={r.card.id}
                  className={`flex gap-4 bg-white rounded-xl border p-4 ${
                    r.rank === 1 ? 'border-indigo-300 ring-1 ring-indigo-100' : 'border-gray-100 opacity-90'
                  }`}
                >
                  <div className="relative w-20 h-28 bg-gray-100 rounded-lg overflow-hidden shrink-0">
                    {r.card.img ? (
                      <Image src={r.card.img} alt={r.card.n} fill className="object-contain" unoptimized />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-gray-300">
                        <ImageOff className="w-6 h-6" />
                      </div>
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <h4 className="font-bold text-gray-900 truncate">{r.card.n}</h4>
                      <span className={`text-xs font-mono px-2 py-0.5 rounded-full shrink-0 ${
                        r.rank === 1 ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-600'
                      }`}>
                        {r.rank === 1 ? '✓ Melhor' : `#${r.rank}`} · {(r.score * 100).toFixed(1)}%
                      </span>
                    </div>
                    <p className="text-sm text-gray-500 truncate">
                      {r.card.sn} · {r.card.num}
                    </p>
                    <div className="flex items-center justify-between mt-2 text-sm">
                      <span className="text-xs text-gray-400">{r.card.r || '—'}</span>
                      {r.card.p != null && (
                        <span className="font-medium text-emerald-600">${r.card.p.toFixed(2)}</span>
                      )}
                    </div>
                    <a
                      href={`https://www.tcgplayer.com/search/pokemon/productname=${encodeURIComponent(r.card.n)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 mt-2 text-xs text-indigo-600 hover:underline"
                    >
                      <ExternalLink className="w-3 h-3" /> Ver no TCGplayer
                    </a>
                  </div>
                </div>
              ))}
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
