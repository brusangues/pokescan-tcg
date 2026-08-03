import { NextResponse } from 'next/server';
import { readFileSync, readdirSync, statSync } from 'fs';
import { join } from 'path';

export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const selected = searchParams.get('arquivo');
    const scoredDir = join(process.cwd(), '..', 'data', 'scored');

    const files = readdirSync(scoredDir)
      .filter(f => f.startsWith('scored_hits_') && f.endsWith('.csv'))
      .sort()
      .reverse();

    if (files.length === 0) {
      return NextResponse.json({ error: 'Nenhum arquivo de hits escorados encontrado' }, { status: 404 });
    }

    // Se não especificou, usa o mais recente
    const target = selected && files.includes(selected) ? selected : files[0];
    const latestFile = join(scoredDir, target);
    const raw = readFileSync(latestFile, 'utf-8');
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

    // Parse CSV
    const lines = raw.trim().split('\n');
    const headers = lines[0].split(',');

    const records: any[] = [];
    for (let i = 1; i < lines.length; i++) {
      const vals = lines[i].split(',');
      const rec: any = {};
      headers.forEach((h, j) => { rec[h.trim()] = vals[j]?.trim(); });
      records.push(rec);
    }

    const cards = records
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
      }))
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