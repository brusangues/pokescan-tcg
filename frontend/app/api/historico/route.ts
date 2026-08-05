import { NextResponse } from 'next/server';
import { readFileSync, readdirSync } from 'fs';
import { join } from 'path';
import { parseScoredCSV } from '@/app/lib/scored';

export const dynamic = 'force-dynamic';

/**
 * Histórico de preços por carta (time series).
 * Lê todos os CSVs escorados (hits diários + snapshots semanais) e
 * agrega por liga_id: { data, real, pred, moeda, tipo } ordenado por data.
 *
 * Query: ?nome=...&sigla=... (busca por nEN ou liga_id)
 *        ?liga_id=SV4M-84   (busca exata — preferida pelo /card)
 *        ?limite=30          (máx pontos retornados, default 60)
 */
export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const ligaId = searchParams.get('liga_id')?.trim();
    const nome = searchParams.get('nome')?.trim().toLowerCase() || '';
    const sigla = searchParams.get('sigla')?.trim().toUpperCase() || '';
    const limite = parseInt(searchParams.get('limite') || '60', 10) || 60;

    const scoredDir = join(process.cwd(), '..', 'data', 'scored');
    const files = readdirSync(scoredDir)
      .filter(f => /^scored_(hits|snapshot)_\d{8}_\d{6}\.csv$/.test(f))
      .sort();

    // key: data (YYYYMMDD) -> ponto de histórico (pega o último do dia)
    const pontos = new Map<string, any>();

    for (const f of files) {
      const m = f.match(/^scored_(hits|snapshot)_(\d{8})_(\d{6})\.csv$/);
      if (!m) continue;
      const tipo = m[1];
      const data = m[2];
      const dataISO = `${data.slice(0, 4)}-${data.slice(4, 6)}-${data.slice(6, 8)}`;

      let cards: any[];
      try {
        cards = parseScoredCSV(join(scoredDir, f));
      } catch {
        continue; // CSV corrompido/incompleto — pula
      }

      for (const c of cards) {
        // Filtro: liga_id exato OU (nome contém AND sigla igual)
        const matchLiga = ligaId && c.liga_id === ligaId;
        const matchNome = !ligaId && nome && (c.nEN || c.nome || '').toLowerCase().includes(nome) &&
          (sigla ? c.sigla === sigla : true);
        if (!matchLiga && !matchNome) continue;

        if (!c.real || c.real <= 0) continue; // só pontos com preço real

        const key = `${data}_${tipo}`;
        pontos.set(key, {
          data: dataISO,
          real: Math.round(c.real * 100) / 100,
          pred: c.pred ? Math.round(c.pred * 100) / 100 : null,
          moeda: c.moeda || 'R$',
          tipo,
        });
      }
    }

    let serie = [...pontos.values()].sort((a, b) => a.data.localeCompare(b.data));
    // Últimos N pontos (limite)
    if (serie.length > limite) {
      serie = serie.slice(-limite);
    }

    if (serie.length === 0) {
      return NextResponse.json({ serie: [], total: 0 });
    }

    return NextResponse.json({
      serie,
      total: serie.length,
      liga_id: ligaId || (sigla ? `${sigla}-` : ''),
    });
  } catch (error) {
    return NextResponse.json({
      error: error instanceof Error ? error.message : 'Erro ao ler histórico'
    }, { status: 500 });
  }
}
