import { NextResponse } from 'next/server';
import { readdirSync, statSync } from 'fs';
import { join } from 'path';
import { parseScoredCSV } from '@/app/lib/scored';

export const dynamic = 'force-dynamic';

interface ArquivoDisponivel {
  arquivo: string;
  label: string;
  data: string;
  cartas: number;
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const selected = searchParams.get('arquivo');
    const scoredDir = join(process.cwd(), '..', 'data', 'scored');

    const files = readdirSync(scoredDir)
      .filter(f => f.startsWith('scored_snapshot_') && f.endsWith('.csv'))
      .sort()
      .reverse();

    if (files.length === 0) {
      return NextResponse.json({ error: 'Nenhum arquivo de snapshot escorado encontrado' }, { status: 404 });
    }

    // Lista de arquivos disponíveis com preview de quantas cartas
    const disponiveis: ArquivoDisponivel[] = [];
    for (const f of files) {
      const m = f.match(/scored_snapshot_(\d{8})_(\d{6})\.csv/);
      if (!m) continue;
      const data = m[1];
      const ano = data.slice(0, 4);
      const mes = data.slice(4, 6);
      const dia = data.slice(6, 8);
      const time = `${m[2].slice(0, 2)}:${m[2].slice(2, 4)}`;

      // Conta rapidamente quantas linhas (sem parse completo)
      const raw = readFileSync(join(scoredDir, f), 'utf-8');
      const lineCount = raw.split('\n').filter(l => l.trim()).length - 1; // -header

      disponiveis.push({
        arquivo: f,
        label: `${dia}/${mes}/${ano} ${time}`,
        data,
        cartas: lineCount,
      });
    }

    // Agrupa por semana (para o seletor)
    const semanas: { label: string; arquivos: ArquivoDisponivel[] }[] = [];
    for (const a of disponiveis) {
      const d = new Date(
        parseInt(a.data.slice(0, 4)),
        parseInt(a.data.slice(4, 6)) - 1,
        parseInt(a.data.slice(6, 8))
      );
      const weekLabel = `Semana de ${d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })}`;
      const last = semanas[semanas.length - 1];
      if (last && last.label === weekLabel) {
        last.arquivos.push(a);
      } else {
        semanas.push({ label: weekLabel, arquivos: [a] });
      }
    }

    // Seleciona o arquivo alvo
    const target = selected && files.includes(selected) ? selected : files[0];
    const targetPath = join(scoredDir, target);
    const stats = statSync(targetPath);

    const cards = parseScoredCSV(targetPath);

    const subvalorizadas = cards.filter(c => c.oportunidade === '🔥 Subvalorizada' && c.real >= 5)
      .sort((a, b) => b.upside - a.upside);
    const inflacionadas = cards.filter(c => c.oportunidade === '💀 Inflacionada')
      .sort((a, b) => a.upside - b.upside);
    const justo = cards.filter(c => c.oportunidade === '⚖️ Preço Justo');

    // Sets
    const setCounts: Record<string, number> = {};
    cards.forEach(c => { if (c.sigla) setCounts[c.sigla] = (setCounts[c.sigla] || 0) + 1; });
    const sets = Object.entries(setCounts)
      .map(([sigla, count]) => ({ sigla, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);

    return NextResponse.json({
      arquivo: target,
      ultimaAtualizacao: stats.mtime.toISOString(),
      total: cards.length,
      disponiveis,
      semanas,
      subvalorizadas,
      inflacionadas: inflacionadas.slice(0, 20),
      justo: justo.length,
      todas: cards,
      sets,
    });
  } catch (error) {
    return NextResponse.json({
      error: error instanceof Error ? error.message : 'Erro ao ler dados'
    }, { status: 500 });
  }
}