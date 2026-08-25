"""fase3_ab_brl.py — P1.32/Fase 3: A/B do modelo BRL Liga-first vs atual.

Pipeline A (atual, train_model_brl): base EN cache -> TCGCSV/cache USD ->
filtro USD -> enrich_brl (merge Liga por sigla+num) -> filtro BRL -> treino.
Pipeline B (Liga-first): base = catalogo_liga.json (p1b alvo) -> join EN por
en_id (features + USD cache + embeddings) -> treino. liga_only entram sem USD/emb.

Mesmo split temporal (80% antigas / 20% novas por ano), mesmos hiperparâmetros.
Métrica: MAE R$ / R² no teste + erro relativo MEDIANO safra 2026.
"""
import json, sys, re
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


def err_rel_mediano(y_real, y_pred, anos):
    m = (anos >= 2026)
    if m.sum() < 20: m = np.ones(len(y_real), bool)
    er = np.abs(np.expm1(y_pred[m]) - np.expm1(y_real[m])) / np.maximum(np.expm1(y_real[m]), 0.01)
    return float(np.median(er)) * 100


def treina(Xtr, ytr, Xte, yte, cat_idx):
    model = CatBoostRegressor(iterations=500, learning_rate=0.05, depth=6,
                              l2_leaf_reg=3, loss_function='MAE', eval_metric='MAE',
                              cat_features=cat_idx, verbose=False, random_seed=42,
                              early_stopping_rounds=30)
    model.fit(Xtr, ytr, eval_set=(Xte, yte), verbose=False)
    return model


def main():
    print('=== PIPELINE A (atual) ===')
    cards = json.loads(CACHE.read_text(encoding='utf-8'))
    dfA = pd.DataFrame([pm.parse_card(c) for c in cards])
    dfA['_raw'] = cards
    dfA = pm._enrich(dfA)
    dfA = pm.add_supply_features(dfA)
    dfA = dfA[dfA['target_price'].notna() & (dfA['target_price'] > 0)].copy()
    lb, li, smap = pm.build_liga_lookup()
    dfA = pm.enrich_brl(dfA, lb, li, smap)
    dfA = dfA[dfA['target_price_brl'].notna() & (dfA['target_price_brl'] > 0)].copy()
    dfA['target_price_usd'] = dfA['target_price'].fillna(dfA['target_price'].median())
    try:
        from script.tcgcsv_pricing import FEATS_TEMPORAIS
        extras = ['target_price_usd'] + [c for c in FEATS_TEMPORAIS if c in dfA.columns]
    except Exception:
        extras = ['target_price_usd']
    dfA['log_target'] = np.log1p(dfA['target_price_brl'])
    dfa = dfA.sort_values('release_year', na_position='first')
    sp = int(len(dfa) * 0.8)
    trA, teA = dfa.iloc[:sp], dfa.iloc[sp:]
    Xtr = pm.prepare_features(trA, extra_features=extras)
    Xte = pm.prepare_features(teA, extra_features=extras)
    cat_idx = [i for i, c in enumerate(Xtr.columns) if c in pm.CAT_FEATURES]
    mA = treina(Xtr, trA['log_target'], Xte, teA['log_target'], cat_idx)
    predA = mA.predict(Xte)
    realA = np.expm1(teA['log_target'].values)
    print(f"A: n={len(dfa)} | MAE teste R${mean_absolute_error(realA, predA):.2f} | "
          f"R² {r2_score(realA, predA):.4f} | erroRelMed safra-nova {err_rel_mediano(teA['log_target'].values, predA, teA['release_year'].values)}%")

    print('\n=== PIPELINE B (Liga-first) ===')
    cat_liga = json.loads(CAT_LIGA.read_text(encoding='utf-8'))
    # índice EN: id -> (rarity, hp, types, year, usd_market)
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
                       'ano': int(rd[:4]) if rd[:4].isdigit() else None,
                       'usd': mk}
    embdf = None
    if EMB.exists():
        embdf = pd.read_csv(EMB)
        embcols = [c for c in embdf.columns if c.startswith('emb_')]
        embmap = {r['id']: r[embcols].values.astype(np.float32) for _, r in embdf.iterrows()}
    else:
        embmap = {}
    rows = []
    for c in cat_liga:
        p1b = float(c.get('p1b') or 0)
        if p1b <= 0:
            continue
        eid = c.get('en_id')
        meta = en.get(eid, {}) if eid else {}
        rows.append({
            'sigla': c.get('sigla'), 'iCO': float(c.get('iCO') or 0),
            'iR': float(c.get('iR') or 0),
            'rar': meta.get('rar'), 'hp': meta.get('hp'), 'types': meta.get('types'),
            'ano': meta.get('ano'),
            'usd': meta.get('usd'),
            'tem_emb': 1.0 if eid in embmap else 0.0,
            **({f'emb_{i}': float(v) for i, v in enumerate(embmap[eid])} if eid in embmap else {f'emb_{i}': 0.0 for i in range(32)}),
            'y': np.log1p(p1b), 'liga_only': 1.0 if not eid else 0.0,
        })
    dfB = pd.DataFrame(rows)
    dfB['usd'] = dfB['usd'].fillna(dfB['usd'].median())
    cats = ['sigla', 'rar', 'types']
    for ccat in cats:
        dfB[ccat] = dfB[ccat].fillna('desconhecido').astype(str)
    dfB = dfB.sort_values('ano', na_position='first')  # sem ano -> primeiro (vão pro treino)
    spb = int(len(dfB) * 0.8)
    trB, teB = dfB.iloc[:spb], dfB.iloc[spb:]
    feats = ['iCO', 'iR', 'usd', 'tem_emb', 'liga_only'] + [f'emb_{i}' for i in range(32)]
    XtrB, XteB = trB[feats + cats], teB[feats + cats]
    cat_idxB = [XtrB.columns.get_loc(c) for c in cats]
    mB = treina(XtrB, trB['y'], XteB, teB['y'], cat_idxB)
    predB = mB.predict(XteB)
    realB = teB['y'].values
    anosB = teB['ano'].fillna(2026).values
    lo = teB['liga_only'].values.astype(bool)
    pl, rl = predB[lo], realB[lo]
    print(f"B: n={len(dfB)} ({int(dfB['liga_only'].sum())} liga_only) | MAE teste "
          f"R${mean_absolute_error(np.expm1(realB), np.expm1(predB)):.2f} | "
          f"R² {r2_score(realB, predB):.4f} | erroRelMed safra-nova {err_rel_mediano(realB, predB, anosB)}%")
    if len(rl) > 30:
        print(f"   subconjunto liga_only (n={len(rl)}): MAE R${mean_absolute_error(np.expm1(rl), np.expm1(pl)):.2f}")
    imp = sorted(zip(feats + cats, mB.get_feature_importance()), key=lambda t: -t[1])[:6]
    print('   top feats:', [(k, round(v, 1)) for k, v in imp])


if __name__ == '__main__':
    main()