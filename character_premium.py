"""
character_premium.py
====================
E2: Character Premium & Artist Premium — demanda de verdade.

Calcula, a partir dos preços reais do cache pokemontcg.io:
  - character_premium: quanto um Pokémon comanda de prêmio sobre a mediana
    da sua era (normalizado por release_year para remover efeito de inflação).
    Ex: Charizard ~1.1x, Umbreon ~1.3x, Mew ~1.4x (lógica do PokeDataDadGuy).
  - artist_premium: quanto um ilustrador comanda de prêmio sobre a mediana
    da era (captura "artist clout" — ex: Shinji Kanda Magikarp).

Método:
  premium(pokemon) = mediana(preço_carta / mediana_preço_era) por pokémon
  - Preço relativo à era remove o efeito temporal (cartas antigas naturalmente caras).
  - Mediana por pokémon resiste a outliers (1 carta absurda não domina).

Saídas (cache em data/):
  - data/character_premium.json  {pokedex_number: float}
  - data/artist_premium.json     {artist_name: float}

Uso:
  python character_premium.py                # recalcula a partir do cache
  from character_premium import get_character_premium, get_artist_premium
"""

import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
CHAR_PATH = DATA_DIR / 'character_premium.json'
ARTIST_PATH = DATA_DIR / 'artist_premium.json'
CACHE_PATH = DATA_DIR / 'ptcg_cards_cache.json'


def _mediana_por_era(df):
    """Rank percentil do preço dentro da década (remove efeito temporal).

    Usa rank percentil (0-1) do preço dentro da década em vez de razão,
    porque a distribuição de preços é muito assimétrica (mediana 2020+ é
    ~$0.23, com cauda longa de SIRs caras). Rank é robusto a outliers e
    mede exatamente "quão premium é a carta vs. contemporâneos".
    """
    if 'release_year' not in df.columns or df['release_year'].isna().all():
        return pd.Series(0.5, index=df.index)
    df = df.copy()
    df['decada'] = (df['release_year'] // 10) * 10
    rank = df.groupby('decada')['target_price'].rank(pct=True)
    return rank


def compute_premiums(df=None):
    """Calcula character_premium (por pokedex) e artist_premium (por artista).

    df: DataFrame com colunas id, name, pokedex_number, illustrator,
        release_year, target_price. Se None, carrega do cache.
    Retorna (dict pokedex->premium, dict artista->premium).

    Método (sem vazamento):
      - rank percentil do preço dentro da década (0-1)
      - leave-one-out: o premium de um pokémon/artista é a MÉDIA do rank
        das OUTRAS cartas do mesmo grupo (exclui a própria carta, evitando
        que a carta use o próprio preço como feature)
      - escala: premium = rank_loo / 0.5 → 1.0 = típico, ~2x = top
    """
    if df is None:
        sys.path.insert(0, str(BASE_DIR))
        import pokemon_price_monitor as pm

        cache_path = CACHE_PATH
        if not cache_path.exists():
            import ptcg_io
            cards = ptcg_io.fetch_all_cards_global()
            cache_path.write_text(json.dumps(cards, ensure_ascii=False), encoding='utf-8')
        cards = json.loads(cache_path.read_text(encoding='utf-8'))
        df = pd.DataFrame([pm.parse_card(c) for c in cards])
        df['_raw'] = cards
        df = pm.enrich_pricing(df)

    df = df[df['target_price'].notna() & (df['target_price'] > 0)].copy()
    if len(df) < 100:
        print('⚠️  Poucas cartas com preço para calcular premiums.')
        return {}, {}

    # Artista vem do payload bruto (campo illustrator fica vazio no modelo
    # p/ evitar cardinalidade alta; o sinal é capturado por artist_premium)
    if 'illustrator' not in df.columns or df['illustrator'].isna().all() or (df['illustrator'] == '').all():
        raw_col = df['_raw'] if '_raw' in df.columns else None
        if raw_col is not None:
            df['illustrator'] = raw_col.apply(lambda c: (c.get('artist') or '') if isinstance(c, dict) else '')

    df['rank_era'] = _mediana_por_era(df)

    def _normalizar_loo(grupo_col, min_n=4):
        """Leave-one-out: média do rank das OUTRAS cartas do grupo.

        soma_loo = (soma_rank - rank_carta) / (n - 1), só para n >= min_n.
        Depois converte p/ multiplicador (rank/0.5) com clip [0.1, 4].
        """
        sub = df[df[grupo_col].notna() & (df[grupo_col] != '')].copy()
        g = sub.groupby(grupo_col)['rank_era']
        soma = g.transform('sum')
        n = g.transform('count')
        loo_media = (soma - sub['rank_era']) / (n - 1).clip(lower=1)
        prem = pd.Series(1.0, index=sub.index)
        valido = n >= min_n
        prem.loc[valido] = np.clip(loo_media[valido] / 0.5, 0.1, 4.0)
        # Agrega: mediana do premium LOO por grupo
        return prem.groupby(sub[grupo_col]).median().to_dict()

    char = {}
    if 'pokedex_number' in df.columns:
        char = _normalizar_loo('pokedex_number')
        char = {int(k): round(float(v), 3) for k, v in char.items()}

    art = {}
    if 'illustrator' in df.columns:
        art = _normalizar_loo('illustrator')
        art = {str(k): round(float(v), 3) for k, v in art.items()}

    # Salva
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CHAR_PATH.write_text(json.dumps(char, ensure_ascii=False), encoding='utf-8')
    ARTIST_PATH.write_text(json.dumps(art, ensure_ascii=False), encoding='utf-8')

    print(f'💎 Character premium: {len(char)} pokémons | Artist premium: {len(art)} artistas')
    return char, art


# ── Lookups em memória ──────────────────────────────────────────────

_char_cache = None
_artist_cache = None


def _load():
    global _char_cache, _artist_cache
    if _char_cache is None:
        _char_cache = json.loads(CHAR_PATH.read_text(encoding='utf-8')) if CHAR_PATH.exists() else {}
        _artist_cache = json.loads(ARTIST_PATH.read_text(encoding='utf-8')) if ARTIST_PATH.exists() else {}


def get_character_premium(pokedex_number):
    """Retorna o premium de um Pokémon (1.0 = mediana da era, >1 = premium)."""
    _load()
    if pokedex_number is None:
        return 1.0
    try:
        return _char_cache.get(str(int(pokedex_number)), 1.0)
    except (TypeError, ValueError):
        return 1.0


def get_artist_premium(artist):
    """Retorna o premium de um artista (1.0 = mediana da era)."""
    _load()
    if not artist:
        return 1.0
    return _artist_cache.get(str(artist), 1.0)


if __name__ == '__main__':
    compute_premiums()
    # Top 15 por premium
    ch, ar = _char_cache, _artist_cache
    _load()
    print('\n🏆 TOP 15 CHARACTER PREMIUM:')
    for dex, p in sorted(_char_cache.items(), key=lambda x: -x[1])[:15]:
        print(f'  dex #{dex:4s}  {p:.2f}x')
    print('\n🎨 TOP 15 ARTIST PREMIUM:')
    for a, p in sorted(_artist_cache.items(), key=lambda x: -x[1])[:15]:
        print(f'  {a:28s} {p:.2f}x')
