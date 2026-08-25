"""brl_liga.py — Modelo BRL LIGA-FIRST (Fase 3/P1.32).

Base de treino: data/catalogo_liga.json (p1b = preço mercado BRL da Liga).
Features: iR, iCO, sigla, rar/types/ano/usd via en_id (join EN), embeddings DINOv2
(32d) via en_id. USD é FEATURE, não dirige a base.

API:
  treinar()            -> treina e salva data/catboost_model_brl_liga.cbm (+meta json)
  carregar()           -> (model, meta) ou (None, None)
  prever(df_liga)      -> coluna pred_brl_liga p/ DataFrame com colunas do catálogo

Consumo: score_apos_crawl.predict_base junta por card_id Liga ({idE}-{num}) e usa
pred_brl_liga quando existir; senão cai no pred_brl atual.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
CAT_LIGA = BASE / 'data' / 'catalogo_liga.json'
CACHE = BASE / 'data' / 'ptcg_cards_cache.json'
EMB = BASE / 'data' / 'pokemon_embeddings_base32.csv'
MODEL_PATH = BASE / 'data' / 'catboost_model_brl_liga.cbm'
META_PATH = BASE / 'data' / 'catboost_model_brl_liga_meta.json'

CATS = ['sigla', 'rar', 'types']
NUMS = ['iR', 'iCO', 'usd']
FEATS = NUMS + CATS  # sem embeddings na v1 (custo de join baixo; emb não ajudou no A/B)


def _indice_en():
    cards = json.loads(CACHE.read_text(encoding='utf-8'))
    idx = {}
    for c in cards:
        pr = ((c.get('tcgplayer') or {}).get('prices') or {})
        mk = None
        for k in ('holofoil', 'normal'):
            if pr.get(k, {}).get('market'):
                mk = pr[k]['market']; break
        rd = str((c.get('set') or {}).get('releaseDate') or '')
        idx[c['id']] = {
            'rar': str(c.get('rarity') or 'desconhecido'),
            'types': ','.join(c.get('types') or []) or 'desconhecido',
            'usd': float(mk) if mk else np.nan,
        }
    return idx


def montar_dataset():
    """DataFrame de treino/scoring a partir do catálogo da Liga."""
    cat = json.loads(CAT_LIGA.read_text(encoding='utf-8'))
    idx = _indice_en()
    rows = []
    for c in cat:
        p1b = float(c.get('p1b') or 0)
        if p1b <= 0:
            continue
        meta = idx.get(c.get('en_id'), {}) if c.get('en_id') else {}
        rows.append({
            'card_id': f"{c['idE']}-{c['num']}",
            'sigla': str(c.get('sigla') or 'desconhecido'),
            'iR': float(c.get('iR') or 0), 'iCO': float(c.get('iCO') or 0),
            'rar': meta.get('rar', 'desconhecido'),
            'types': meta.get('types', 'desconhecido'),
            'usd': meta.get('usd', np.nan),
            'y': np.log1p(p1b),
        })
    df = pd.DataFrame(rows)
    df['usd'] = df['usd'].fillna(df['usd'].median())
    for c in CATS:
        df[c] = df[c].astype(str)
    return df


def treinar(verbose=True):
    from catboost import CatBoostRegressor
    df = montar_dataset()
    if verbose:
        print(f'BRL-Liga dataset: {len(df)} cartas '
              f'({int((df["sigla"].notna()).sum())} linhas)')
    model = CatBoostRegressor(iterations=600, learning_rate=0.05, depth=6,
                              l2_leaf_reg=3, loss_function='MAE', eval_metric='MAE',
                              cat_features=[df[FEATS].columns.get_loc(c) for c in CATS],
                              verbose=False, random_seed=42)
    model.fit(df[FEATS], df['y'])
    model.save_model(str(MODEL_PATH))
    META_PATH.write_text(json.dumps({
        'feats': FEATS, 'cats': CATS, 'n_treino': len(df),
        'fonte': 'data/catalogo_liga.json (p1b)', 'versao': 'fase3-v1',
    }, ensure_ascii=False, indent=1))
    if verbose:
        print(f'✅ {MODEL_PATH.name} salvo ({len(df)} cartas)')
    return model


_carregado = None


def carregar():
    global _carregado
    if _carregado is not None:
        return _carregado
    try:
        from catboost import CatBoostRegressor
        m = CatBoostRegressor()
        m.load_model(str(MODEL_PATH))
        meta = json.loads(META_PATH.read_text(encoding='utf-8'))
        _carregado = (m, meta)
    except Exception:
        _carregado = (None, None)
    return _carregado


def prever(df_liga: pd.DataFrame):
    """df_liga: colunas card_id/sigla/iR/iCO (+en_id opcional p/ usd/rar/types).
    Retorna Series pred_brl_liga (NaN onde não aplicável)."""
    model, meta = carregar()
    if model is None or df_liga is None or len(df_liga) == 0:
        return pd.Series(np.nan, index=df_liga.index if df_liga is not None else None)
    idx = _indice_en()
    rows = []
    for _, r in df_liga.iterrows():
        eid = r.get('en_id')
        meta_en = idx.get(eid, {}) if eid else {}
        rows.append({
            'iR': float(r.get('iR') or 0), 'iCO': float(r.get('iCO') or 0),
            'usd': float(meta_en['usd']) if meta_en.get('usd') is not None else np.nan,
            'sigla': str(r.get('sigla') or 'desconhecido'),
            'rar': str(meta_en.get('rar', 'desconhecido')),
            'types': str(meta_en.get('types', 'desconhecido')),
        })
    X = pd.DataFrame(rows)
    mediana = MODEL_MEDIANA.get('usd')
    if mediana is not None:
        X['usd'] = X['usd'].fillna(mediana)
    for c in CATS:
        X[c] = X[c].astype(str)
    return pd.Series(model.predict(X[FEATS]), index=df_liga.index)


MODEL_MEDIANA = {}


def _carregar_mediana():
    """Mediana de usd usada no treino (para imputar no predict igual ao treino)."""
    global MODEL_MEDIANA
    if MODEL_MEDIANA:
        return
    try:
        df = montar_dataset()
        MODEL_MEDIANA['usd'] = float(df['usd'].median())
    except Exception:
        MODEL_MEDIANA['usd'] = None


_idx_en_cache = None


def indice_en():
    """Índice EN cacheado (o cache ptcg tem ~100MB — NUNCA recarregar por linha)."""
    global _idx_en_cache
    if _idx_en_cache is None:
        _idx_en_cache = _indice_en()
    return _idx_en_cache


def prever_linhas(df_liga: pd.DataFrame):
    """Prediz BRL em LOTE p/ DataFrame c/ colunas card_id/sigla/iR/iCO.
    Junta as features do catálogo por card_id '{idE}-{num}'; NaN fora da cobertura."""
    model, meta = carregar()
    if model is None or df_liga is None or len(df_liga) == 0:
        return pd.Series(np.nan, index=df_liga.index)
    _carregar_mediana()
    ien = indice_en()
    cat = json.loads(CAT_LIGA.read_text(encoding='utf-8'))
    idx_cat = {}
    for cl in cat:
        if float(cl.get('p1b') or 0) > 0:
            idx_cat[f"{cl['idE']}-{cl['num']}"] = cl
    med_usd = MODEL_MEDIANA.get('usd')
    rows, out_idx = [], []
    for pos, r in df_liga.iterrows():
        parts = str(r.get('card_id') or '').split('-')
        chave = f'{parts[0]}-{parts[2]}' if len(parts) == 3 else ''
        cl = idx_cat.get(chave)
        if cl is None:
            continue
        eid = cl.get('en_id')
        me = ien.get(eid, {}) if eid else {}
        rows.append({
            'iR': float(cl.get('iR') or 0), 'iCO': float(cl.get('iCO') or 0),
            'usd': float(me['usd']) if me.get('usd') is not None else (med_usd or np.nan),
            'sigla': str(cl.get('sigla') or 'desconhecido'),
            'rar': str(me.get('rar', 'desconhecido')),
            'types': str(me.get('types', 'desconhecido')),
        })
        out_idx.append(pos)
    if not rows:
        return pd.Series(np.nan, index=df_liga.index)
    X = pd.DataFrame(rows)
    X['usd'] = X['usd'].fillna(med_usd) if med_usd is not None else X['usd'].fillna(0)
    for c in CATS:
        X[c] = X[c].astype(str)
    preds = np.expm1(model.predict(X[FEATS]))
    return pd.Series(preds, index=out_idx).reindex(df_liga.index)


def prever_linha(cl: dict):
    """Prediz BRL p/ UMA linha do catalogo_liga.json. None se fora de cobertura."""
    model, meta = carregar()
    if model is None:
        return None
    _carregar_mediana()
    idx = _indice_en()
    eid = cl.get('en_id')
    me = idx.get(eid, {}) if eid else {}
    X = pd.DataFrame([{
        'iR': float(cl.get('iR') or 0), 'iCO': float(cl.get('iCO') or 0),
        'usd': float(me['usd']) if me.get('usd') is not None else (MODEL_MEDIANA.get('usd') or np.nan),
        'sigla': str(cl.get('sigla') or 'desconhecido'),
        'rar': str(me.get('rar', 'desconhecido')),
        'types': str(me.get('types', 'desconhecido')),
    }])
    for c in CATS:
        X[c] = X[c].astype(str)
    return float(np.expm1(model.predict(X[FEATS])[0]))


if __name__ == '__main__':
    treinar()
    # sanity: prediz para 3 linhas do próprio catálogo
    df = montar_dataset().head(50)
    _carregar_mediana()
    p = prever(df)
    real = np.expm1(df['y'].values)
    er = np.abs(np.expm1(p.values) - real) / np.maximum(real, .01)
    print(f'sanity in-sample: erroRelMed {100*np.median(er):.1f}% em {len(df)} cartas')