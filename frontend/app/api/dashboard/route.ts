import { NextResponse } from 'next/server';
import { readdirSync, statSync } from 'fs';
import { parseScoredCSV } from '@/app/lib/scored';
import { SCORED_DIR } from '@/app/lib/paths';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const scoredDir = SCORED_DIR;

    // Latest hits
    const hitsFiles = readdirSync(scoredDir)
      .filter(f => f.startsWith('scored_hits_') && f.endsWith('.csv'))
      .sort().reverse();

    // Latest snapshot
    const snapFiles = readdirSync(scoredDir)
      .filter(f => f.startsWith('scored_snapshot_') && f.endsWith('.csv'))
      .sort().reverse();

    const hitsData = hitsFiles.length > 0
      ? parseScoredCSV(`${scoredDir}/${hitsFiles[0]}`)
      : [];
    const snapData = snapFiles.length > 0
      ? parseScoredCSV(`${scoredDir}/${snapFiles[0]}`)
      : [];

    const hitsMeta = hitsFiles[0] ? {
      arquivo: hitsFiles[0],
      data: statSync(`${scoredDir}/${hitsFiles[0]}`).mtime.toISOString(),
    } : null;

    const snapMeta = snapFiles[0] ? {
      arquivo: snapFiles[0],
      data: statSync(`${scoredDir}/${snapFiles[0]}`).mtime.toISOString(),
    } : null;

    const allCards = [...hitsData, ...snapData];

    // Distribuição de upside
    const buckets: Record<string, number> = {};
    allCards.forEach(c => {
      const u = Math.max(-500, Math.min(500, c.upside));
      const b = Math.floor(u / 10) * 10;
      const key = `${b} a ${b + 10}%`;
      buckets[key] = (buckets[key] || 0) + 1;
    });
    const distribuicao = Object.entries(buckets)
      .map(([range, count]) => ({ range, count }))
      .sort((a, b) => parseInt(a.range) - parseInt(b.range));

    // Top oportunidades
    const subHits = hitsData
      .filter(c => c.oportunidade === '🔥 Subvalorizada' && c.real >= 5)
      .sort((a, b) => b.upside - a.upside)
      .slice(0, 10);

    const subSnap = snapData
      .filter(c => c.oportunidade === '🔥 Subvalorizada' && c.real >= 5)
      .sort((a, b) => b.upside - a.upside)
      .slice(0, 10);

    const inflaHits = hitsData
      .filter(c => c.oportunidade === '💀 Inflacionada')
      .sort((a, b) => a.upside - b.upside)
      .slice(0, 10);

    const inflaSnap = snapData
      .filter(c => c.oportunidade === '💀 Inflacionada')
      .sort((a, b) => a.upside - b.upside)
      .slice(0, 10);

    // Por set (agrupa sigla)
    const setCounts: Record<string, number> = {};
    hitsData.forEach(c => {
      if (c.sigla) setCounts[c.sigla] = (setCounts[c.sigla] || 0) + 1;
    });
    const sets = Object.entries(setCounts)
      .map(([sigla, count]) => ({ sigla, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);

    return NextResponse.json({
      hits: {
        meta: hitsMeta,
        total: hitsData.length,
        subvalorizadas: hitsData.filter(c => c.oportunidade === '🔥 Subvalorizada' && c.real >= 5).length,
        inflacionadas: hitsData.filter(c => c.oportunidade === '💀 Inflacionada').length,
        justo: hitsData.filter(c => c.oportunidade === '⚖️ Preço Justo').length,
        topOportunidades: subHits,
        topInflacionadas: inflaHits,
      },
      snapshot: {
        meta: snapMeta,
        total: snapData.length,
        subvalorizadas: snapData.filter(c => c.oportunidade === '🔥 Subvalorizada').length,
        inflacionadas: snapData.filter(c => c.oportunidade === '💀 Inflacionada').length,
        topOportunidades: subSnap,
        topInflacionadas: inflaSnap,
      },
      distribuicao,
      sets,
    });
  } catch (error) {
    return NextResponse.json({
      error: error instanceof Error ? error.message : 'Erro ao ler dados'
    }, { status: 500 });
  }
}