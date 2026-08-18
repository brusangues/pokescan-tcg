"""
script/tcgcsv_lib.py — funções de dados TCGCSV usadas no PRODUTIVO (retrain/score).

bloco_semana(hist, semana)  -> DataFrame (card × t_*): preço por subtype,
    retornos 1/4/8 sem, momentum, volatilidade, spread, n de semanas.
mapeamento()                -> pid2card (productId TCGCSV → card_id do catálogo).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
EX = BASE_DIR / 'experiments' / 'tcgcsv'


def mapeamento() -> dict:
    """productId TCGCSV → card_id do catálogo (pid_to_card.json)."""
    return json.loads((EX / 'pid_to_card.json').read_text(encoding='utf-8'))


def ler_historico() -> pd.DataFrame:
    """historico_en.csv com a coluna 'card' (card_id do catálogo) já mapeada."""
    hist = pd.read_csv(EX / 'historico_en.csv', dtype={'productId': str})
    hist['card'] = hist['productId'].map(mapeamento())
    return hist.dropna(subset=['card'])[['data', 'productId', 'subtype', 'market_price', 'card']]


def _matrizes(hist: pd.DataFrame):
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
    """Features temporais (prefixo t_) da semana alvo, indexadas por card_id."""
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


def preco_ultima_semana(hist: pd.DataFrame = None) -> tuple[dict, dict, str]:
    """Preço principal por card (dict) + variante por card (dict) da semana mais
    recente do histórico. Retorna (preco, variante, semana)."""
    if hist is None:
        hist = ler_historico()
    semana = max(hist['data'])
    h = hist[hist['data'] == semana]
    preco, variante = {}, {}
    for pid, g in h.groupby('productId'):
        vals = {r['subtype']: r['market_price'] for _, r in g.iterrows() if r['market_price'] > 0}
        cid = g['card'].iloc[0]
        for st in ('Holofoil', 'Normal', 'Reverse Holofoil'):
            if st in vals:
                preco[cid] = vals[st]
                variante[cid] = st.lower()
                break
    return preco, variante, semana