#!/usr/bin/env python
"""
temporal_lib.py — funções compartilhadas de features temporais TCGCSV.

bloco_semana(hist, semana) -> DataFrame (card × t_*): preço por subtype,
retornos 1/4/8 sem, momentum, volatilidade, spread, n de semanas para uma
semana alvo qualquer (a mais recente ANTES de um snapshot, por exemplo).

Reusada por ab_tcgcsv.py e validar_brl_temporal.py.
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EX = REPO / 'experiments' / 'tcgcsv'


def _matrizes(hist):
    """Preço principal (holofoil→normal→reverse) + por subtype, card × data."""
    n_sem_pid = hist.groupby(['card', 'productId'])['data'].nunique().rename('n').reset_index()
    melhor = n_sem_pid.sort_values('n', ascending=False).drop_duplicates('card')
    h = hist.merge(melhor[['card', 'productId']], on=['card', 'productId'])

    P = None
    for st in ['Holofoil', 'Normal', 'Reverse Holofoil']:
        m = h[h['subtype'] == st].pivot_table(index='card', columns='data',
                                              values='market_price', aggfunc='first')
        P = m.copy() if P is None else P.fillna(m)
    Pn = h[h['subtype'] == 'Normal'].pivot_table(index='card', columns='data', values='market_price', aggfunc='first')
    Ph = h[h['subtype'] == 'Holofoil'].pivot_table(index='card', columns='data', values='market_price', aggfunc='first')
    Pr = h[h['subtype'] == 'Reverse Holofoil'].pivot_table(index='card', columns='data', values='market_price', aggfunc='first')
    return P, Pn, Ph, Pr


def bloco_semana(hist: pd.DataFrame, semana: str) -> pd.DataFrame:
    """Features temporais (prefixo t_) da semana alvo, indexadas por card."""
    P, Pn, Ph, Pr = _matrizes(hist)
    logP = np.log(P.replace(0, np.nan))
    ret = logP.diff(axis=1)
    ret_4w, ret_8w = logP.diff(4, axis=1), logP.diff(8, axis=1)
    mom_4w = ret.T.rolling(4, min_periods=1).mean().T
    vol_8w = ret.T.rolling(8, min_periods=3).std().T
    cum_n = P.notna().cumsum(axis=1)

    def col(m):
        return m[semana].reindex(P.index) if semana in m.columns else pd.Series(np.nan, index=P.index)

    out = pd.DataFrame({
        't_price_principal': col(P).values, 't_price_normal': col(Pn).values,
        't_price_holo': col(Ph).values, 't_price_reverse': col(Pr).values,
        't_ret_1w': col(ret).values, 't_ret_4w': col(ret_4w).values,
        't_ret_8w': col(ret_8w).values, 't_mom_4w': col(mom_4w).values,
        't_vol_8w': col(vol_8w).values, 't_n_semanas': col(cum_n).values,
    }, index=P.index)
    out.index.name = 'card_id'
    out['t_spread_rev_norm'] = out['t_price_reverse'] - out['t_price_normal']
    out['t_spread_rev_norm_rel'] = (out['t_price_reverse'] - out['t_price_normal']) / out['t_price_normal'].replace(0, np.nan)
    return out


if __name__ == '__main__':
    hist = pd.read_csv(EX / 'historico_en.csv', dtype={'productId': str})
    pid2card = json.loads((EX / 'pid_to_card.json').read_text(encoding='utf-8'))
    hist['card'] = hist['productId'].map(pid2card)
    hist = hist.dropna(subset=['card'])
    b = bloco_semana(hist, '2026-08-11')
    print(f'bloco semana 2026-08-11: {len(b):,} cards × {b.shape[1]} feats')
    print(b.dropna(subset=['t_price_principal']).head(3).to_string())