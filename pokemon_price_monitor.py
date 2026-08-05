"""
pokemon_price_monitor.py
=========================
Pipeline de coleta → features → predição → monitoramento.
API: TCGdex (pt-BR) — estável, sem Cloudflare.
Preços: TCGPlayer USD via TCGdex.

Uso:
  python pokemon_price_monitor.py              # rodar completo
  python pokemon_price_monitor.py --status     # ver últimos snapshots
"""

import os, sys, json, time
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from catboost import CatBoostRegressor, CatBoostClassifier
from concurrent.futures import ThreadPoolExecutor, as_completed
from sklearn.metrics import mean_absolute_error, r2_score
sys.path.insert(0, str(Path(__file__).parent))
import pokemon_popularity as pop
import ptcg_io

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
MONITOR_DIR = DATA_DIR / 'monitoring'
MODEL_PATH = DATA_DIR / 'catboost_model.cbm'
BRL_MODEL_PATH = DATA_DIR / 'catboost_model_brl.cbm'
SNAPSHOT_LOG = MONITOR_DIR / '_snapshots.json'
TIMEOUT = 30
os.makedirs(MONITOR_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/131.0.0.0 Safari/537.36',
}
TCGDEX = 'https://api.tcgdex.net/v2'


# ── 1. Fetch (TCGdex) ─────────────────────────────────────────────

def fetch_json(url):
    """Fetch com retry e timeout."""
    import requests
    for attempt in range(1, 4):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code == 200:
                return resp.json()
            print(f'  Retry {attempt}/3 — status {resp.status_code}')
        except Exception as e:
            print(f'  Retry {attempt}/3 — {e}')
        time.sleep(2 ** attempt)
    return None


def fetch_all_sets():
    """Lista todos os sets via pokemontcg.io."""
    return ptcg_io.fetch_all_sets()


def fetch_set_cards(set_id):
    """Retorna cartas de um set via pokemontcg.io."""
    return ptcg_io.fetch_set_cards(set_id)


def fetch_card_pricing(card_id):
    """Busca pricing individual + raridade + variantes (pokemontcg.io)."""
    return ptcg_io.fetch_card_pricing(card_id)


# ── Gênero dos treinadores (P1.7) ─────────────────────────────────
# Dicionário explícito nome → gênero (fonte: Bulbapedia, canônico TCG).
# Substitui as listas antigas que tinham homens na lista feminina
# (Hop, Bede, Nanu, Hilbert, Nate, Curtis, Brendan, Lucas, Calem,
# Elio, Milo, Kabu) e mulheres na masculina (Misty, Erika, etc.).
TRAINER_GENDER = {
    # Kanto / Johto
    'brock': 'male', 'lt. surge': 'male', 'koga': 'male', 'giovanni': 'male',
    'lance': 'male', 'misty': 'female', 'erika': 'female', 'sabrina': 'female',
    'falkner': 'male', 'bugsy': 'male', 'whitney': 'female', 'morty': 'male',
    'chuck': 'male', 'jasmine': 'female', 'pryce': 'male', 'clair': 'female',
    'janine': 'female', 'professor oak': 'male', 'oak': 'male',
    'youngster': 'male', 'lass': 'female', 'beauty': 'female',
    'fisherman': 'male', 'hiker': 'male', 'bug catcher': 'male',
    'scientist': 'male', 'breeder': 'neutral', 'roughneck': 'male',
    'red': 'male', 'blue': 'male', 'green': 'female', 'yellow': 'female',
    'gold': 'male', 'silver': 'male', 'crystal': 'female', 'leaf': 'female',
    # Hoenn
    'steven': 'male', 'wallace': 'male', 'sydney': 'male', 'phoebe': 'female',
    'glacia': 'female', 'drake': 'male', 'roxanne': 'female', 'brawly': 'male',
    'wattson': 'male', 'flannery': 'female', 'norman': 'male', 'winona': 'female',
    'tate': 'male', 'liza': 'female', 'archie': 'male', 'maxie': 'male',
    'wally': 'male', 'may': 'female', 'brendan': 'male', 'courtney': 'female',
    'shelly': 'female', 'tabitha': 'male', 'matt': 'male',
    # Sinnoh
    'cyrus': 'male', 'mars': 'female', 'jupiter': 'female', 'saturn': 'male',
    'charon': 'male', 'candice': 'female', 'cynthia': 'female',
    'lucas': 'male', 'dawn': 'female', 'fantina': 'female', 'gardenia': 'female',
    'maylene': 'female', 'roark': 'male', 'byron': 'male', 'volkner': 'male',
    'aaron': 'male', 'bertha': 'female', 'flint': 'male', 'lucian': 'male',
    # Unova
    'ghetsis': 'male', 'cheren': 'male', 'bianca': 'female',
    'cilan': 'male', 'chili': 'male', 'cress': 'male', 'lenora': 'female',
    'burgh': 'male', 'elesa': 'female', 'clay': 'male', 'skyla': 'female',
    'brycen': 'male', 'drayden': 'male', 'iris': 'female',
    'hilbert': 'male', 'hilda': 'female', 'nate': 'male', 'rosa': 'female',
    'hugh': 'male', 'juniper': 'female', 'yancy': 'female', 'curtis': 'male',
    'shauntal': 'female', 'marshal': 'male', 'grimsley': 'male', 'caitlin': 'female',
    'alder': 'male', 'roxie': 'female', 'marlon': 'male', 'colress': 'male',
    'professor juniper': 'female',
    # Kalos
    'professor sycamore': 'male', 'diantha': 'female', 'serena': 'female',
    'calem': 'male', 'shauna': 'female', 'tierno': 'male', 'trevor': 'male',
    'viola': 'female', 'grant': 'male', 'korrina': 'female', 'ramos': 'male',
    'clemont': 'male', 'valerie': 'female', 'olympia': 'female', 'wulfric': 'male',
    'malva': 'female', 'siebold': 'male', 'wikstrom': 'male', 'drasna': 'female',
    # Alola
    'guzma': 'male', 'kukui': 'male', 'professor kukui': 'male', 'hau': 'male',
    'lillie': 'female', 'gladion': 'male', 'lusamine': 'female',
    'mallow': 'female', 'lana': 'female', 'kiawe': 'male', 'olivia': 'female',
    'sophocles': 'male', 'mina': 'female', 'hala': 'male', 'nanu': 'male',
    'hapu': 'female', 'acerola': 'female', 'kahili': 'female', 'molayne': 'male', 'ryuki': 'male',
    'selene': 'female', 'elio': 'male', 'plumeria': 'female', 'faba': 'male',
    # Galar
    'hop': 'male', 'bede': 'male', 'marnie': 'female', 'rose': 'male',
    'oleana': 'female', 'piers': 'male', 'raihan': 'male', 'leon': 'male',
    'victor': 'male', 'gloria': 'female', 'mustard': 'male', 'avery': 'male',
    'klara': 'female', 'peony': 'male', 'peonia': 'female',
    'sonia': 'female', 'professor magnolia': 'female', 'magnolia': 'female',
    'milo': 'male', 'nessa': 'female', 'kabu': 'male', 'bea': 'female',
    'allister': 'male', 'opal': 'female', 'gordie': 'male', 'melony': 'female',
    'melony': 'female',
    # Hisui / Paldea
    'geeta': 'female', 'sada': 'female', 'turo': 'male', 'arven': 'male',
    'nemona': 'female', 'clavell': 'male', 'larry': 'male', 'rika': 'female',
    'poppy': 'female', 'hassel': 'male', 'kieran': 'male', 'briar': 'female',
    'carmine': 'female', 'penny': 'female', 'juliana': 'female', 'florian': 'male',
    'iono': 'female', 'grusha': 'male', 'brassius': 'male', 'katy': 'female',
    'brains': 'male',
    # Outros / treinadores diversos
    'lisia': 'female', 'zinnia': 'female', 'team flare': 'male',
    'professor': 'male', 'pokémon breeder': 'neutral', 'breeder': 'neutral',
}

# Classes de treinador genéricas (fallback por palavra-chave)
TRAINER_CLASS_GENDER = {
    'youngster': 'male', 'lass': 'female', 'beauty': 'female',
    'fisherman': 'male', 'hiker': 'male', 'bug catcher': 'male',
    'scientist': 'male', 'roughneck': 'male', 'pokémon breeder': 'neutral',
    'breeder': 'neutral', 'team flare': 'male',
}


def infer_trainer_gender(name):
    """Infere gênero do treinador por nome canônico (dicionário explícito).

    Usa match de substring com fronteiras de palavra para nomes curtos
    (ex: 'N' não casa dentro de 'Lenora') e prioriza nomes mais longos.
    """
    if not name:
        return 'neutral'
    name_lower = str(name).lower().strip()

    # Caso especial: treinador N (Unova) — nome de 1 letra, aparece como
    # "N's Resolve" etc. Só casa se for a palavra inteira ou "n's ..."
    if name_lower == 'n' or name_lower.startswith("n's") or name_lower.startswith('n '):
        return 'male'

    # Match no dicionário: prioriza o nome mais longo que casar
    best = None
    for key, gender in TRAINER_GENDER.items():
        if key in name_lower and (best is None or len(key) > len(best)):
            best = key
    if best:
        return TRAINER_GENDER[best]

    # Fallback: classes de treinador
    for key, gender in TRAINER_CLASS_GENDER.items():
        if key in name_lower:
            return gender

    return 'neutral'


def fetch_all_cards(max_sets=50):
    """Coleta cartas de N sets via pokemontcg.io."""
    return ptcg_io.fetch_all_cards(max_sets=max_sets)


# ── 2. Parse (TCGdex → df) ─────────────────────────────────────────

def parse_card(c):
    """Extrai features de uma carta pokemontcg.io."""
    return ptcg_io.parse_card(c)


# ── 3a. Merge BRL (Liga Pokémon) ────────────────────────────────────

LIGA_PATH = DATA_DIR / 'liga' / 'liga_all_cards.csv'

def build_liga_lookup():
    """Constrói lookups de BRL + iCO + tcg_set → liga_sigla."""
    import re
    
    # Carrega mapping set_id (pokemontcg.io) → Liga sigla
    liga_map_path = DATA_DIR / 'liga' / 'liga_set_sigla_ptcg.json'
    if not liga_map_path.exists():
        liga_map_path = DATA_DIR / 'liga' / 'liga_set_sigla.json'  # fallback TCGdex
    if liga_map_path.exists():
        set_mapping = json.loads(liga_map_path.read_text())
    else:
        set_mapping = json.loads((BASE_DIR / 'set_mapping.json').read_text()) if (BASE_DIR / 'set_mapping.json').exists() else {}
    
    # Lookup Liga: (sigla, num) → preços + nome
    liga_dir = DATA_DIR / 'liga'
    lookup_brl = {}
    lookup_ico = {}
    
    for f in sorted(liga_dir.glob('set_[0-9]*.json')):
        with open(f) as fh:
            for c in json.load(fh):
                sigla = str(c.get('sSigla', '')).strip()
                num_m = re.search(r'\(?#?(\d+)', str(c.get('nEN', '')))
                if not num_m: continue
                num = int(num_m.group(1))
                p_med = float(c.get('p1b', 0) or 0)
                ico = c.get('iCO', 0) or 0
                
                if p_med > 0:
                    # Extrai nome do card do nEN (ex: "Stunky (#76/124)")
                    nome_liga = str(c.get('nEN', ''))
                    # Chave com sigla NORMALIZADA (upper) — os set_*.json da
                    # Liga têm siglas mixed-case (SV8a, M2a, SM12a) e o enrich
                    # testa upper/lower; normalizar aqui garante o match.
                    key = (sigla.upper(), num)
                    if key not in lookup_brl or p_med < lookup_brl[key].get('preco_medio_brl', float('inf')):
                        lookup_brl[key] = {
                            'preco_min_brl': float(c.get('p1a', 0) or 0),
                            'preco_medio_brl': p_med,
                            'preco_max_brl': float(c.get('p1c', 0) or 0),
                            'nome_liga': nome_liga,
                        }
                    if key not in lookup_ico or ico > lookup_ico[key][0]:
                        lookup_ico[key] = (ico, p_med)
    
    print(f'📦 Liga BRL: {len(lookup_brl)} cartas | iCO: {len(lookup_ico)} | sets mapeados: {len(set_mapping)}')
    return lookup_brl, lookup_ico, set_mapping


def enrich_brl(df_tcgdex, lookup_brl, lookup_ico, set_mapping):
    """Faz merge dos preços BRL usando (set_mapping[set_id], card_number)."""
    import re
    
    results = {'target_price_brl': [], 'preco_min_brl': [], 'preco_max_brl': [], 'iCO': []}
    matched = 0
    
    for _, row in df_tcgdex.iterrows():
        parts = str(row.get('id', '')).split('-')
        match_found = False
        if len(parts) == 2:
            tcg_set = parts[0]
            try: local_id = int(parts[1])
            except: local_id = None
            
            liga_sigla = set_mapping.get(tcg_set)
            if liga_sigla and local_id is not None:
                # Tenta case-insensitive
                for sigla_try in {liga_sigla, liga_sigla.upper(), liga_sigla.lower()}:
                    key = (sigla_try, local_id)
                    if key in lookup_brl:
                        brl = lookup_brl[key]
                        ico_data = lookup_ico.get(key, (0, 0))
                        matched += 1
                        results['target_price_brl'].append(brl.get('preco_medio_brl'))
                        results['preco_min_brl'].append(brl.get('preco_min_brl'))
                        results['preco_max_brl'].append(brl.get('preco_max_brl'))
                        results['iCO'].append(ico_data[0])
                        match_found = True
                        break
            
            if not match_found and local_id is not None:
                # Fallback: busca na Liga por NOME + número (prioriza siglas do mapping)
                card_name_key = str(row.get('name', '')).strip().lower() or str(row.get('name_en', '')).strip().lower()
                if card_name_key:
                    best = None
                    sigla_principal = set_mapping.get(tcg_set)
                    siglas_prioridade = {sigla_principal, sigla_principal.upper(), sigla_principal.lower()} if sigla_principal else set()
                    
                    # Primeira passada: só siglas do mapping
                    if siglas_prioridade:
                        for (b_sigla, b_num), b_val in lookup_brl.items():
                            if b_sigla not in siglas_prioridade or b_num != local_id:
                                continue
                            nen_key = str(b_val.get('nome_liga', '')).lower()
                            pokemon_name = re.sub(r'\s*\([^)]*\)\s*$', '', nen_key).strip()
                            if pokemon_name and (card_name_key in pokemon_name or pokemon_name in card_name_key):
                                best = (b_sigla, b_val)
                                break
                    
                    # Segunda passada: qualquer sigla
                    if best is None:
                        for (b_sigla, b_num), b_val in lookup_brl.items():
                            if b_num != local_id:
                                continue
                            nen_key = str(b_val.get('nome_liga', '')).lower()
                            pokemon_name = re.sub(r'\s*\([^)]*\)\s*$', '', nen_key).strip()
                            if pokemon_name and (card_name_key in pokemon_name or pokemon_name in card_name_key):
                                best = (b_sigla, b_val)
                                break
                    
                    # Terceira passada: match parcial
                    if best is None:
                        card_words = set(card_name_key.split())
                        for (b_sigla, b_num), b_val in lookup_brl.items():
                            if b_num != local_id:
                                continue
                            nen_key = str(b_val.get('nome_liga', '')).lower()
                            pokemon_name = re.sub(r'\s*\([^)]*\)\s*$', '', nen_key).strip()
                            if pokemon_name:
                                common = card_words & set(pokemon_name.split())
                                if len(common) >= 2 or (len(common) >= 1 and min(len(card_name_key), len(pokemon_name)) >= 5):
                                    # Match parcial só aceita se for da sigla principal
                                    if sigla_principal and b_sigla in {sigla_principal, sigla_principal.upper(), sigla_principal.lower()}:
                                        best = (b_sigla, b_val)
                                        break
                    
                    if best:
                        b_sigla, b_val = best
                        results['target_price_brl'].append(b_val.get('preco_medio_brl'))
                        results['preco_min_brl'].append(b_val.get('preco_min_brl'))
                        results['preco_max_brl'].append(b_val.get('preco_max_brl'))
                        ico_data = lookup_ico.get((b_sigla, local_id), (0, 0))
                        results['iCO'].append(ico_data[0])
                        matched += 1
                        match_found = True
        
        if not match_found:
            results['target_price_brl'].append(None)
            results['preco_min_brl'].append(None)
            results['preco_max_brl'].append(None)
            results['iCO'].append(0)
    
    print(f'💰 BRL (merge): {matched}/{len(df_tcgdex)} cartas')
    for k in results:
        df_tcgdex[k] = results[k]
    return df_tcgdex


# ── 3b. Pricing (busca individual TCGPlayer) ───────────────────────────

def enrich_pricing(df):
    """Busca pricing TCGPlayer USD.

    Se os cards já vieram com pricing embutido (pokemontcg.io traz
    tcgplayer/cardmarket no payload), usa direto. Caso contrário,
    faz requisições paralelas individuais.
    """
    # Verifica se o df ainda tem o payload bruto (came de ptcg_io.fetch_all_cards)
    # A coluna '_raw' é anexada por train_model/run_snapshot quando disponível
    has_raw = '_raw' in df.columns

    total = len(df)
    if has_raw:
        print(f'\n📡 Usando pricing embutido ({total} cartas)...')
        results = df['_raw'].apply(fetch_card_pricing)
        df_prices = pd.DataFrame(results.tolist())
    else:
        cids = df['id'].str.replace('pt/', '', regex=False).tolist()
        print(f'\n📡 Buscando preços ({total} cartas, 20 threads)...')
        results = [{}] * total
        done_count = 0

        with ThreadPoolExecutor(max_workers=20) as executor:
            fut_map = {executor.submit(fetch_card_pricing, cid): i for i, cid in enumerate(cids)}
            for fut in as_completed(fut_map):
                idx = fut_map[fut]
                results[idx] = fut.result()
                done_count += 1
                if done_count % 200 == 0:
                    print(f'  Preços: {done_count}/{total}')

        df_prices = pd.DataFrame(results)

    df['target_price'] = df_prices['target_price_usd']
    df['price_type'] = df_prices['price_type']
    df['rarity_tcg'] = df_prices['rarity_tcg'].fillna('Unknown')
    df['is_holo'] = df_prices['is_holo'].fillna(False).astype(int)
    df['is_reverse'] = df_prices['is_reverse'].fillna(False).astype(int)
    df['is_normal'] = df_prices['is_normal'].fillna(False).astype(int)
    df['is_shiny'] = df_prices['is_shiny'].fillna(0).astype(int)
    df['illustrator'] = df_prices['illustrator'].fillna('')
    df['trainer_gender'] = df_prices['trainer_gender'].fillna('neutral')
    # Precos historicos Cardmarket
    df['cardmarket_avg'] = pd.to_numeric(df_prices['cardmarket_avg'], errors='coerce')
    df['cardmarket_avg1'] = pd.to_numeric(df_prices['cardmarket_avg1'], errors='coerce')
    df['cardmarket_avg7'] = pd.to_numeric(df_prices['cardmarket_avg7'], errors='coerce')
    df['cardmarket_avg30'] = pd.to_numeric(df_prices['cardmarket_avg30'], errors='coerce')
    df['cardmarket_trend'] = pd.to_numeric(df_prices['cardmarket_trend'], errors='coerce')
    df['cardmarket_low'] = pd.to_numeric(df_prices['cardmarket_low'], errors='coerce')
    df['cardmarket_updated'] = df_prices['cardmarket_updated'].fillna('')
    # Nome EN vindo do endpoint individual (mais confiável)
    en_names = df_prices['name_en'].fillna('')
    df['name_en'] = df['name_en'].combine_first(en_names)
    # rarity pura (sem mapping)
    df['rarity'] = df['rarity_tcg']
    has_price = df['target_price'].notna().sum()
    print(f'  Cartas com preço: {has_price}/{total}')
    return df


# ── 4. Features ─────────────────────────────────────────────────────

CAT_FEATURES = ['rarity_tcg', 'primary_type', 'set_series', 'price_type', 'supertype', 'illustrator', 'trainer_gender']
# Embeddings: dinov2-base + cls+mean + PCA32 (vencedor das ablações, Ago/2026)
N_EMB = 32
EMBEDDINGS_FILE = DATA_DIR / 'pokemon_embeddings_base32.csv'

# Precos historicos (cardmarket)
CM_FEATURES = ['cardmarket_avg', 'cardmarket_avg1', 'cardmarket_avg7', 'cardmarket_avg30', 'cardmarket_trend', 'cardmarket_low']
# Flags binarias de arte
ART_FEATURES = ['is_holo', 'is_reverse', 'is_normal', 'is_shiny', 'is_legendary']
# Grail score e popularidade
NUM_FEATURES = ['hp', 'subtypes_count', 'set_printed_total', 'release_year', 'card_age_years', 'pokedex_number', 'pokemon_popularity', 'iCO', 'pokemon_grail_score'] + CM_FEATURES + ART_FEATURES + [f'emb_{i}' for i in range(N_EMB)]
# Features de supply (E1): pool de raridade + pull cost
SUPPLY_FEATURES = ['rarity_pool_size', 'pull_cost_log']
NUM_FEATURES = NUM_FEATURES + SUPPLY_FEATURES
NUM_FEATURES_BRL = NUM_FEATURES + ['target_price_usd']  # USD price como feature para modelo BRL
FEATURE_COLS = CAT_FEATURES + NUM_FEATURES

# ── 4b. Supply: Pull Cost & Rarity Pool (E1) ───────────────────────

# Packs estimados para acertar UMA carta do slot de raridade
# (aproximação pública da era moderna; varia por set — usado como baseline)
PULL_RATE_PACKS = {
    'Common': 1/6, 'Uncommon': 1/4, 'Rare': 1/2, 'Rare Holo': 5,
    'Double Rare': 7, 'Ultra Rare': 9, 'Illustration Rare': 11,
    'Rare Ultra': 18, 'Special Illustration Rare': 45, 'Rare Secret': 65,
    'Rare Rainbow': 90, 'Rare Holo V': 12, 'Rare Holo VMAX': 15,
    'Rare Holo VSTAR': 15, 'Rare Holo EX': 12, 'Rare BREAK': 15,
    'LEGEND': 20, 'Promo': 1, 'Unknown': 5,
}

def pack_price_estimado(release_year):
    """Preço médio de booster (USD) por era."""
    if release_year is None:
        return 4.0
    if release_year >= 2020:
        return 4.5
    if release_year >= 2014:
        return 4.0
    if release_year >= 2003:
        return 3.5
    return 3.0  # WOTC


def add_supply_features(df):
    """E1: features de oferta — rarity_pool_size e pull_cost.

    rarity_pool_size: quantas cartas competem no mesmo slot (set × raridade).
    pull_cost: custo monetário estimado para puxar a carta específica:
        pull_cost = pack_price × packs_por_carta(raridade) × rarity_pool_size
    (mesma lógica do PokeDataDadGuy: pull rate × pool size × pack price)

    Deve ser chamado ANTES de filtrar por preço, para o pool refletir
    o set completo (não só as cartas com preço).
    """
    df = df.copy()

    # Pool: quantas cartas competem no mesmo slot (set_id, rarity_tcg)
    if 'rarity_pool_size' not in df.columns:
        pool = df.groupby(['set_id', 'rarity_tcg']).size().reset_index(name='rarity_pool_size')
        df = df.merge(pool, on=['set_id', 'rarity_tcg'], how='left')
        df['rarity_pool_size'] = df['rarity_pool_size'].fillna(1).clip(lower=1)

    # Pack price por era
    if 'pack_price_est' not in df.columns:
        df['pack_price_est'] = df['release_year'].apply(pack_price_estimado)

    # Packs p/ acertar 1 carta do slot (fator por raridade)
    if 'packs_por_carta' not in df.columns:
        df['packs_por_carta'] = df['rarity_tcg'].map(PULL_RATE_PACKS).fillna(5.0)

    # Pull cost = pack_price × (packs/1 carta do slot) × pool_size
    if 'pull_cost_log' not in df.columns:
        pull_cost = df['pack_price_est'] * df['packs_por_carta'] * df['rarity_pool_size']
        df['pull_cost_log'] = np.log1p(pull_cost)

    return df

# ── 4c. Grail Score & Legendary ────────────────────────────────────
GRAIL_SCORE = {
    'charizard': 10, 'pikachu': 9, 'mewtwo': 9, 'mew': 8, 'lugia': 8,
    'ho-oh': 8, 'rayquaza': 8, 'gengar': 9, 'umbreon': 8, 'eevee': 7,
    'espeon': 7, 'dragonite': 7, 'gyarados': 7, 'blastoise': 7,
    'venusaur': 7, 'tyranitar': 7, 'mimikyu': 6, 'lucario': 6,
    'greninja': 6, 'gardevoir': 6, 'sylveon': 7, 'glaceon': 6,
    'leafeon': 6, 'vaporeon': 6, 'flareon': 6, 'jolteon': 6,
    'charmander': 8, 'charmeleon': 8, 'charizard': 10,
    'squirtle': 6, 'wartortle': 6, 'blastoise': 7,
    'bulbasaur': 6, 'ivysaur': 6, 'venusaur': 7,
    'celebi': 7, 'jirachi': 7, 'deoxys': 7, 'miltank': 5,
    'darkrai': 7, 'latias': 7, 'latios': 7, 'keldeo': 6,
}

LEGENDARY_DEX = {144, 145, 146, 150, 151, 243, 244, 245, 249, 250,
                 377, 378, 379, 380, 381, 382, 383, 384, 385, 386,
                 480, 481, 482, 483, 484, 485, 486, 487, 488, 489, 490, 491, 492, 493,
                 494, 638, 639, 640, 641, 642, 643, 644, 645, 646, 647, 648, 649,
                 716, 717, 718, 719, 720, 721,
                 772, 773, 785, 786, 787, 788, 789, 790, 791, 792, 793, 794, 795, 796, 797, 798, 799, 800, 801, 802,
                 803, 804, 805, 806, 807,
                 888, 889, 890, 891, 892, 893, 894, 895, 896, 897, 898,
                 899, 900, 901, 902, 903, 904, 905,
                 984, 985, 986, 987, 988, 989, 990, 991, 992, 993, 994, 995, 996, 997, 998, 999, 1000, 1001, 1002, 1003, 1004}

def calc_grail_score(name, name_en, dex_id):
    """Calcula grail score (0-10) para um Pokémon."""
    if not name and not name_en:
        return 0
    name_lower = (str(name) + ' ' + str(name_en)).lower()
    
    # Tenta match direto no dicionário
    for pokemon, score in GRAIL_SCORE.items():
        if pokemon in name_lower:
            return score
    
    # Fallback: lendários/míticos ganham 4 se não estiverem no dicionário
    try:
        dex_int = int(float(dex_id)) if dex_id is not None and str(dex_id) != 'nan' else None
    except (TypeError, ValueError):
        dex_int = None
    if dex_int and dex_int in LEGENDARY_DEX:
        return 4
    
    return 0

def is_legendary(dex_id):
    """Retorna 1 se o Pokémon é lendário/mítico."""
    try:
        dex_int = int(float(dex_id)) if dex_id is not None and str(dex_id) != 'nan' else None
    except (TypeError, ValueError):
        dex_int = None
    if not dex_int:
        return 0
    return 1 if dex_int in LEGENDARY_DEX else 0


def prepare_features(df, extra_features=None):
    """Prepara features (numéricas + categóricas) para o modelo.
    
    Args:
        df: DataFrame com as cartas.
        extra_features: Lista opcional de features extras p/ incluir (ex: target_price_usd no BRL).
    """
    # Carrega embeddings
    emb_cache = getattr(prepare_features, '_emb_cache', None)
    if emb_cache is None:
        if EMBEDDINGS_FILE.exists():
            emb_cache = pd.read_csv(EMBEDDINGS_FILE)
            emb_cache.columns = emb_cache.columns.str.strip()
            prepare_features._emb_cache = emb_cache
        else:
            prepare_features._emb_cache = pd.DataFrame()
    
    # Features úteis
    extra_features = extra_features or []
    feature_cols_total = FEATURE_COLS + [c for c in extra_features if c not in FEATURE_COLS]
    
    X = df[[c for c in ['id'] + feature_cols_total if c in df.columns]].copy() if df is not None else pd.DataFrame()
    
    # Popularidade por nome
    import pokemon_popularity as pop
    if 'name_en' in df.columns and 'pokemon_popularity' not in X.columns:
        X['pokemon_popularity'] = df['name_en'].apply(
            lambda n: pop.get_popularity(n) if pd.notna(n) else 10.0
        )
    elif 'pokemon_popularity' not in X.columns:
        X['pokemon_popularity'] = 10.0
    
    # iCO default
    if 'iCO' not in X.columns:
        X['iCO'] = 0
    
    # Grail score
    X['pokemon_grail_score'] = df.apply(
        lambda r: calc_grail_score(r.get('name', ''), r.get('name_en', ''), r.get('pokedex_number', None)),
        axis=1
    ) if 'pokemon_grail_score' not in X.columns else X['pokemon_grail_score']
    
    # Legendary flag
    X['is_legendary'] = df.apply(
        lambda r: is_legendary(r.get('pokedex_number', None)),
        axis=1
    ) if 'is_legendary' not in X.columns else X['is_legendary']
    
    # Merge embeddings
    if not emb_cache.empty:
        X = X.merge(emb_cache, on='id', how='left')
        for i in range(N_EMB):
            col = f'emb_{i}'
            if col in X.columns:
                X[col] = X[col].fillna(0.0)
            else:
                X[col] = 0.0
    
    # Categorias
    for c in CAT_FEATURES:
        if c in X.columns:
            X[c] = X[c].astype(str)
    
    # Fallbacks
    X['pokemon_popularity'] = X.get('pokemon_popularity', 0.0)
    if 'pokemon_popularity' in X.columns:
        X['pokemon_popularity'] = pd.to_numeric(X['pokemon_popularity'], errors='coerce').fillna(0.0)
    else:
        X['pokemon_popularity'] = 10.0
    
    # Seleciona apenas as features disponíveis
    avail = [c for c in feature_cols_total if c in X.columns]
    X = X[avail].copy()
    # Fallbacks E1 (supply) — caso o df não tenha passado por add_supply_features
    if 'rarity_pool_size' in feature_cols_total and 'rarity_pool_size' not in X.columns:
        X['rarity_pool_size'] = 1
    if 'pull_cost_log' in feature_cols_total and 'pull_cost_log' not in X.columns:
        X['pull_cost_log'] = 0.0
    X['hp'] = X['hp'].fillna(X['hp'].median())
    X['set_printed_total'] = X['set_printed_total'].fillna(X['set_printed_total'].median())
    X['release_year'] = X['release_year'].fillna(2016)
    X['card_age_years'] = X['card_age_years'].fillna(10)
    X['pokedex_number'] = X['pokedex_number'].fillna(0).astype(int)
    X['iCO'] = X.get('iCO', 0).fillna(0) if isinstance(X.get('iCO', 0), pd.Series) else 0
    X['pokemon_grail_score'] = pd.to_numeric(X.get('pokemon_grail_score', 0)).fillna(0).astype(int)
    if 'target_price_usd' in X.columns:
        X['target_price_usd'] = X['target_price_usd'].fillna(0)
    # Flags de arte default
    for col in ['is_holo', 'is_reverse', 'is_normal', 'is_shiny', 'is_legendary']:
        if col not in X.columns:
            X[col] = 0
        else:
            X[col] = X[col].fillna(0).astype(int)
    X = X.infer_objects(copy=False)
    return X


# ── 5. Modelo ───────────────────────────────────────────────────────

def train_model(max_sets=20, cards=None):
    print('\n📦 Treinando modelo...')
    if cards is None:
        cards = fetch_all_cards(max_sets=max_sets)
    df = pd.DataFrame([parse_card(c) for c in cards])
    df['_raw'] = cards  # payload bruto com pricing embutido (pokemontcg.io)
    df = enrich_pricing(df)
    df = add_supply_features(df)  # E1: rarity_pool_size + pull_cost (antes do filtro)
    df = df[df['target_price'].notna() & (df['target_price'] > 0)].copy()
    df['log_target'] = np.log1p(df['target_price'])

    cat_idx = [i for i, c in enumerate(FEATURE_COLS) if c in CAT_FEATURES]

    # Split temporal: 80% antigas treino, 20% recentes teste
    df_sorted = df.sort_values('release_year', na_position='first')
    split = int(len(df_sorted) * 0.8)
    train_df = df_sorted.iloc[:split]
    test_df = df_sorted.iloc[split:]

    X_train = prepare_features(train_df)
    y_train = train_df['log_target']
    X_test = prepare_features(test_df)
    y_test = test_df['log_target']

    print(f'  Treino: {len(train_df)} | Teste: {len(test_df)} (split temporal)')

    model = CatBoostRegressor(
        iterations=500, learning_rate=0.05, depth=6,
        l2_leaf_reg=3, loss_function='MAE', eval_metric='MAE',
        cat_features=cat_idx, verbose=50, random_seed=42,
        early_stopping_rounds=30,
    )
    model.fit(X_train, y_train, eval_set=(X_test, y_test), verbose=50)

    # Métricas separadas
    for nome, X_eval, y_eval in [('Treino', X_train, y_train), ('Teste', X_test, y_test)]:
        pred_log = model.predict(X_eval)
        pred = np.expm1(pred_log)
        real = np.expm1(y_eval.values)
        mae = mean_absolute_error(real, pred)
        r2 = r2_score(real, pred)
        print(f'  MAE {nome}: ${mae:.2f}  |  R² {nome}: {r2:.4f}')

    model.save_model(str(MODEL_PATH))
    print(f'✅ Modelo salvo em {MODEL_PATH} (melhor iteração: {model.get_best_iteration()})')
    
    # Classificador de faixa de preço
    print()
    train_price_classifier(X_train, train_df['log_target'], X_test, test_df['log_target'], cat_idx, prefix='USD ')
    return model


# ── 5c. Classificador de faixa de preço ─────────────────────────────

PRICE_BINS = ['Muito barato', 'Barato', 'Médio', 'Caro', 'Muito caro']

def train_price_classifier(X_train, y_train_price, X_test, y_test_price, cat_idx, prefix=''):
    """Treina classificador de faixa de preço (5 bins por percentil)."""
    from sklearn.metrics import accuracy_score, f1_score, confusion_matrix
    
    # Bins por percentil (20% cada) em log-scale
    bins = y_train_price.quantile([0, 0.2, 0.4, 0.6, 0.8, 1.0]).values
    bins = np.array(bins, dtype=float)
    bins[0] = -np.inf
    bins[-1] = np.inf
    labels = list(range(5))
    
    y_train_cls = pd.cut(y_train_price, bins=bins, labels=labels, include_lowest=True)
    y_test_cls = pd.cut(y_test_price, bins=bins, labels=labels, include_lowest=True)
    
    model_cls = CatBoostClassifier(
        iterations=300, learning_rate=0.05, depth=6,
        loss_function='MultiClass', eval_metric='Accuracy',
        cat_features=cat_idx, verbose=0, random_seed=42,
        early_stopping_rounds=30,
    )
    model_cls.fit(X_train, y_train_cls, eval_set=(X_test, y_test_cls), verbose=0)
    
    for nome, X_eval, y_eval in [('Treino', X_train, y_train_cls), ('Teste', X_test, y_test_cls)]:
        pred = model_cls.predict(X_eval).flatten()
        acc = accuracy_score(y_eval, pred)
        f1 = f1_score(y_eval, pred, average='weighted')
        print(f'  {prefix}Cls {nome}: Acc={acc:.2%} | F1={f1:.3f}')
    
    # Matriz de confusão
    y_pred_test = model_cls.predict(X_test).flatten()
    cm = confusion_matrix(y_test_cls, y_pred_test)
    print(f'  {prefix}Matriz de confusão (teste):')
    for i in range(len(cm)):
        line = f'    Bin {PRICE_BINS[i]:15s}: '
        for j in range(len(cm[i])):
            line += f'{cm[i][j]:4d} '
        print(line)
    real_bins = np.expm1(bins[1:5])
    if prefix == 'BRL ':
        print(f'    Limites: R${real_bins[0]:.2f}, R${real_bins[1]:.2f}, R${real_bins[2]:.2f}, R${real_bins[3]:.2f}')
    else:
        print(f'    Limites: ${real_bins[0]:.2f}, ${real_bins[1]:.2f}, ${real_bins[2]:.2f}, ${real_bins[3]:.2f}')
    
    return model_cls


def load_model():
    if MODEL_PATH.exists():
        model = CatBoostRegressor()
        model.load_model(str(MODEL_PATH))
        print(f'📦 Modelo carregado de {MODEL_PATH}')
        return model
    return train_model()


# ── 5b. Modelo BRL ────────────────────────────────────────────────

def train_model_brl(max_sets=50, cards=None):
    """Treina modelo com target BRL (preços brasileiros).

    cards: lista opcional de cards já buscados (evita re-fetch e rate limit).
    """
    print('\n📦 Treinando modelo BRL...')
    if cards is None:
        cards = fetch_all_cards(max_sets=max_sets)
    df = pd.DataFrame([parse_card(c) for c in cards])
    df['_raw'] = cards
    df = enrich_pricing(df)
    df = add_supply_features(df)  # E1: rarity_pool_size + pull_cost (antes do filtro)
    df = df[df['target_price'].notna() & (df['target_price'] > 0)].copy()
    
    # Merge BRL
    _lookup_brl, _lookup_ico, _set_map = build_liga_lookup()
    df = enrich_brl(df, _lookup_brl, _lookup_ico, _set_map)
    df = df[df['target_price_brl'].notna() & (df['target_price_brl'] > 0)].copy()
    
    if len(df) < 100:
        print(f'⚠️  Poucas cartas BRL ({len(df)}). Pulando treino.')
        return None
    
    df['log_target_brl'] = np.log1p(df['target_price_brl'])
    
    # USD price como feature de entrada para o modelo BRL
    df['target_price_usd'] = df['target_price'].fillna(df['target_price'].median())
    
    # Split temporal: 80% antigas treino, 20% recentes teste
    df_sorted = df.sort_values('release_year', na_position='first')
    split = int(len(df_sorted) * 0.8)
    train_df = df_sorted.iloc[:split]
    test_df = df_sorted.iloc[split:]
    
    X_train = prepare_features(train_df, extra_features=['target_price_usd'])
    y_train = train_df['log_target_brl']
    X_test = prepare_features(test_df, extra_features=['target_price_usd'])
    y_test = test_df['log_target_brl']
    
    cat_idx = [i for i, c in enumerate(X_train.columns) if c in CAT_FEATURES]
    
    print(f'  Treino: {len(train_df)} | Teste: {len(test_df)} (split temporal BRL)')
    
    model = CatBoostRegressor(
        iterations=500, learning_rate=0.05, depth=6,
        l2_leaf_reg=3, loss_function='MAE', eval_metric='MAE',
        cat_features=cat_idx, verbose=50, random_seed=42,
        early_stopping_rounds=30,
    )
    model.fit(X_train, y_train, eval_set=(X_test, y_test), verbose=50)
    
    # Métricas separadas
    for nome, X_eval, y_eval in [('Treino', X_train, y_train), ('Teste', X_test, y_test)]:
        pred_log = model.predict(X_eval)
        pred = np.expm1(pred_log)
        real = np.expm1(y_eval.values)
        mae = mean_absolute_error(real, pred)
        r2 = r2_score(real, pred)
        print(f'  MAE {nome}: R${mae:.2f}  |  R² {nome}: {r2:.4f}')
    
    model.save_model(str(BRL_MODEL_PATH))
    print(f'✅ Modelo BRL salvo em {BRL_MODEL_PATH} ({len(df)} cartas, melhor iteração: {model.get_best_iteration()})')
    
    # Classificador de faixa de preço
    print()
    train_price_classifier(X_train, train_df['log_target_brl'], X_test, test_df['log_target_brl'], cat_idx, prefix='BRL ')
    return model


def load_model_brl():
    if BRL_MODEL_PATH.exists():
        model = CatBoostRegressor()
        model.load_model(str(BRL_MODEL_PATH))
        print(f'📦 Modelo BRL carregado de {BRL_MODEL_PATH}')
        return model
    return train_model_brl()


# ── 6. Snapshot ─────────────────────────────────────────────────────

def run_snapshot(model=None, max_sets=50):
    print(f'\n{"="*50}')
    print(f'📸 Snapshot: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print(f'{"="*50}')

    cards = fetch_all_cards(max_sets=50)        # ~13000 cartas
    print(f'\n📥 {len(cards)} cartas coletadas')
    if not cards:
        print('⚠️  Nenhuma carta coletada.')
        return None

    df = pd.DataFrame([parse_card(c) for c in cards])
    df['_raw'] = cards  # payload com pricing embutido
    print(f'📊 Metadados: {df.shape}')

    df = enrich_pricing(df)
    df = add_supply_features(df)  # E1: rarity_pool_size + pull_cost (antes do filtro)
    df_valid = df[df['target_price'].notna() & (df['target_price'] > 0)].copy()
    print(f'💰 USD: {len(df_valid)} cartas com preço')

    # BRL
    _lookup_brl, _lookup_ico, _set_map = build_liga_lookup()
    df_valid = enrich_brl(df_valid, _lookup_brl, _lookup_ico, _set_map)

    if model is None:
        model = load_model()

    X = prepare_features(df_valid)
    log_pred = model.predict(X)
    df_valid['predicted_price'] = np.expm1(log_pred)
    df_valid['residual_usd'] = df_valid['target_price'] - df_valid['predicted_price']
    df_valid['residual_pct'] = (df_valid['residual_usd'] / df_valid['target_price'] * 100).clip(-500, 500)
    df_valid['snapshot_date'] = datetime.now().strftime('%Y-%m-%d %H:%M')

    # Predição BRL
    tem_brl = df_valid['target_price_brl'].notna().sum()
    if tem_brl > 50:
        model_brl = load_model_brl()
        if model_brl:
            brl_idx = df_valid['target_price_brl'].notna()
            # USD price é feature do modelo BRL (como no treino) — sem isso o
            # predict falha/divergia (shape diferente do treino)
            df_valid['target_price_usd'] = df_valid['target_price'].fillna(df_valid['target_price'].median())
            X_brl = prepare_features(df_valid[brl_idx], extra_features=['target_price_usd'])
            log_pred_brl = model_brl.predict(X_brl)
            df_valid.loc[brl_idx, 'predicted_price_brl'] = np.expm1(log_pred_brl)
            df_valid.loc[brl_idx, 'residual_brl'] = df_valid.loc[brl_idx, 'target_price_brl'] - df_valid.loc[brl_idx, 'predicted_price_brl']
            print(f'  BRL: {tem_brl} cartas, MAE R${df_valid.loc[brl_idx, "residual_brl"].abs().mean():.2f}')

    resid_std = df_valid['residual_usd'].std()
    df_valid['is_outlier'] = df_valid['residual_usd'].abs() > 2 * resid_std

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = MONITOR_DIR / f'snapshot_{ts}.csv'
    df_valid.to_csv(path, index=False)
    print(f'💾 Salvo: {path} ({len(df_valid)} cartas)')

    print(f'\n📈 RESUMO')
    print(f'  Preço USD médio:     ${df_valid["target_price"].mean():.2f}')
    print(f'  Preço predito médio: ${df_valid["predicted_price"].mean():.2f}')
    print(f'  MAE (USD):           ${df_valid["residual_usd"].abs().mean():.2f}')
    print(f'  Outliers detectados: {df_valid["is_outlier"].sum()}')
    if df_valid['target_price_brl'].notna().sum() > 0:
        b = df_valid['target_price_brl'].dropna()
        print(f'  Preço BRL médio:      R${b.mean():.2f} ({len(b)} cartas)')
    if 'predicted_price_brl' in df_valid.columns and df_valid['predicted_price_brl'].notna().sum() > 0:
        print(f'  MAE (BRL):            R${df_valid["residual_brl"].abs().mean():.2f}')
        print(f'  Predito BRL médio:    R${df_valid["predicted_price_brl"].mean():.2f}')

    last_path = get_last_snapshot()
    if last_path:
        prev = pd.read_csv(last_path)
        merged = df_valid.merge(
            prev[['id', 'target_price']].rename(columns={'target_price': 'prev_price'}),
            on='id', how='inner'
        )
        if len(merged) > 0:
            merged['price_delta'] = merged['target_price'] - merged['prev_price']
            merged['price_delta_pct'] = merged['price_delta'] / merged['prev_price'] * 100
            big = merged[merged['price_delta_pct'].abs() > 20].sort_values('price_delta_pct', ascending=False)
            if len(big) > 0:
                print(f'\n⚠️  VARIAÇÃO >20% (top 10):')
                for _, r in big.head(10).iterrows():
                    print(f'  {r["id"]:15s} {r["name"]:25s} '
                          f'${r["prev_price"]:>7.2f} → ${r["target_price"]:>7.2f} '
                          f'({r["price_delta_pct"]:+.1f}%)')

    update_snapshot_log(ts, len(df_valid))
    return df_valid


# ── 6b. Escoragem em dados de hits e snapshots semanais ────────────

LIGA_SCORE_DIR = DATA_DIR / 'scored'
LIGA_SCORE_DIR.mkdir(parents=True, exist_ok=True)
HITS_DIR = DATA_DIR / 'liga'

def score_hits(model=None, model_brl=None):
    """Escora os arquivos de hits e snapshots semanais com o modelo treinado.
    Marca cartas baratas (predito > real) como oportunidades.
    """
    from pathlib import Path
    import glob

    if model is None:
        model = load_model()
    if model_brl is None:
        model_brl = load_model_brl()

    # Carrega dados pokemontcg.io (features) para match com os hits
    print('\n📦 Carregando features pokemontcg.io...')
    cards = fetch_all_cards(max_sets=50)
    df_base = pd.DataFrame([parse_card(c) for c in cards])
    df_base['_raw'] = cards
    df_base = enrich_pricing(df_base)
    df_base = add_supply_features(df_base)  # E1: rarity_pool_size + pull_cost

    _lookup_brl, _lookup_ico, _set_map = build_liga_lookup()

    resultados = []

    # 1. Escorar arquivos de hits
    import json
    hits_files = sorted(glob.glob(str(HITS_DIR / '*alta*.json')) + glob.glob(str(HITS_DIR / '*queda*.json')))
    print(f'\n📊 Escorando {len(hits_files)} arquivos de hits...')

    for fpath in hits_files:
        fname = Path(fpath).name
        if not Path(fpath).exists():
            continue
        hits_data = json.loads(Path(fpath).read_text())
        if not hits_data:
            continue

        df_hits = pd.DataFrame(hits_data)

        # Converte id pra string no hits
        if 'id' in df_hits.columns:
            df_hits['id'] = df_hits['id'].astype(str)
        elif 'IDE_CartaUnica' in df_hits.columns:
            # IDs da Liga são numericos, mas TCGdex é string "base1-1"
            # Precisamos match por nome mesmo
            pass

        # Tenta match por sNomeIngles ou nEN com nome TCGdex
        df_hits['nome_match'] = ''
        if 'sNomeIngles' in df_hits.columns:
            df_hits['nome_match'] = df_hits['sNomeIngles'].str.lower().str.strip()
        elif 'sNomePortugues' in df_hits.columns:
            df_hits['nome_match'] = df_hits['sNomePortugues'].str.lower().str.strip()
        elif 'nome' in df_hits.columns:
            df_hits['nome_match'] = df_hits['nome'].str.lower().str.strip()

        # Adiciona número da carta se disponível (desambigua)
        df_hits['card_num'] = ''
        if 'sNumber' in df_hits.columns:
            df_hits['card_num'] = df_hits['sNumber'].str.strip()
        elif 'sN' in df_hits.columns:
            df_hits['card_num'] = df_hits['sN'].str.strip()

        # Match com base TCGdex: tentar (nome, numero) primeiro
        df_base['nome_match'] = df_base.get('name_en', df_base['name']).str.lower().str.strip()
        # Extrair numero do id TCGdex (ex: base1-4 -> "4")
        df_base['card_num'] = df_base['id'].str.split('-').str[-1]
        # Remove leading zeros
        df_base['card_num'] = df_base['card_num'].str.lstrip('0')

        merged_total = 0
        # Match nível 1: nome + número
        if df_hits['card_num'].str.len().sum() > 0:
            df_merged = df_hits.merge(df_base[['id', 'nome_match', 'card_num', 'target_price']],
                                      on=['nome_match', 'card_num'], how='inner', suffixes=('', '_tcg'))
            merged_total += len(df_merged)
        else:
            df_merged = pd.DataFrame()

        # Match nível 2: só nome (quando não tem número)
        df_hits_semn = df_hits[~df_hits['nome_match'].isin(df_merged['nome_match'])] if len(df_merged) > 0 else df_hits
        if len(df_hits_semn) > 0:
            mais = df_hits_semn.merge(df_base[['id', 'nome_match', 'target_price']],
                                      on='nome_match', how='inner', suffixes=('', '_tcg'))
            df_merged = pd.concat([df_merged, mais], ignore_index=True) if len(df_merged) > 0 else mais
            merged_total += len(mais)

        df_merged = df_merged.drop_duplicates(subset=['id'] + [c for c in df_merged.columns if c != 'fonte'] if 'fonte' in df_merged.columns else ['id'])

        if len(df_merged) == 0:
            continue

        # Prepara features: escora df_base e match por liga_id
        df_base_feat = df_base.copy()
        df_base_feat['id'] = df_base_feat['id'].astype(str)

        X_base = prepare_features(df_base_feat)
        for c in CAT_FEATURES:
            if c in X_base.columns:
                X_base[c] = X_base[c].fillna('Unknown').astype(str)
        pred_log_all = model.predict(X_base)
        df_base_feat['predicted_price'] = np.expm1(pred_log_all)

        # Cria liga_id no df_base_feat
        import json
        set_sigla_path = DATA_DIR / 'liga' / 'liga_set_sigla_ptcg.json'
        if not set_sigla_path.exists():
            set_sigla_path = DATA_DIR / 'liga' / 'liga_set_sigla.json'
        set_sigla = json.loads(set_sigla_path.read_text()) if set_sigla_path.exists() else {}

        def tcgdex_to_liga_id(tcg_id):
            parts = str(tcg_id).split('-')
            if len(parts) != 2: return None
            sigla = set_sigla.get(parts[0])
            if not sigla: return None
            return sigla.upper() + '-' + parts[1].lstrip('0')

        df_base_feat['liga_id'] = df_base_feat['id'].apply(tcgdex_to_liga_id)

        # Cria liga_id nos hits
        df_hits['liga_id'] = (df_hits['sSigla'].str.strip().str.upper() + '-' +
                               df_hits['sNumber'].str.strip().str.lstrip('0'))

        # Match nivel 1: liga_id
        merged_liga = df_hits.merge(
            df_base_feat[['liga_id', 'predicted_price', 'target_price']],
            on='liga_id', how='inner')
        df_result = merged_liga.copy()

        # Match nivel 2: fallback nome + numero
        if len(merged_liga) < len(df_hits):
            hit_ids_l = set(merged_liga['liga_id']) if len(merged_liga) > 0 else set()
            rest = df_hits[~df_hits['liga_id'].isin(hit_ids_l)].copy()
            nome_col = ('sNomeIngles' if 'sNomeIngles' in rest.columns
                        else ('sNomePortugues' if 'sNomePortugues' in rest.columns else None))
            if nome_col:
                rest['nome_match'] = rest[nome_col].str.lower().str.strip()
                rest['card_num'] = rest['sNumber'].str.strip().str.lstrip('0')
                df_base_feat['nome_match'] = df_base_feat.get('name_en', df_base_feat['name']).str.lower().str.strip()
                df_base_feat['card_num'] = df_base_feat['id'].str.split('-').str[-1].str.lstrip('0')
                mais = rest.merge(
                    df_base_feat[['nome_match', 'card_num', 'predicted_price', 'target_price']],
                    on=['nome_match', 'card_num'], how='inner')
                if len(mais) > 0:
                    df_result = pd.concat([df_result, mais], ignore_index=True) if len(df_result) > 0 else mais

        if len(df_result) == 0:
            continue

        df_result['residual'] = df_result['target_price'] - df_result['predicted_price']
        df_result['residual_pct'] = (df_result['residual'] / df_result['target_price'] * 100).clip(-500, 500)
        df_result['oportunidade'] = df_result['residual_pct'].apply(
            lambda x: '🔥 Barata' if x > 30 else ('👍 Leve' if x > 10 else ('💀 Cara' if x < -30 else ''))
        )
        df_result['fonte'] = fname
        df_result['data_score'] = datetime.now().strftime('%Y-%m-%d %H:%M')

        resultados.append(df_result)

    if not resultados:
        print('  Nenhum hit com match encontrado.')
        return

    df_out = pd.concat(resultados, ignore_index=True)

    # Top oportunidades
    baratas = df_out[df_out['oportunidade'] == '🔥 Barata'].sort_values('residual_pct', ascending=False)
    caras = df_out[df_out['oportunidade'] == '💀 Cara'].sort_values('residual_pct')

    print(f'\n🏆 OPORTUNIDADES ENCONTRADAS')
    print(f'  🔥 Baratas (pred >30% acima do real): {len(baratas)}')
    print(f'  👍 Leves (pred 10-30% acima):         {len(df_out[df_out["oportunidade"] == "👍 Leve"])}')
    print(f'  💀 Caras (real >30% acima do pred):   {len(caras)}')

    if len(baratas) > 0:
        print(f'\n🔥 Top 10 baratas:')
        for _, r in baratas.head(10).iterrows():
            nome = r.get('nome', r.get('sNomePortugues', r.get('name', '?')))
            tgt = 'target_price'
            prd = 'predicted_price'
            pct = 'residual_pct'
            src = 'fonte'
            print(f'  {nome:35s} | Real: ${r[tgt]:>7.2f} | Pred: ${r[prd]:>7.2f} | Diff: {r[pct]:+.0f}% | Fonte: {str(r.get(src,""))[:20]}')

    if len(caras) > 0:
        print(f'\n💀 Top 10 caras (superfaturadas):')
        for _, r in caras.head(10).iterrows():
            nome = r.get('nome', r.get('sNomePortugues', r.get('name', '?')))
            tgt = 'target_price'
            prd = 'predicted_price'
            pct = 'residual_pct'
            print(f'  {nome:35s} | Real: ${r[tgt]:>7.2f} | Pred: ${r[prd]:>7.2f} | Diff: {r[pct]:+.0f}%')

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = LIGA_SCORE_DIR / f'scored_hits_{ts}.csv'
    df_out.to_csv(path, index=False)
    print(f'\n💾 Salvo: {path} ({len(df_out)} linhas)')
    return df_out


def score_snapshot(snapshot_path=None, model=None, model_brl=None):
    """Escora o snapshot semanal com o modelo atual e marca oportunidades."""
    if snapshot_path is None:
        snapshot_path = get_last_snapshot()
        if snapshot_path is None:
            print('  Nenhum snapshot encontrado.')
            return None

    print(f'\n📊 Escorando snapshot: {Path(snapshot_path).name}')
    df_snap = pd.read_csv(snapshot_path)

    # Garante id como string
    df_snap['id'] = df_snap['id'].astype(str)

    # Carrega modelos
    if model is None:
        model = load_model()
    if model_brl is None:
        model_brl = load_model_brl() if BRL_MODEL_PATH.exists() else None

    # Busca base pokemontcg.io para features
    cards = fetch_all_cards(max_sets=50)
    df_base = pd.DataFrame([parse_card(c) for c in cards])
    df_base['_raw'] = cards
    df_base = enrich_pricing(df_base)
    df_base = add_supply_features(df_base)  # E1: rarity_pool_size + pull_cost
    df_base['id'] = df_base['id'].astype(str)

    X_base = prepare_features(df_base)
    for c in CAT_FEATURES:
        if c in X_base.columns:
            X_base[c] = X_base[c].fillna('Unknown').astype(str)

    # Predicao USD
    pred_usd = np.expm1(model.predict(X_base))
    df_base['predicted_price'] = pred_usd

    # Predicao BRL (se modelo existe)
    if model_brl is not None:
        try:
            pred_brl = np.expm1(model_brl.predict(X_base))
            df_base['predicted_price_brl'] = pred_brl
        except Exception:
            pass

    # Merge com snapshot
    cols = ['id', 'predicted_price']
    if 'predicted_price_brl' in df_base.columns:
        cols.append('predicted_price_brl')
    df_out = df_snap.merge(df_base[cols], on='id', how='left', suffixes=('', '_novo'))

    # Se o snapshot ja tinha predicao, prefere a nova
    if 'predicted_price_novo' in df_out.columns:
        df_out['predicted_price'] = df_out['predicted_price_novo'].fillna(df_out['predicted_price'])
        df_out.drop(columns=['predicted_price_novo'], inplace=True)
    if 'predicted_price_brl_novo' in df_out.columns:
        df_out['predicted_price_brl'] = df_out['predicted_price_brl_novo'].fillna(df_out['predicted_price_brl'])
        df_out.drop(columns=['predicted_price_brl_novo'], inplace=True)

    # Marca oportunidades: compara real vs pred
    # Usa BRL se disponivel, senao USD
    if 'target_price_brl' in df_out.columns:
        df_out['tem_brl'] = df_out['target_price_brl'].notna() & (df_out['target_price_brl'] > 0) & df_out['predicted_price_brl'].notna()
    else:
        df_out['tem_brl'] = False

    df_out['real_ref'] = np.where(df_out['tem_brl'], df_out['target_price_brl'], df_out['target_price'])
    df_out['pred_ref'] = np.where(df_out['tem_brl'], df_out['predicted_price_brl'], df_out['predicted_price'])

    # Marca oportunidades: compara prediz vs real
    # Se PREDIÇÃO > REAL: a carta está SUBVALORIZADA (ótima oportunidade de compra)
    # Se REAL > PREDIÇÃO: a carta está SOBREVALORIZADA / INFLACIONADA no mercado
    df_out['diff_pct'] = ((df_out['pred_ref'] - df_out['real_ref']) / df_out['real_ref'] * 100).clip(-500, 500)
    df_out['oportunidade'] = df_out['diff_pct'].apply(
        lambda x: '🔥 Subvalorizada' if x > 25 else ('👍 Leve Desconto' if x > 10 else ('💀 Inflacionada' if x < -25 else '⚖️ Preço Justo'))
    )

    baratas = df_out[df_out['oportunidade'] == '🔥 Subvalorizada'].sort_values('diff_pct', ascending=False)
    caras = df_out[df_out['oportunidade'] == '💀 Inflacionada'].sort_values('diff_pct')

    print(f'\n🏆 OPORTUNIDADES NO SNAPSHOT')
    print(f'  Total cartas: {len(df_out)}')
    print(f'  🔥 Subvalorizadas (Pred > Real +25%): {len(baratas)}')
    print(f'  👍 Leve Desconto (Pred > Real +10-25%): {len(df_out[df_out["oportunidade"] == "👍 Leve Desconto"])}')
    print(f'  ⚖️ Preço Justo (-25% a +10%):           {len(df_out[df_out["oportunidade"] == "⚖️ Preço Justo"])}')
    print(f'  💀 Inflacionadas (Real > Pred +25%):   {len(caras)}')

    if len(baratas) > 0:
        print(f'\n🔥 Top 15 Subvalorizadas (Oportunidades de Compra):')
        for _, r in baratas.head(15).iterrows():
            nome = r.get('name', r.get('name_en', '?'))
            real = r['real_ref']
            pred = r['pred_ref']
            moeda = 'R$' if r['tem_brl'] else '$'
            print(f'  {str(nome):35s} | Real: {moeda}{real:>8.2f} | Pred: {moeda}{pred:>8.2f} | Upside: {r["diff_pct"]:+.0f}%')

    if len(caras) > 0:
        print(f'\n💀 Top 10 Inflacionadas (evitar compra):')
        for _, r in caras.head(10).iterrows():
            nome = r.get('name', r.get('name_en', '?'))
            real = r['real_ref']
            pred = r['pred_ref']
            moeda = 'R$' if r['tem_brl'] else '$'
            print(f'  {str(nome):35s} | Real: {moeda}{real:>8.2f} | Pred: {moeda}{pred:>8.2f} | Upside: {r["diff_pct"]:+.0f}%')

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = LIGA_SCORE_DIR / f'scored_snapshot_{ts}.csv'
    df_out.to_csv(path, index=False)
    print(f'\n💾 Salvo: {path} ({len(df_out)} linhas)')
    return df_out


# ── 7. Utilitários ─────────────────────────────────────────────────

def get_last_snapshot():
    files = sorted(MONITOR_DIR.glob('snapshot_*.csv'))
    return files[-1] if files else None


def update_snapshot_log(ts, count):
    log = []
    if SNAPSHOT_LOG.exists():
        with open(SNAPSHOT_LOG) as f:
            log = json.load(f)
    log.append({'ts': ts, 'date': datetime.now().strftime('%Y-%m-%d %H:%M'), 'count': count, 'source': 'tcgdex'})
    with open(SNAPSHOT_LOG, 'w') as f:
        json.dump(log[-50:], f, indent=2)


def show_status():
    if not SNAPSHOT_LOG.exists():
        print('Nenhum snapshot encontrado.')
        return
    with open(SNAPSHOT_LOG) as f:
        log = json.load(f)
    print(f'\n📋 HISTÓRICO DE SNAPSHOTS ({len(log)} execuções)')
    print(f'{"Data":<22} {"Cartas":<8} Fonte')
    print('-' * 50)
    for entry in reversed(log[-10:]):
        print(f'{entry["date"]:<22} {entry["count"]:<8} {entry.get("source","pokemontcg")}')


if __name__ == '__main__':
    if '--status' in sys.argv:
        show_status()
    else:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('--max-sets', type=int, default=50, help='Limite de sets (mais recentes)')
        parser.add_argument('--train-brl', action='store_true', help='Só treina modelo BRL')
        args, _ = parser.parse_known_args()
        
        import requests
        import time
        model = load_model()
        run_snapshot(model, max_sets=args.max_sets)
