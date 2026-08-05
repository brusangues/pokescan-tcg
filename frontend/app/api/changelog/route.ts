import { NextResponse } from 'next/server';
import { spawnSync } from 'child_process';
import { readFileSync, existsSync } from 'fs';
import { join } from 'path';
import { parse } from 'csv-parse/sync';

export const dynamic = 'force-dynamic';

const REPO_DIR = join(process.cwd(), '..'); // raiz do repo pokescan-tcg
const ABLATIONS_CSV = join(process.cwd(), '..', 'experiments', 'ablation_results.csv');

function getCommits() {
  try {
    // Formato: hash|data ISO|autor|subject
    // spawnSync com array — evita que o cmd.exe interprete %a como variável
    const res = spawnSync(
      'git',
      ['log', '--date=iso', '--pretty=format:%h|%aI|%an|%s', '-n', '60'],
      { cwd: REPO_DIR, encoding: 'utf-8', maxBuffer: 1024 * 1024 }
    );
    if (res.status !== 0) {
      console.error('git log status:', res.status, res.stderr?.slice(0, 200));
      return [];
    }
    const out = res.stdout || '';
    return out
      .trim()
      .split('\n')
      .filter(Boolean)
      .map(line => {
        const [hash, date, author, ...rest] = line.split('|');
        const subject = rest.join('|') || '';
        // Extrai tipo (feat/fix/docs/refactor/...)
        const m = subject.match(/^(\w+)(?:\(([^)]+)\))?:/);
        return {
          hash,
          date: date || '',
          author: author || '',
          subject,
          type: m ? m[1] : 'other',
          scope: m && m[2] ? m[2] : null,
        };
      });
  } catch (e) {
    console.error('git log falhou:', e);
    return [];
  }
}

function getAblations() {
  if (!existsSync(ABLATIONS_CSV)) return [];
  try {
    const raw = readFileSync(ABLATIONS_CSV, 'utf-8');
    const rows: any[] = parse(raw, { columns: true, skip_empty_lines: true });
    return rows.map(r => {
      const [modelo, agg, pca] = (r.label || '').split('/');
      return {
        label: r.label,
        modelo: modelo || '',
        agregacao: agg || '',
        pca: pca ? parseInt(pca.replace('pca', ''), 10) : null,
        mae: parseFloat(r.mae),
        r2: parseFloat(r.r2),
        n_train: parseInt(r.n_train, 10),
        n_test: parseInt(r.n_test, 10),
      };
    });
  } catch (e) {
    console.error('ablações CSV falhou:', e);
    return [];
  }
}

export async function GET() {
  const commits = getCommits();
  const ablations = getAblations();

  // Melhor R²
  const melhor = ablations.length
    ? ablations.reduce((a, b) => (b.r2 > a.r2 ? b : a))
    : null;

  return NextResponse.json({
    commits,
    ablations,
    melhor,
    total_commits: commits.length,
    atualizado_em: new Date().toISOString(),
  });
}
