import { NextResponse } from 'next/server';
import { readFileSync, statSync } from 'fs';
import { parse } from 'csv-parse/sync';
import { DATA_DIR } from '@/app/lib/paths';

export const dynamic = 'force-dynamic';

const CSV_PATH = `${DATA_DIR}/features/predicoes_latest.csv`;

// Página de debug: desabilitada em produção a menos que NEXT_PUBLIC_FEATURES=1
const FEATURES_ENABLED = process.env.NEXT_PUBLIC_FEATURES === '1';

// Cache com invalidação por mtime (mesmo padrão do /api/card)
let _cache: { rows: any[]; cols: string[] } | null = null;
let _mtime = 0;

function load() {
  if (!FEATURES_ENABLED) return null;
  let mtime = 0;
  try {
    mtime = statSync(CSV_PATH).mtimeMs;
  } catch {
    return null; // CSV ainda não gerado
  }
  if (_cache && _mtime === mtime) return _cache;

  const raw = readFileSync(CSV_PATH, 'utf-8');
  const records = parse(raw, { columns: true, skip_empty_lines: true, relax_column_count: true, trim: true });
  const cols = records.length > 0 ? Object.keys(records[0]) : [];
  _cache = { rows: records, cols };
  _mtime = mtime;
  return _cache;
}

export async function GET(request: Request) {
  if (!FEATURES_ENABLED) {
    return NextResponse.json(
      { error: 'Página de features desabilitada. Defina NEXT_PUBLIC_FEATURES=1 para habilitar.' },
      { status: 404 }
    );
  }

  try {
    const { searchParams } = new URL(request.url);
    const search = (searchParams.get('search') || '').toLowerCase().trim();
    const limit = Math.min(parseInt(searchParams.get('limit') || '100', 10) || 100, 500);
    const offset = Math.max(parseInt(searchParams.get('offset') || '0', 10) || 0, 0);

    const data = load();
    if (!data) {
      return NextResponse.json(
        { error: 'CSV de predições não gerado. Rode script/export_features.py primeiro.' },
        { status: 404 }
      );
    }

    let rows = data.rows;
    if (search) {
      rows = rows.filter((r: any) =>
        String(r.id || '').toLowerCase().includes(search) ||
        String(r.name || '').toLowerCase().includes(search) ||
        String(r.set_id || '').toLowerCase().includes(search)
      );
    }

    const total = rows.length;
    const page = rows.slice(offset, offset + limit);

    return NextResponse.json({
      total,
      offset,
      limit,
      cols: data.cols,
      rows: page,
      geradoEm: statSync(CSV_PATH).mtime.toISOString(),
    });
  } catch (error) {
    return NextResponse.json({
      error: error instanceof Error ? error.message : 'Erro ao ler features'
    }, { status: 500 });
  }
}
