#!/usr/bin/env python
"""
validar_brl_temporal.py — as features temporais USD melhoram o modelo BRL?

Monta um dataset (card × data do snapshot da Liga) com:
  label  = preco_real_brl (preço BR daquele dia)
  X      = estáticas + target_usd + features TEMPORAIS USD da semana TCGCSV
           mais recente ANTES do dia do snapshot (sem vazamento)
Corte temporal: train = snapshots até 10/08, test = 17/08.
Compara: baseline BRL (estáticas + USD) vs temporal (+ histórico TCGCSV).

Uso: python experiments/validar_brl_temporal.py
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
EX = REPO / 'experiments' / 'tcgcsv'
sys.path.insert(0, str(REPO))
import pokemon_price_monitor as pm

FEATS_TEMPORAIS = ['price_principal', 'price_normal', 'price_holo', 'price_reverse',
                   'ret_1w', 'ret_4w', 'ret_8w', 'mom_4w', 'vol_8w',
                   'spread_rev_norm', 'spread_rev_norm_rel', 'n_semanas']

# dia do snapshot → semana TCGCSV das features (a mais recente ANTES do snapshot)
SNAP_PARA_SEMANA = {
    '20260802': '2026-07-28',
    '20260803': '2026-07-28',
    '20260805': '2026-08-04',
    '20260810': '2026-08-04',
    '20260817': '2026-08-11',
}


def build_temporais_por_semana():
    """Reconstrói as matrizes card × data das features temporais (como features_temporais)."""
    hist = pd.read_csv(EX / 'historico_en.csv', dtype={'productId': str})
    pid2card = json.loads((EX / 'pid_to_card.json').read_text(encoding='utf-8'))
    hist['card'] = hist['productId'].map(pid2card)
    hist = hist.dropna(subset=['card'])
    hist['data'] = hist['data'].astype(str)
    n_sem_pid = hist.groupby(['card', 'productId'])['data'].nunique().rename('n').reset_index()
    melhor = n_sem_pid.sort_values('n', ascending=False).drop_duplicates('card')
    hist = hist.merge(melhor[['card', 'productId']], on=['card', 'productId'])

    P = None
    for st in ['Holofoil', 'Normal', 'Reverse Holofoil']:
        m = hist[hist['subtype'] == st].pivot_table(index='card', columns='data',
                                                    values='market_price', aggfunc='first')
        P = m.copy() if P is None else P.fillna(m)
    Pn = hist[hist['subtype'] == 'Normal'].pivot_table(index='card', columns='data', values='market_price', aggfunc='first')
    Ph = hist[hist['subtype'] == 'Holofoil'].pivot_table(index='card', columns='data', values='market_price', aggfunc='first')
    Pr = hist[hist['subtype'] == 'Reverse Holofoil'].pivot_table(index='card', columns='data', values='market_price', aggfunc='first')

    logP = np.log(P.replace(0, np.nan))
    ret = logP.diff(axis=1)
    ret_4w, ret_8w = logP.diff(4, axis=1), logP.diff(8, axis=1)
    mom_4w = ret.T.rolling(4, min_periods=1).mean().T
    vol_8w = ret.T.rolling(8, min_periods=3).std().T
    cum_n = P.notna().cumsum(axis=1)

    def bloco(semana):
        """DataFrame card × {features temporais} para a semana alvo."""
        def col(m):
            return m[semana].reindex(P.index) if semana in m.columns else pd.Series(np.nan, index=P.index)
        out = pd.DataFrame({
            'card': P.index.values,
            't_price_principal': col(P).values, 't_price_normal': col(Pn).values, 't_price_holo': col(Ph).values,
            't_price_reverse': col(Pr).values, 't_ret_1w': col(ret).values, 't_ret_4w': col(ret_4w).values,
            't_ret_8w': col(ret_8w).values, 't_mom_4w': col(mom_4w).values, 't_vol_8w': col(vol_8w).values,
            't_n_semanas': col(cum_n).values,
        })
        out['t_spread_rev_norm'] = out['t_price_reverse'] - out['t_price_normal']
        out['t_spread_rev_norm_rel'] = (out['t_price_reverse'] - out['t_price_normal']) / out['t_price_normal'].replace(0, np.nan)
        return out

    return bloco


def load_estaticas():
    cache = json.loads((REPO / 'data' / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
    df = pd.DataFrame([pm.parse_card(c) for c in cache])
    df['_raw'] = cache
    df = pm.enrich_pricing(df)
    df = pm.add_supply_features(df)
    df['id'] = df['id'].astype(str)
    X = pm.prepare_features(df)
    X['id'] = df['id'].values
    X['release_year'] = df['release_year'].values
    return X.set_index('id')


def main():
    print('Features estáticas...', flush=True)
    est = load_estaticas()
    print(f'  {len(est)} cartas × {est.shape[1]}', flush=True)
    print('Build das temporais USD por semana...', flush=True)
    bloco = build_temporais_por_semana()

    frames = []
    for dia, semana in SNAP_PARA_SEMANA.items():
        arquivo = sorted(glob.glob(f'data/scored/scored_snapshot_{dia}_*.csv'))[-1]
        s = pd.read_csv(arquivo)
        s = s[s['preco_real_brl'].notna()].copy()
        # card_id da Liga ('25-en-75' ou antigos via liga_id 'CL-75') → card_id do
        # catálogo ('col1-75') via set_map (idE → set TCGAPI) — o pid_to_card usa
        # o formato do catálogo
        ed = json.loads((REPO / 'data' / 'liga' / 'edicoes_liga.json').read_text(encoding='utf-8'))
        sm = json.loads((REPO / 'frontend' / 'public' / 'data' / 'set_map.json').read_text(encoding='utf-8'))
        sigla_para_idE = {v.get('sigla'): k for k, v in ed.items() if v.get('sigla')}
        def para_catalogo(card_liga):
            if pd.isna(card_liga):
                return None
            c = str(card_liga).strip()
            if '-' not in c:
                return None
            if c[0].isalpha():
                # liga_id antigo: 'CL-75' → idE via sigla
                sigla, num = c.rsplit('-', 1)
                ide = sigla_para_idE.get(sigla.upper()) or sigla_para_idE.get(sigla)
                if not ide:
                    return None
            else:
                # card_id novo: '25-en-75'
                partes = c.split('-')
                ide, num = partes[0], partes[-1]
            set_api = sm.get(str(ide))
            if not set_api:
                return None
            num_limpo = num.lstrip('0') or '0'
            return f'{set_api}-{num_limpo}'
        if 'card_id' in s.columns:
            s['card_id'] = s['card_id'].map(para_catalogo)
        else:
            s['card_id'] = s['liga_id'].map(para_catalogo)
        s = s[s['card_id'].notna()].drop_duplicates('card_id')
        s['card_id'] = s['card_id'].astype(str)
        tmp = s[['card_id', 'preco_real_brl']].merge(bloco(semana), left_on='card_id', right_on='card', how='inner')
        tmp = tmp.merge(est, left_on='card_id', right_index=True, how='inner')
        tmp['data'] = dia
        # só cartas com histórico USD (para as temporais não serem tudo NaN)
        tmp = tmp[tmp['t_price_principal'].notna()]
        frames.append(tmp)
        print(f'  {dia} (semana {semana}): {len(tmp):,} cartas c/ BRL+USD+hist', flush=True)

    df = pd.concat(frames, ignore_index=True)
    df = df[df['preco_real_brl'] > 0]
    df['log_brl'] = np.log(df['preco_real_brl'])

    corte = '20260810'
    train = df[df['data'] <= corte]
    test = df[df['data'] > corte]
    print(f'\nCORTE {corte}: train {len(train):,} | test {len(test):,}', flush=True)

    car = ['rarity_tcg', 'primary_type', 'set_series', 'price_type', 'supertype', 'illustrator', 'trainer_gender']
    car = [c for c in car if c in train.columns]
    # as temporais do dataset têm prefixo t_ (bloco de build_temporais_por_semana)
    t_cols = [f't_{c}' for c in FEATS_TEMPORAIS if f't_{c}' in train.columns]
    est_cols = [c for c in est.columns if c not in FEATS_TEMPORAIS and c != 'release_year']

    def avaliar(cols, nome):
        Xtr, Xte = train[cols].copy(), test[cols].copy()
        for c in cols:
            if c in car:
                Xtr[c] = Xtr[c].astype(str).fillna('NA')
                Xte[c] = Xte[c].astype(str).fillna('NA')
            else:
                med = Xtr[c].median()
                Xtr[c] = pd.to_numeric(Xtr[c], errors='coerce').fillna(med)
                Xte[c] = pd.to_numeric(Xte[c], errors='coerce').fillna(med)

        # garante que as colunas existem (baseline = est_*, temporal = est_* + t_*)
        cols_ok = [c for c in cols if c in Xtr.columns]
        from catboost import CatBoostRegressor
        m = CatBoostRegressor(iterations=600, learning_rate=0.06, depth=6,
                              l2_leaf_reg=5, random_seed=42, verbose=0)
        cats = [c for c in car if c in Xtr.columns]
        # 'target_price_usd' entra como numérica
        m.fit(Xtr[cols_ok], train['log_brl'].values.astype(float),
              cat_features=[c for c in cats if c in cols_ok])
        pred = m.predict(Xte[cols_ok])
        y = test['log_brl'].values.astype(float)
        r2 = 1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2)
        pred_p, y_p = np.exp(pred), np.exp(y)
        mape = np.mean(np.abs(pred_p - y_p) / y_p) * 100
        print(f'\n  [{nome}] R²(log)={r2:.4f} | MAPE={mape:.1f}% | mediana real={np.median(y_p):.2f} pred={np.median(pred_p):.2f}')
        if 'release_year' in test.columns:
            tf = test.copy(); tf['pred'] = np.exp(pred); tf['real'] = y_p
            for ano in sorted(tf['release_year'].dropna().astype(int).unique()):
                s2 = tf[tf['release_year'].astype(int) == ano]
                if len(s2) >= 30:
                    rel2 = np.abs(s2['pred'] - s2['real']) / s2['real']
                    e = np.median(rel2) * 100
                    marca = ' ◀ safra nova' if ano >= 2025 else ''
                    print(f'    safra {ano}: n={len(s2):>5} | erro mediano={e:.1f}%{marca}')
        if nome == 'temporal':
            imp = pd.Series(m.get_feature_importance(), index=cols_ok).sort_values(ascending=False)
            print('    top-8:', ', '.join(f'{k}={v:.0f}' for k, v in imp.head(8).items()))
        return mape

    base_cols = [c for c in est.columns if c not in FEATS_TEMPORAIS and c != 'release_year']
    print('\n=== BASELINE BRL (estáticas + target_usd) ===')
    avaliar(base_cols, 'baseline')
    print('\n=== TEMPORAL BRL (+ histórico USD) ===')
    avaliar(base_cols + t_cols, 'temporal')


if __name__ == '__main__':
    main()