#!/usr/bin/env python
"""macro_diaria.py — P2.10 consolidado: hits + snapshot + alertas numa rotina.

Roda em SEQUÊNCIA (não concorrente — evita o timeout/lock visto quando os 3
jobs rodavam em paralelo ~06:30–07:05) e imprime um relatório RESUMIDO:

  1. crawler_liga_hits --tipo all  → raspa + enriquece as 6 combinações
  2. script/ensure_embeddings.py    → garante imagens/embeddings (incremental)
  3. script/score_apos_crawl.py --tipo hits  → scored_hits
  4. crawler_liga_snapshot.py       → snapshot BRL (série temporal diária)
  5. script/score_apos_crawl.py --tipo snapshot → scored_snapshot
  6. alertas_oportunidade.py        → O foco: oportunidades (upside+iCO)

Cada passo alimenta o próximo; capturamos só o resumo (contadores) p/ não
inundar o Telegram. O alerta final sai na íntegra.
"""
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PY = r'C:/Models/hermes/hermes-agent/venv/Scripts/python.exe'


def rodar(passo: str, cmd: list, timeout=3600) -> str:
    """Roda um subprocesso, capturando stdout+stderr. Retorna a saída (str)."""
    print(f'\n▶ {passo}', flush=True)
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=str(BASE), capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=timeout)
        out = (r.stdout or '') + (r.stderr or '')
        ok = r.returncode == 0
    except subprocess.TimeoutExpired:
        ok = False
        out = f'TIMEOUT após {timeout}s'
    dur = time.time() - t0
    status = '✅' if ok else '❌'
    print(f'{status} {passo} ({dur/60:.0f}min)')
    return out, ok, dur


def extrai(out: str, patterns: dict) -> dict:
    res = {}
    for chave, rx in patterns.items():
        m = re.search(rx, out)
        res[chave] = m.group(1).strip() if m else None
    return res


def main():
    print('🧭 MACRO DIÁRIA PokeScan TCG —', datetime.now().strftime('%d/%m/%Y %H:%M'))
    print('=' * 52)

    # 1. HITS
    out, ok_hits, dur_hits = rodar('HITS · crawler', [PY, 'crawler/crawler_liga_hits.py', '--tipo', 'all'])
    print('   (crawler hits ok)' if ok_hits else '   (⚠ crawler hits falhou, segue?)')
    out_map, ok_map, dur_map = rodar('HITS · mapping', [PY, 'script/rebuild_set_mapping.py'])
    out_emb, ok_emb, dur_emb = rodar('HITS · embeddings', [PY, 'script/ensure_embeddings.py'])
    out_escore, ok_escore, dur_escore = rodar('HITS · escore', [PY, 'script/score_apos_crawl.py', '--tipo', 'hits', '--top', '10'])
    m_hits = extrai(out_escore, {
        'total': r'Total cartas enscoradas:\s*(\d+)',
        'sub': r'Subvalorizadas .*?:\s*(\d+)',
        'leve': r'Leve Desconto .*?:\s*(\d+)',
        'justo': r'Preço Justo.*?:\s*(\d+)',
        'infl': r'Inflacionadas.*?:\s*(\d+)',
        'salvo': r'Salvo:\s*(\S+)',
    })

    # 2. SNAPSHOT (com IDEMPOTÊNCIA — igual ao liga-snapshot-diario.sh: se o
    #    scored_snapshot_<hoje> já existe (ex. produzido pelo snapshot-semanal
    #    ou rodada anterior), NÃO re-crawla — só o resumo de hoje fica no site.
    hoje = datetime.now().strftime('%Y%m%d')
    snap_existente = list((BASE / 'data' / 'scored').glob(f'scored_snapshot_{hoje}_*.csv'))
    if snap_existente:
        print(f'\n▶ SNAPSHOT (já existe hoje: {snap_existente[0].name}) — pulando crawl', flush=True)
        ok_snap, ok_snap_esc = True, True
        dur_snap, dur_snap_esc = 0.0, 0.0
        arquivo = snap_existente[0]
        # estima contadores a partir do CSV (sem re-escorar)
        import pandas as pd
        try:
            df = pd.read_csv(arquivo)
            if 'upside_pct' in df.columns and 'iCO' in df.columns:
                import numpy as np
                up = pd.to_numeric(df.get('upside_pct'), errors='coerce').fillna(0)
                ico = pd.to_numeric(df.get('iCO'), errors='coerce').fillna(0)
                m_snap = {
                    'total': str(len(df)),
                    'sub': str(int((up > 25).sum())),
                    'infl': str(int((up < -25).sum())),
                    'salvo': str(arquivo),
                }
            else:
                m_snap = {'total': str(len(df)), 'sub': None, 'infl': None, 'salvo': str(arquivo)}
        except Exception:
            m_snap = {'total': '?', 'sub': None, 'infl': None, 'salvo': str(arquivo)}
    else:
        out_snap, ok_snap, dur_snap = rodar('SNAPSHOT · crawler', [PY, 'crawler/crawler_liga_snapshot.py', '--max-sets', '999'])
        out_snap_esc, ok_snap_esc, dur_snap_esc = rodar('SNAPSHOT · escore', [PY, 'script/score_apos_crawl.py', '--tipo', 'snapshot', '--top', '15'])
        m_snap = extrai(out_snap_esc, {
            'total': r'Total cartas enscoradas:\s*(\d+)',
            'sub': r'Subvalorizadas .*?:\s*(\d+)',
            'infl': r'Inflacionadas.*?:\s*(\d+)',
            'salvo': r'Salvo:\s*(\S+)',
        })

    # 3. ALERTAS (foco) — roda por último e sai na íntegra
    print('\n▶ ALERTA DE OPORTUNIDADES (foco)', flush=True)
    a_out, a_ok, a_dur = rodar('ALERTAS', [PY, 'script/alertas_oportunidade.py', '--tipo', 'hits',
                                           '--upside-min', '50', '--ico-min', '3'])

    # ── RELATÓRIO CONSOLIDADO ──────────────────────────────────────────────
    print('\n' + '═' * 52)
    print('📊 MACRO DIÁRIA — RESUMO')
    print('═' * 52)

    # Resumo das etapas (1 linha cada)
    print('🖥️  Execução:')
    print(f'  {"✅" if ok_hits else "❌"} HITS crawl        ({dur_hits/60:.0f}min)')
    print(f'  {"✅" if ok_map else "❌"} HITS mapping      ({dur_map/60:.0f}min)')
    print(f'  {"✅" if ok_emb else "❌"} HITS embeddings   ({dur_emb/60:.0f}min)')
    print(f'  {"✅" if ok_escore else "❌"} HITS escore       ({dur_escore/60:.0f}min)')
    print(f'  {"✅" if ok_snap else "❌"} SNAPSHOT crawl    ({dur_snap/60:.0f}min)')
    print(f'  {"✅" if ok_snap_esc else "❌"} SNAPSHOT escore   ({dur_snap_esc/60:.0f}min)')

    # Contadores HITS
    print('\n🔥 HITS —', m_hits.get('total') or '?', 'cartas escoradas',
          f'(sub {m_hits.get("sub") or 0} · leve {m_hits.get("leve") or 0} · justo {m_hits.get("justo") or 0} · infl {m_hits.get("infl") or 0})')
    if m_hits.get('salvo'):
        print(f'   csv: {Path(m_hits["salvo"]).name}')

    # Contadores SNAPSHOT
    print('🏞️  SNAPSHOT —', m_snap.get('total') or '?', 'cartas escoradas',
          f'(sub {m_snap.get("sub") or 0} · infl {m_snap.get("infl") or 0})')

    # As oportunidades (se o alerta emitiu algo) — o a_out já veio impresso acima
    if a_out.strip():
        print('\n🚨 OPORTUNIDADES (upside ≥50% e iCO ≥3):')
        print(a_out.strip()[:3000])
    else:
        print('\n🚨 Nenhuma oportunidade hoje (nada cruzou upside ≥50% e iCO ≥3).')
    print('═' * 52)


if __name__ == '__main__':
    main()