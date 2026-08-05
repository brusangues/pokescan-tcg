import { readFileSync } from 'fs';
import { parse } from 'csv-parse/sync';

/**
 * Lê e parseia um CSV escorado (data/scored/scored_*.csv) de forma correta,
 * respeitando aspas e vírgulas internas (ex: "+37,91" decimal, dicts com vírgula).
 * Retorna array de records string→string, já com os valores inválidos filtrados.
 */
export function parseScoredCSV(filePath: string): any[] {
  const raw = readFileSync(filePath, 'utf-8');
  const records = parse(raw, {
    columns: true,
    skip_empty_lines: true,
    relax_column_count: true,
    trim: true,
  });

  return records
    .filter((r: any) => r.oportunidade && r.real_ref && r.pred_ref)
    .map((r: any) => ({
      nome: r.nPT || r.name || r.nome || r.nEN || 'Unknown',
      sigla: r.sSigla || r.set_id || '',
      setNome: r.ed_sNome || r.ed_sNomePortugues || r.set_name || '',
      real: parseFloat(String(r.real_ref).replace(',', '.')),
      pred: parseFloat(String(r.pred_ref).replace(',', '.')),
      upside: parseFloat(String(r.upside_pct).replace(',', '.')),
      oportunidade: r.oportunidade,
      iCO: parseInt(r.iCO || r.iCO_real || '0', 10),
      moeda: r.moeda || 'R$',
      liga_id: r.liga_id || '',
      nEN: r.nEN || '',
      sNumber: r.sNumber || '',
      num: r.num || '',
      fonte: r.fonte || '',
    }))
    .filter((c: any) => {
      const ok = !Number.isNaN(c.upside) && !Number.isNaN(c.real) && !Number.isNaN(c.pred);
      if (!ok) {
        console.warn(`[scored] cartão inválido descartado: ${c.nome} (upside=${c.upside}, real=${c.real}, pred=${c.pred})`);
      }
      return ok;
    });
}