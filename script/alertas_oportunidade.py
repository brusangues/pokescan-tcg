#!/usr/bin/env python
"""alertas_oportunidade.py — P2.10: alerta DEDICADO de oportunidade (Telegram).

Lê o CSV escorado mais recente (data/scored/scored_{tipo}_*.csv, gerado por
score_apos_crawl.py) e imprime SOMENTE as cartas que cruzam thresholds de
oportunidade (upside alto + mínimo de ofertas iCO). Segue o padrão WATCHDOG de
cron no_agent: **stdout vazio = silêncio** (nada cruza = nenhuma mensagem);
stdout não-vazio = o alerta, entregue verbatim.

Thresholds default (alinhados ao backlog P2.10):
  - upside_pct >= UPSIDE_MIN (50%)
  - iCO >= ICO_MIN (3)
  - real_ref >= PRECO_MIN_BRL (R$ 5) ou >= PRECO_MIN_USD ($ 2) — ignora lixo
Pode reusar o fundo com --tipo snapshot. PMID 2026-08-26 (P2.10).
"""
import argparse
import glob
import os
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
SCORE_DIR = BASE / 'data' / 'scored'
SITE = 'https://brusangues.github.io/pokescan-tcg'


def ultimo_csv(tipo: str) -> Path:
    pat = SCORE_DIR / f'scored_{tipo}_*.csv'
    files = sorted(glob.glob(str(pat)))
    if not files:
        sys.exit(0)  # sem dados hoje → silêncio (exit 0 + stdout vazio)
    return Path(files[-1])


def linha_alerta(r) -> dict:
    moeda = str(r.get('moeda') or '$')
    real = float(r.get('real_ref') or 0)
    pred = float(r.get('pred_ref') or real)
    up = float(r.get('upside_pct') or 0)
    ico = int(r.get('iCO_real') or r.get('iCO') or 0)
    nome = str(r.get('nPT') or r.get('nome_en') or r.get('name') or '?')
    sigla = str(r.get('sSigla') or '?')
    cid = str(r.get('card_id') or r.get('liga_id') or '')
    link = f'{SITE}/card?card_id={_url(cid)}' if cid else ''
    return {'nome': nome, 'sigla': sigla, 'moeda': moeda, 'real': real,
            'pred': pred, 'carta_preco_real': real, 'upside': up, 'iCO': ico,
            'link': link}


def _url(s: str) -> str:
    try:
        from urllib.parse import quote
        return quote(s)
    except Exception:
        return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tipo', choices=['hits', 'snapshot'], default='hits')
    ap.add_argument('--upside-min', type=float, default=50.0)
    ap.add_argument('--ico-min', type=int, default=3)
    ap.add_argument('--preco-min-brl', type=float, default=5.0)
    ap.add_argument('--preco-min-usd', type=float, default=2.0)
    a = ap.parse_args()

    f = ultimo_csv(a.tipo)
    df = pd.read_csv(f)

    df['upside_pct'] = pd.to_numeric(df.get('upside_pct'), errors='coerce').fillna(0)
    col_ico_real = 'iCO_real' if 'iCO_real' in df.columns else None
    if col_ico_real:
        ico_eff = pd.to_numeric(df[col_ico_real], errors='coerce').fillna(
            pd.to_numeric(df.get('iCO'), errors='coerce')).fillna(0)
    else:
        ico_eff = pd.to_numeric(df.get('iCO'), errors='coerce').fillna(0)
    df['iCO_eff'] = ico_eff
    df['real_ref'] = pd.to_numeric(df.get('real_ref'), errors='coerce').fillna(0)
    df['moeda'] = df.get('moeda', pd.Series('$', index=df.index)).fillna('$')

    # filtro: upside alto + ofertas + preço mínimo real
    m = (df['upside_pct'] >= a.upside_min) & (df['iCO_eff'] >= a.ico_min)
    sub = df[m].copy()
    if len(sub) == 0:
        sys.exit(0)  # nada cruza → silêncio (exit 0 + stdout vazio)

    sub = sub.sort_values(['iCO_eff', 'upside_pct'], ascending=[False, False])
    linhas = [linha_alerta(r) for _, r in sub.iterrows()]

    # monta a mensagem (verbatim → Telegram)
    total = len(linhas)
    head = (f'🚨 {a.tipo.upper()} — {total} oportunidade(s) com upside ≥{a.upside_min:.0f}% '
            f'e iCO ≥{a.ico_min}')
    print(head)
    print('')
    for i, L in enumerate(linhas, 1):
        m_ = 'R$' if L['moeda'] == 'R$' else '$'
        up = f'+{L["upside"]:.0f}%' if L['upside'] >= 0 else f'{L["upside"]:.0f}%'
        seg = L['link'] or '(sem link)'
        print(f'{i}. **{L["nome"]}** ({L["sigla"]}) — {m_}{L["real"]:.2f} → {m_}{L["pred"]:.2f} ({up}, iCO {L["iCO"]})')
        print(f'   {seg}')
    print('')
    print(f'Fonte: {f.name.split("_")[-1].replace(".csv","")} · {BASE}')


if __name__ == '__main__':
    main()