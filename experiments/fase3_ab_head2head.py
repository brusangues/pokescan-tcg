"""fase3_ab_head2head.py — A/B JUSTO da Fase 3: mesmo holdout para os 2 modelos.

Protocolo (espelho do A/B TCGCSV aprovado pelo usuário):
1. Universo A (produção atual): base EN -> USD -> merge BRL. Split temporal 80/20.
2. Treina A no trA (features completas do pm).
3. Treina B (Liga-first) na SUA base (catálogo da Liga inteiro).
4. Avalia A e B NAS MESMAS LINHAS de teA (toda linha de teA existe no universo B
   pois tem en_id) — B recebe as features do par en_id->catálogo.
Métricas: MAE R$, R², erro relativo mediano — nas mesmas cartas.
"""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
import pokemon_price_monitor as pm
from sklearn.metrics import mean_absolute_error, r2_score
from catboost import CatBoostRegressor

CACHE = BASE / 'data' / 'ptcg_cards_cache.json'
CAT_LIGA = BASE / 'data' / 'catalogo_liga.json'
EMB = BASE / 'data' / 'pokemon_embeddings_base32.csv'


def treina(Xtr, ytr, Xte, yte, cat_idx):
    m = CatBoostRegressor(iterations=500, learning_rate=0.05, depth=6,
                          l2_leaf_reg=3, loss_function='MAE', eval_metric='MAE',
                          cat_features=cat_idx, verbose=False, random_seed=42,
                          early_stopping_rounds=30)
    m.fit(Xtr, ytr, eval_set=(Xte, yte), verbose=False)
    return m


def metricas(real, pred, label):
    er = np.abs(pred - real) / np.maximum(real, 0.01)
    print(f'{label}: n={len(real)} | MAE R${mean_absolute_error(real, pred):.2f} | '
          f'R² {r2_score(real, pred):.4f} | erroRelMed {100*np.median(er):.1f}%')


def main():
    # ── Universo A (idêntico ao treino produtivo) ──
    cards = json.loads(CACHE.read_text(encoding='utf-8'))
    dfA = pd.DataFrame([pm.parse_card(c) for c in cards])
    dfA['_raw'] = cards
    dfA = pm._enrich(dfA)
    dfA = pm.add_supply_features(dfA)
    dfA = dfA[dfA['target_price'].notna() & (dfA['target_price'] > 0)].copy()
    lb, li, smap = pm.build_liga_lookup()
    dfA = pm.enrich_brl(dfA, lb, li, smap)
    dfA = dfA[dfA['target_price_brl'].notna() & (dfA['target_price_brl'] > 0)].copy()
    try:
        from script.tcgcsv_pricing import FEATS_TEMPORAIS
        extras = ['target_price_usd'] + [c for c in FEATS_TEMPORAIS if c in dfA.columns]
    except Exception:
        extras = ['target_price_usd']
    dfA['target_price_usd'] = dfA['target_price'].fillna(dfA['target_price'].median())
    dfA['log_target'] = np.log1p(dfA['target_price_brl'])
    dfa = dfA.sort_values('release_year', na_position='first')
    sp = int(len(dfa) * 0.8)
    trA, teA = dfa.iloc[:sp], dfa.iloc[sp:]
    XtrA = pm.prepare_features(trA, extra_features=extras)
    XteA = pm.prepare_features(teA, extra_features=extras)
    cat_idxA = [i for i, c in enumerate(XtrA.columns) if c in pm.CAT_FEATURES]
    mA = treina(XtrA, trA['log_target'], XteA, teA['log_target'], cat_idxA)

    # ── Universo/treino B (Liga-first completo) ──
    cat_liga = json.loads(CAT_LIGA.read_text(encoding='utf-8'))
    en = {}
    for c in cards:
        pr = ((c.get('tcgplayer') or {}).get('prices') or {})
        mk = None
        for k in ('holofoil', 'normal'):
            if pr.get(k, {}).get('market'):
                mk = pr[k]['market']; break
        rd = str((c.get('set') or {}).get('releaseDate') or '')
        en[c['id']] = {'rar': c.get('rarity'), 'hp': c.get('hp'),
                       'types': ','.join(c.get('types') or []),
                       'ano': int(rd[:4]) if rd[:4].isdigit() else None, 'usd': mk}
    embmap = {}
    if EMB.exists():
        edf = pd.read_csv(EMB)
        ec = [c for c in edf.columns if c.startswith('emb_')]
        embmap = {r['id']: r[ec].values.astype(np.float32) for _, r in edf.iterrows()}

    def feats_B(cl_row):
        eid = cl_row.get('en_id')
        meta = en.get(eid, {}) if eid else {}
        return {
            'sigla': str(cl_row.get('sigla') or 'desconhecido'),
            'iCO': float(cl_row.get('iCO') or 0), 'iR': float(cl_row.get('iR') or 0),
            'rar': str(meta.get('rar') or 'desconhecido'),
            'types': str(meta.get('types') or 'desconhecido'),
            'usd': float(meta.get('usd')) if meta.get('usd') is not None else np.nan,
            'tem_emb': 1.0 if eid in embmap else 0.0,
            **{f'emb_{i}': float(v) for i, v in enumerate(embmap.get(eid, np.zeros(32)))},
        }

    rows = []
    liga_by_en = {}
    for c in cat_liga:
        p1b = float(c.get('p1b') or 0)
        if p1b <= 0:
            continue
        r = feats_B(c); r['y'] = np.log1p(p1b)
        rows.append(r)
        if c.get('en_id'):
            liga_by_en[c['en_id']] = r
    dfB = pd.DataFrame(rows)
    dfB['usd'] = dfB['usd'].fillna(dfB['usd'].median())
    cats = ['sigla', 'rar', 'types']
    featsB = ['iCO', 'iR', 'usd', 'tem_emb'] + [f'emb_{i}' for i in range(32)] + cats
    mB = treina(dfB[featsB], dfB['y'], dfB[featsB].iloc[:200], dfB['y'].iloc[:200],
                [dfB[featsB].columns.get_loc(c) for c in cats])

    # ── Head-to-head nas MESMAS linhas de teA ──
    # linha B da carta: pega do liga_by_en pelo id ptcg (teA['id'])
    idx_ok, y_real, predsA = [], [], []
    predsB_rows = []
    missing = 0
    for pos, (_, row) in enumerate(teA.iterrows()):
        rB = liga_by_en.get(row['id'])
        if rB is None:
            missing += 1
            continue
        idx_ok.append(pos); y_real.append(row['log_target']); predsA.append(None)
        predsB_rows.append(rB)
    teA2 = teA.iloc[idx_ok]
    XteA2 = XteA.iloc[idx_ok]  # XteA é numpy/posicional — usar iloc (pitfall P1.28)
    predA = mA.predict(XteA2)
    dfTB = pd.DataFrame(predsB_rows)
    predB = mB.predict(dfTB[featsB])
    real = np.expm1(np.array(y_real))
    pa = np.expm1(predA); pb = np.expm1(predB)
    print(f'\n=== HEAD-TO-HEAD (mesmas {len(real)} cartas do holdout atual; '
          f'{missing} sem par Liga-fora) ===')
    metricas(real, pa, 'Pipeline A (atual)     ')
    metricas(real, pb, 'Pipeline B (Liga-first)')
    # por faixa de preço
    for lo_, hi_ in [(0, 20), (20, 100), (100, 10**9)]:
        msk = (real >= lo_) & (real < hi_)
        if msk.sum() > 30:
            ea = np.median(np.abs(pa[msk]-real[msk])/np.maximum(real[msk], .01))*100
            eb = np.median(np.abs(pb[msk]-real[msk])/np.maximum(real[msk], .01))*100
            print(f'  faixa R${lo_}-{hi_:g}: n={msk.sum()} | erroRelMed A {ea:.1f}% | B {eb:.1f}%')

if __name__ == '__main__':
    main()