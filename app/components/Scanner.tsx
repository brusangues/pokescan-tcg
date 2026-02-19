
'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Upload, Camera, Loader2, Search, CheckCircle2, AlertCircle } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { useDropzone } from 'react-dropzone';
import PipelineSingleton from '@/app/lib/pipeline';
import { fetchCards, PokemonCard } from '@/app/lib/pokemon';
import CardDisplay from './CardDisplay';
import Image from 'next/image';

// Helper for cosine similarity
function cosineSimilarity(a: number[], b: number[]) {
  let dotProduct = 0;
  let magnitudeA = 0;
  let magnitudeB = 0;
  for (let i = 0; i < a.length; i++) {
    dotProduct += a[i] * b[i];
    magnitudeA += a[i] * a[i];
    magnitudeB += b[i] * b[i];
  }
  magnitudeA = Math.sqrt(magnitudeA);
  magnitudeB = Math.sqrt(magnitudeB);
  if (magnitudeA === 0 || magnitudeB === 0) return 0;
  return dotProduct / (magnitudeA * magnitudeB);
}

export default function Scanner() {
  const [status, setStatus] = useState<'idle' | 'loading_model' | 'indexing' | 'ready' | 'scanning' | 'error'>('idle');
  const [progress, setProgress] = useState(0);
  const [cards, setCards] = useState<PokemonCard[]>([]);
  const [embeddings, setEmbeddings] = useState<number[][]>([]);
  const [matchedCard, setMatchedCard] = useState<{ card: PokemonCard; score: number } | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Load model and index cards on mount
  useEffect(() => {
    async function init() {
      try {
        setStatus('loading_model');
        // 1. Load Model
        const pipeline = await PipelineSingleton.getInstance((data: any) => {
           if (data.status === 'progress') {
             // Model loading progress if needed
           }
        });

        setStatus('indexing');
        // 2. Fetch Cards (Base Set 151 for demo)
        // Fetching a small subset to keep it fast in browser
        const fetchedCards = await fetchCards('q=set.id:base1&pageSize=15'); 
        setCards(fetchedCards);

        // 3. Generate Embeddings for the "Index"
        const newEmbeddings: number[][] = [];
        const total = fetchedCards.length;
        
        for (let i = 0; i < total; i++) {
          const card = fetchedCards[i];
          setProgress(Math.round(((i + 1) / total) * 100));
          
          // Embed the card image
          // We use the small image for speed
          const output = await pipeline(card.images.small);
          newEmbeddings.push(Array.from(output.data));
          
          // Small delay to allow UI updates
          await new Promise(r => setTimeout(r, 10));
        }
        
        setEmbeddings(newEmbeddings);
        setStatus('ready');
      } catch (err) {
        console.error(err);
        setStatus('error');
        setErrorMsg('Failed to initialize AI model or fetch cards.');
      }
    }

    init();
  }, []);

  // Cleanup preview URL
  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (!file) return;

    const objectUrl = URL.createObjectURL(file);
    setPreview(objectUrl);
    setMatchedCard(null);
    setStatus('scanning');

    try {
      const pipeline = await PipelineSingleton.getInstance();
      const output = await pipeline(objectUrl);
      const queryEmbedding = Array.from(output.data) as number[];

      // Find best match
      let bestScore = -1;
      let bestIndex = -1;

      embeddings.forEach((emb, idx) => {
        const score = cosineSimilarity(queryEmbedding, emb);
        if (score > bestScore) {
          bestScore = score;
          bestIndex = idx;
        }
      });

      if (bestIndex !== -1) {
        setMatchedCard({
          card: cards[bestIndex],
          score: bestScore
        });
      }
    } catch (err) {
      console.error(err);
      setErrorMsg('Failed to scan image.');
    } finally {
      setStatus('ready');
    }
  }, [cards, embeddings]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ 
    onDrop,
    accept: {'image/*': []},
    multiple: false,
    disabled: status !== 'ready'
  });

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Status / Progress */}
      <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Search className="w-5 h-5 text-indigo-600" />
            Scanner Status
          </h2>
          <span className={`px-3 py-1 rounded-full text-xs font-medium uppercase tracking-wide ${
            status === 'ready' ? 'bg-green-100 text-green-700' : 
            status === 'error' ? 'bg-red-100 text-red-700' :
            'bg-indigo-100 text-indigo-700'
          }`}>
            {status.replace('_', ' ')}
          </span>
        </div>

        {status === 'indexing' && (
          <div className="space-y-2">
            <div className="flex justify-between text-sm text-gray-500">
              <span>Indexing Base Set Cards...</span>
              <span>{progress}%</span>
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <motion.div 
                className="h-full bg-indigo-600"
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {status === 'loading_model' && (
           <div className="flex items-center gap-2 text-sm text-gray-500">
             <Loader2 className="w-4 h-4 animate-spin" />
             Loading AI Vision Model (approx. 50MB)...
           </div>
        )}

        {status === 'ready' && (
          <div className="flex items-center gap-2 text-sm text-green-600">
            <CheckCircle2 className="w-4 h-4" />
            System ready. Index contains {cards.length} cards.
          </div>
        )}
        
        {errorMsg && (
          <div className="flex items-center gap-2 text-sm text-red-600 mt-2">
            <AlertCircle className="w-4 h-4" />
            {errorMsg}
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
              ${status !== 'ready' ? 'opacity-50 cursor-not-allowed' : ''}
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
                <p className="font-medium text-gray-900">Drop a card image here</p>
                <p className="text-sm text-gray-500 mt-1">or click to upload</p>
              </>
            )}

            {status === 'scanning' && (
              <div className="absolute inset-0 bg-white/80 backdrop-blur-sm flex items-center justify-center rounded-2xl">
                <div className="flex flex-col items-center gap-3">
                  <Loader2 className="w-8 h-8 text-indigo-600 animate-spin" />
                  <span className="font-medium text-indigo-900">Analyzing...</span>
                </div>
              </div>
            )}
          </div>
          
          <p className="text-xs text-center text-gray-400">
            Supports JPG, PNG. For best results, use a clear image of a single card.
          </p>
        </div>

        {/* Results Area */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-900">Match Result</h3>
          <AnimatePresence mode="wait">
            {matchedCard ? (
              <motion.div
                key="result"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
              >
                <CardDisplay card={matchedCard.card} similarity={matchedCard.score} />
              </motion.div>
            ) : (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="h-full min-h-[300px] flex flex-col items-center justify-center text-gray-400 border border-gray-100 rounded-2xl bg-gray-50"
              >
                <Search className="w-12 h-12 mb-3 opacity-20" />
                <p>No card scanned yet</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
