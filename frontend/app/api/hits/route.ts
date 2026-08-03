import { NextResponse } from 'next/server';
import { readFileSync, readdirSync, statSync } from 'fs';
import { join } from 'path';

export const dynamic = 'force-dynamic';

interface ScoredCard {
  nome: string;
  sigla: string;
  real: number;
  pred: number;
  upside: number;
  oportunidade: string;
  iCO: number;
  moeda: string;
  liga_id: string;
  nEN: string;
}

export async function GET() {
  try {
    const scoredDir = join(process.cwd(), '..', 'data', 'scored');
    const files = readdirSync(scoredDir)
      .filter(f => f.startsWith('scored_hits_') && f.endsWith('.csv'))
      .sort()
      .reverse();

    if (files.length === 0) {
      return NextResponse.json({ error: 'Nenhum arquivo de hits escorados encontrado' }, { status: 404 });
    }

    const latestFile = join(scoredDir, files[0]);
    const raw = readFileSync(latestFile, 'utf-8');
    const stats = statSync(latestFile);

    // Parse CSV manual (sem dependência extra)
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
      .filter(r => r.oportunidade && r.real_ref && r.pred_ref)
      .map(r => ({
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
      .sort((a, b) => b.upside - a.upside);

    const subvalorizadas = cards.filter(c => c.oportunidade === '🔥 Subvalorizada' && c.real >= 5);
    const inflacionadas = cards.filter(c => c.oportunidade === '💀 Inflacionada')
      .sort((a, b) => a.upside - b.upside);

    return NextResponse.json({
      arquivo: files[0],
      ultimaAtualizacao: stats.mtime.toISOString(),
      total: cards.length,
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