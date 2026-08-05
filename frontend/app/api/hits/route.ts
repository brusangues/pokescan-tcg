import { NextResponse } from 'next/server';
import { readdirSync, statSync } from 'fs';
import { parseScoredCSV } from '@/app/lib/scored';
import { SCORED_DIR } from '@/app/lib/paths';

export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const selected = searchParams.get('arquivo');
    const scoredDir = SCORED_DIR;

    const files = readdirSync(scoredDir)
      .filter(f => f.startsWith('scored_hits_') && f.endsWith('.csv'))
      .sort()
      .reverse();

    if (files.length === 0) {
      return NextResponse.json({ error: 'Nenhum arquivo de hits escorados encontrado' }, { status: 404 });
    }

    // Se não especificou, usa o mais recente
    const target = selected && files.includes(selected) ? selected : files[0];
    const latestFile = `${scoredDir}/${target}`;
    const stats = statSync(latestFile);

    // Lista de arquivos disponíveis, agrupados por dia
    const dias: { data: string; label: string; arquivos: string[] }[] = [];
    const diaMap = new Map<string, string[]>();

    for (const f of files) {
      const m = f.match(/scored_hits_(\d{8})_(\d{6})\.csv/);
      if (!m) continue;
      const data = m[1]; // YYYYMMDD
      if (!diaMap.has(data)) diaMap.set(data, []);
      diaMap.get(data)!.push(f);
    }

    for (const [data, arquivos] of diaMap) {
      const ano = data.slice(0, 4);
      const mes = data.slice(4, 6);
      const dia = data.slice(6, 8);
      dias.push({
        data,
        label: `${dia}/${mes}/${ano}`,
        arquivos: arquivos.sort().reverse(),
      });
    }

    // Parse CSV (usa csv-parse que respeita aspas e vírgulas internas)
    const cards = parseScoredCSV(latestFile)
      .sort((a: any, b: any) => b.upside - a.upside);

    const subvalorizadas = cards.filter((c: any) => c.oportunidade === '🔥 Subvalorizada' && c.real >= 5);
    const inflacionadas = cards.filter((c: any) => c.oportunidade === '💀 Inflacionada')
      .sort((a: any, b: any) => a.upside - b.upside);

    return NextResponse.json({
      arquivo: target,
      ultimaAtualizacao: stats.mtime.toISOString(),
      total: cards.length,
      dias,
      subvalorizadas,
      inflacionadas: inflacionadas.slice(0, 20),
      todas: cards,
    });
  } catch (error) {
    return NextResponse.json({
      error: error instanceof Error ? error.message : 'Erro ao ler dados'
    }, { status: 500 });
  }
}