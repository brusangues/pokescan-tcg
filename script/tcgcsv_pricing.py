"""
script/tcgcsv_pricing.py — PREÇOS TCGCSV como fonte primária do modelo (produção).

Substitui o tcgplayer do pokemontcg.io como LABEL/preço USD (validado no A/B:
B(tcgcsv) ganha de A(cache) em R² e MAE nos dois alvos). Cardmarket EUR,
imagens e metadados continuam do pokemontcg.io.

enrich_pricing(df) -> df (mesma interface do pm.enrich_pricing):
  1. roda o enrich original (cardmarket, flags de arte, rarity, ...
     — do cache pokemontcg.io)
  2. sobrepõe target_price/price_type com o TCGCSV (última semana do
     histórico; fallback = preço do cache p/ cartas sem TCGCSV)
  3. anexa as features temporais t_* (histórico semanal)

Seguro: se os dados TCGCSV não existirem (experiments/tcgcsv/ vazio),
vira no-op e o fluxo antigo segue funcionando.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
import pokemon_price_monitor as pm
from script.tcgcsv_lib import ler_historico, preco_ultima_semana, bloco_semana

FEATS_TEMPORAIS = ['t_price_principal', 't_price_normal', 't_price_holo', 't_price_reverse',
                   't_ret_1w', 't_ret_4w', 't_ret_8w', 't_mom_4w', 't_vol_8w',
                   't_spread_rev_norm', 't_spread_rev_norm_rel', 't_n_semanas']

_cache = {}


def _tabelas():
    """(preco, variante, temporais) por card — cacheado por sessão."""
    if not _cache:
        try:
            hist = ler_historico()
            preco, variante, semana = preco_ultima_semana(hist)
            temporais = bloco_semana(hist, semana)
            _cache.update({'preco': preco, 'variante': variante,
                           'temporais': temporais, 'semana': semana,
                           'ok': True})
        except Exception as e:
            print(f'⚠️  TCGCSV indisponível ({e}) — usando apenas pokemontcg.io', flush=True)
            _cache['ok'] = False
    return _cache


def disponivel() -> bool:
    return bool(_tabelas().get('ok'))


def enrich_pricing(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich completo: base do cache + sobreposição TCGCSV + temporais."""
    df = pm.enrich_pricing(df)
    if not disponivel():
        return df
    t = _tabelas()
    ids = df['id'].astype(str)
    has = ids.isin(t['preco'])
    if has.any():
        df = df.copy()
        df['target_price'] = np.where(has, ids.map(t['preco']), df['target_price'])
        df['price_type'] = np.where(has, ids.map(t['variante']), df['price_type'])
        df['fonte_preco'] = np.where(has, 'tcgcsv', 'cache')
    else:
        df['fonte_preco'] = 'cache'
    tmp = t['temporais'].reindex(ids.values)
    for c in FEATS_TEMPORAIS:
        df[c] = tmp[c].values
    df['tem_tcgcsv'] = has.astype(int)
    return df