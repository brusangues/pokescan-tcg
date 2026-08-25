"""scatter_fase3.py — Real vs Predito nos sets dos últimos 2 anos (2024+).

Fonte: snapshot pós-Liga-first (pred_ref = modelo Liga-first onde cobre).
Saída: experiments/fase3_scatter_geral.png + fase3_scatter_sets.png
"""
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE = r"C:\projects\pokescan-tcg"
df = pd.read_csv(f"{BASE}\\data\\scored\\scored_snapshot_20260825_073923.csv")

# ano de release por sigla da Liga (via mapping ptcg -> releaseDate)
cards = json.load(open(f"{BASE}\\data\\ptcg_cards_cache.json", encoding='utf-8'))
set_ano = {}
for c in cards:
    sid = (c.get('set') or {}).get('id')
    rd = str((c.get('set') or {}).get('releaseDate') or '')
    if sid and rd[:4].isdigit():
        set_ano[sid] = int(rd[:4])
smap = json.load(open(f"{BASE}\\data\\liga\\liga_set_sigla_ptcg.json", encoding='utf-8'))
sigla_ano = {str(v).upper(): set_ano[k] for k, v in smap.items() if k in set_ano}

df['sigla_u'] = df['sSigla'].astype(str).str.upper()
df['ano'] = df['sigla_u'].map(sigla_ano)
d = df[(df['ano'] >= 2024) & df['real_ref'].notna() & df['pred_ref'].notna()].copy()
d = d[(d['real_ref'] > 0) & (d['pred_ref'] > 0)]
print(f"cartas 2024+: {len(d)} | sets: {d['sigla_u'].nunique()}")

AZUL, VERM, CINZA = '#2563eb', '#dc2626', '#9ca3af'

# ── Figura 1: geral ──
fig, ax = plt.subplots(figsize=(8.5, 7))
lo = max(d['real_ref'].min(), d['pred_ref'].min()) * 0.6
hi = max(d['real_ref'].max(), d['pred_ref'].max()) * 1.6
ax.plot([lo, hi], [lo, hi], color=CINZA, lw=1.2, ls='--', label='predição perfeita')
ax.scatter(d['real_ref'], d['pred_ref'], s=16, alpha=.35, color=AZUL, edgecolors='none')
ax.set_xscale('log'); ax.set_yscale('log')
er = np.abs(d['pred_ref'] - d['real_ref']) / d['real_ref']
ax.set_title(f'Real vs Predito — sets 2024–2026 ({len(d)} cartas, {d["sigla_u"].nunique()} sets)\n'
             f'erro relativo mediano: {100*np.median(er):.0f}%   |   MAE: R${np.abs(d["pred_ref"]-d["real_ref"]).mean():.0f}',
             fontsize=11)
ax.set_xlabel('Preço real (R$, escala log)')
ax.set_ylabel('Predito pelo modelo (R$, escala log)')
ax.legend(loc='upper left')
ax.grid(alpha=.25, which='both')
fig.tight_layout()
fig.savefig(f"{BASE}\\experiments\\fase3_scatter_geral.png", dpi=130)

# ── Figura 2: por set (small multiples, top 12 por n) ──
top = d['sigla_u'].value_counts().head(12).index.tolist()
dd = d[d['sigla_u'].isin(top)]
ncol = 4
nrow = int(np.ceil(len(top) / ncol))
fig2, axes = plt.subplots(nrow, ncol, figsize=(15, 3.4 * nrow), sharex=False, sharey=False)
for ax_, sig in zip(axes.flat, top):
    s = dd[dd['sigla_u'] == sig]
    ano_set = int(s['ano'].iloc[0])
    lo = max(s['real_ref'].min(), s['pred_ref'].min()) * .6
    hi = max(s['real_ref'].max(), s['pred_ref'].max()) * 1.6
    ax_.plot([lo, hi], [lo, hi], color=CINZA, lw=1, ls='--')
    ax_.scatter(s['real_ref'], s['pred_ref'], s=13, alpha=.45, color=AZUL, edgecolors='none')
    e = np.abs(s['pred_ref'] - s['real_ref']) / s['real_ref']
    # faixa de ±25% sombreada
    xx = np.logspace(np.log10(lo), np.log10(hi), 20)
    ax_.fill_between(xx, xx * .75, xx * 1.25, color='#22c55e', alpha=.10, lw=0)
    ax_.set_xscale('log'); ax_.set_yscale('log')
    ax_.set_title(f'{sig} ({ano_set}) — n={len(s)}, erroMed {100*np.median(e):.0f}%', fontsize=9.5)
    ax_.grid(alpha=.25, which='both')
for ax_ in axes.flat[len(top):]:
    ax_.axis('off')
fig2.suptitle('Real vs Predito por set (2024+) — verde = faixa ±25%', fontsize=12)
fig2.tight_layout(rect=[0, 0, 1, 0.97])
fig2.savefig(f"{BASE}\\experiments\\fase3_scatter_sets.png", dpi=120)
print("PNGs salvos em experiments/")
