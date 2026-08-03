import { NextResponse } from 'next/server';
import { readFileSync, readdirSync, statSync } from 'fs';
import { join } from 'path';

export const dynamic = 'force-dynamic';

function parseScoredCSV(filePath: string) {
  const raw = readFileSync(filePath, 'utf-8');
  const lines = raw.trim().split('\n');
  if (lines.length < 2) return [];
  const headers = lines[0].split(',');

  return lines.slice(1).map(line => {
    const vals = line.split(',');
    const rec: any = {};
    headers.forEach((h, j) => { rec[h.trim()] = vals[j]?.trim(); });
    return rec;
  })
  .filter((r: any) => r.oportunidade && r.real_ref && r.pred_ref)
  .map((r: any) => ({
    nome: r.nPT || r.name || r.nome || r.nEN || 'Unknown',
    sigla: r.sSigla || r.set_id || '',
    real: parseFloat(r.real_ref),
    pred: parseFloat(r.pred_ref),
    upside: parseFloat(r.upside_pct),
    oportunidade: r.oportunidade,
    iCO: parseInt(r.iCO || '0', 10),
    moeda: r.moeda || 'R$',
    liga_id: r.liga_id || '',
    nEN: r.nEN || '',
    fonte: r.fonte || '',
  }))
  .filter((c: any) => !Number.isNaN(c.upside) && !Number.isNaN(c.real));
}

export async function GET() {
  try {
    const scoredDir = join(process.cwd(), '..', 'data', 'scored');

    // Latest hits
    const hitsFiles = readdirSync(scoredDir)
      .filter(f => f.startsWith('scored_hits_') && f.endsWith('.csv'))
      .sort().reverse();

    // Latest snapshot
    const snapFiles = readdirSync(scoredDir)
      .filter(f => f.startsWith('scored_snapshot_') && f.endsWith('.csv'))
      .sort().reverse();

    const hitsData = hitsFiles.length > 0
      ? parseScoredCSV(join(scoredDir, hitsFiles[0]))
      : [];
    const snapData = snapFiles.length > 0
      ? parseScoredCSV(join(scoredDir, snapFiles[0]))
      : [];

    const hitsMeta = hitsFiles[0] ? {
      arquivo: hitsFiles[0],
      data: statSync(join(scoredDir, hitsFiles[0])).mtime.toISOString(),
    } : null;

    const snapMeta = snapFiles[0] ? {
      arquivo: snapFiles[0],
      data: statSync(join(scoredDir, snapFiles[0])).mtime.toISOString(),
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