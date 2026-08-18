#!/usr/bin/env python
"""
features_temporais.py — build do dataset temporal (100% VETORIZADO).

Para cada (card_id, semana t ≥ 8):
  price_principal   — marketPrice do subtype principal (holofoil → normal → reverse)
  price_normal / price_holo / price_reverse
  ret_1w / ret_4w / ret_8w   — retorno log vs 1/4/8 semanas atrás
  mom_4w                     — média dos retornos semanais (últ. 4)
  vol_8w                     — std dos retornos semanais (últ. 8, min 3)
  spread_rev_norm (_rel)     — reverse − normal
  n_semanas
label: target_plus1 = price_principal em t+1 (previsão 1 passo à frente)

Saída: experiments/tcgcsv/dataset_temporal.csv
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EX = REPO / 'experiments' / 'tcgcsv'
PRIORIDADE = ['Holofoil', 'Normal', 'Reverse Holofoil']


def main():
    hist = pd.read_csv(EX / 'historico_en.csv', dtype={'productId': str})
    pid2card = json.loads((EX / 'pid_to_card.json').read_text(encoding='utf-8'))

    hist['card'] = hist['productId'].map(pid2card)
    hist = hist.dropna(subset=['card'])
    hist['data'] = hist['data'].astype(str)

    # 1 pid por card (o com mais semanas)
    n_sem_pid = hist.groupby(['card', 'productId'])['data'].nunique().rename('n').reset_index()
    melhor_pid = n_sem_pid.sort_values('n', ascending=False).drop_duplicates('card')
    hist = hist.merge(melhor_pid[['card', 'productId']], on=['card', 'productId'])

    datas = sorted(hist['data'].unique())

    def pivot(subtype=None):
        if subtype is None:
            mats = []
            for st in PRIORIDADE:
                mats.append(hist[hist['subtype'] == st].pivot_table(
                    index='card', columns='data', values='market_price', aggfunc='first'))
            p = mats[0].copy()
            for m in mats[1:]:
                p = p.fillna(m)
            return p
        return hist[hist['subtype'] == subtype].pivot_table(
            index='card', columns='data', values='market_price', aggfunc='first')

    P = pivot()
    Pn, Ph, Pr = pivot('Normal'), pivot('Holofoil'), pivot('Reverse Holofoil')

    logP = np.log(P.replace(0, np.nan))
    ret = logP.diff(axis=1)
    ret_4w = logP.diff(4, axis=1)
    ret_8w = logP.diff(8, axis=1)
    # rolling por coluna (pandas antigo não tem axis=1) — transpõe e roda por linha
    mom_4w = ret.T.rolling(4, min_periods=1).mean().T
    vol_8w = ret.T.rolling(8, min_periods=3).std().T
    cum_n = P.notna().cumsum(axis=1)

    blocos = []
    for pos, t in enumerate(datas):
        if pos < 8 or pos + 1 >= len(datas):
            continue
        prox = datas[pos + 1]
        def col(m, d):
            return m[d].reindex(P.index) if d in m.columns else pd.Series(np.nan, index=P.index)
        bloco = pd.DataFrame({
            'card_id': P.index,
            'data': t,
            'price_principal': col(P, t),
            'price_normal': col(Pn, t),
            'price_holo': col(Ph, t),
            'price_reverse': col(Pr, t),
            'ret_1w': col(ret, t),
            'ret_4w': col(ret_4w, t),
            'ret_8w': col(ret_8w, t),
            'mom_4w': col(mom_4w, t),
            'vol_8w': col(vol_8w, t),
            'n_semanas': col(cum_n, t),
            'target_plus1': col(P, prox),
        })
        blocos.append(bloco)

    df = pd.concat(blocos, ignore_index=True)
    df['spread_rev_norm'] = df['price_reverse'] - df['price_normal']
    df['spread_rev_norm_rel'] = (df['price_reverse'] - df['price_normal']) / df['price_normal'].replace(0, np.nan)
    df['retorno_plus1'] = np.log(df['target_plus1'] / df['price_principal'])
    df = df.dropna(subset=['price_principal', 'target_plus1'])
    df['card_id'] = df['card_id'].astype(str)

    out = EX / 'dataset_temporal.csv'
    df.to_csv(out, index=False)
    print(f'=== DATASET TEMPORAL ===')
    print(f'linhas: {len(df):,} | cards únicos: {df["card_id"].nunique():,}')
    print(f'semanas: {df["data"].min()} → {df["data"].max()} (em {df["data"].nunique()} colunas de corte)')
    print(f'retorno_plus1 média: {df["retorno_plus1"].mean():.4f} | std: {df["retorno_plus1"].std():.4f}')
    print(f'medianas: price={df["price_principal"].median():.2f} | ret_1w={df["ret_1w"].median():.4f} | '
          f'ret_4w={df["ret_4w"].median():.4f} | spread_rel={df["spread_rev_norm_rel"].median():.4f}')
    print('salvo:', out)


if __name__ == '__main__':
    main()