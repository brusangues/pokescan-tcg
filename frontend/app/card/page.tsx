'use client';

import { useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import CardDetailContent from './CardDetailContent';

export default function CardDetailPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-slate-50 flex items-center justify-center"><div className="animate-spin w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full" /></div>}>
      <CardDetailContent />
    </Suspense>
  );
}