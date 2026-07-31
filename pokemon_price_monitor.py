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
    """Lista todos os sets disponíveis em pt-BR."""
    data = fetch_json(f'{TCGDEX}/pt/sets')
    if not data:
        return []
    print(f'  Sets disponíveis: {len(data)}')
    return data


def fetch_set_cards(set_id):
    """Retorna cartas de um set com dados completos. Tenta pt-BR, fallback EN."""
    data = fetch_json(f'{TCGDEX}/pt/sets/{set_id}')
    if not data:
        return []
    cards = data.get('cards', [])
    # Se vazio em pt-BR, tenta EN
    if not cards:
        data_en = fetch_json(f'{TCGDEX}/en/sets/{set_id}')
        if data_en:
            cards = data_en.get('cards', [])
            # Usa nome pt-BR do set se disponível
            if cards:
                pass
    set_info = {
        'set_id': data.get('id', set_id),
        'set_name': data.get('name', ''),
        'set_series': data.get('series', ''),
        'set_release_date': data.get('releaseDate', ''),
        'set_printed_total': data.get('cardCount', {}).get('total', 0),
    }
    for c in cards:
        c['_set'] = set_info
    return cards


def fetch_card_pricing(card_id):
    """Busca pricing individual + raridade + variantes de uma carta."""
    clean_id = card_id.replace('pt/', '')
    data = fetch_json(f'{TCGDEX}/en/cards/{clean_id}')
    if not data:
        return {}
    pricing = data.get('pricing', {})
    tcg = pricing.get('tcgplayer', {}) if pricing else {}
    holofoil = tcg.get('holofoil', {}) if tcg else {}
    normal = tcg.get('normal', {}) if tcg else {}
    
    # Extrai info de arte/raridade
    rarity_tcg = data.get('rarity', 'Unknown')
    variants = data.get('variants', {}) or {}
    variants_detailed = data.get('variants_detailed', [])
    
    # Flags de arte
    is_holo = variants.get('holo', False) or any(v.get('type') == 'holo' for v in variants_detailed)
    is_reverse = variants.get('reverse', False)
    is_normal = variants.get('normal', False)
    
    # Nome em inglês (da EN endpoint)
    name_en = data.get('name', '')
    illustrator = data.get('illustrator', '')
    shiny_name = 'shiny' in name_en.lower() or 'brilhante' in data.get('name', '').lower()
    
    # Gênero do treinador
    category = data.get('category', '')
    trainer_gender = 'neutral'
    if category == 'Trainer' or category == 'Supporter':
        trainer_gender = infer_trainer_gender(name_en)
    
    return {
        'target_price_usd': holofoil.get('marketPrice') or normal.get('marketPrice'),
        'price_type': 'holofoil' if holofoil.get('marketPrice') else ('normal' if normal.get('marketPrice') else None),
        'rarity_tcg': rarity_tcg,
        'is_holo': is_holo,
        'is_reverse': is_reverse,
        'is_normal': is_normal,
        'name_en': name_en,
        'illustrator': illustrator,
        'is_shiny': int(shiny_name),
        'trainer_gender': trainer_gender,
    }


def infer_trainer_gender(name):
    if not name:
        return 'neutral'
    male_keywords = [
        'Brock', 'Misty', 'Lt. Surge', 'Erika', 'Koga', 'Sabrina', 'Giovanni',
        'Lance', 'Steven', 'Wallace', 'Sidney', 'Phoebe', 'Glacia', 'Drake',
        'Roxanne', 'Brawly', 'Wattson', 'Flannery', 'Norman', 'Winona', 'Tate', 'Liza',
        'Skye', 'Archie', 'Maxie', 'Ghetsis', 'N', 'Cheren', 'Bianca',
        'Guzma', 'Kukui', 'Hau', 'Mallow', 'Kiawe', 'Hala', 'Olivia', 'Nanu', 'Hapu',
        'Cyrus', 'Mars', 'Jupiter', 'Saturn', 'Charon',
        'Hop', 'Bede', 'Marnie', 'Rose', 'Oleana', 'Piers', 'Raihan', 'Leon',
        'Victor', 'Gloria', 'Mustard', 'Avery', 'Klara', 'Peony', 'Peonia',
        'Geeta', 'Sada', 'Turo', 'Arven', 'Nemona', 'Clavell', 'Larry', 'Rika',
        'Poppy', 'Hassel', 'Kieran', 'Briar', 'Carmine',
        'Leaf', 'Red', 'Blue', 'Green', 'Yellow', 'Gold', 'Silver', 'Crystal',
        'Professor', 'Youngster', 'Lass', 'Fisherman', 'Hiker', 'Bug Catcher',
        'Scientist', 'Beauty', 'Breeder', 'Roughneck', 'Team Flare',
        'Lisia', 'Zinnia', 'Wally', 'Courtney', 'Tabitha', 'Matt', 'Shelly',
        'Iris', 'Cilan', 'Chili', 'Cress', 'Brycen', 'Drayden', 'Skyla', 'Elesa',
        'Clay', 'Burgh', 'Lenora', 'Whitney', 'Jasmine', 'Clair', 'Morty', 'Chuck',
        'Pryce', 'Falkner', 'Bugsy', 'Janine', 'Flannery',
    ]
    male_set = {k.lower() for k in male_keywords}
    # Palavras tipicamente femininas
    female_words = ['Lass', 'Beauty', 'Misty', 'Sabrina', 'Erika', 'Winona', 'Flannery',
                    'Liza', 'Bianca', 'Gloria', 'Marnie', 'Oleana', 'Klara', 'Peonia',
                    'Geeta', 'Sada', 'Nemona', 'Rika', 'Poppy', 'Briar', 'Carmine',
                    'Green', 'Yellow', 'Crystal', 'Lisia', 'Zinnia', 'Courtney', 'Shelly',
                    'Skyla', 'Elesa', 'Lenora', 'Whitney', 'Clair', 'Janine', 'Phoebe',
                    'Glacia', 'Roxanne', 'Olivia', 'Nanu', 'Hapu', 'Lillie', 'Rosa', 'Hilda',
                    'Mallow', 'Lana', 'Mina', 'Acerola', 'Kahili', 'Diantha',
                    'Iris', 'Hilbert', 'Hilda', 'Rosa', 'Nate', 'Yancy', 'Curtis',
                    'May', 'Brendan', 'Dawn', 'Lucas', 'Serena', 'Calem', 'Selene', 'Elio',
                    'Juniper', 'Sonia', 'Hop', 'Bede', 'Milo', 'Nessa', 'Kabu', 'Opal']
    female_set = {k.lower() for k in female_words}
    
    name_lower = name.lower()
    
    # Verificar nomes femininos conhecidos
    for f in female_set:
        if f in name_lower:
            return 'female'
    
    # Verificar nomes masculinos conhecidos
    for m in male_set:
        if m in name_lower:
            return 'male'
    
    return 'neutral'


def fetch_all_cards(max_sets=50):
    """Coleta cartas de N sets via TCGdex (pt-BR)."""
    sets = fetch_all_sets()
    if not sets:
        return []

    # Filtra sets com cards (exclui promos avulsas)
    valid_sets = [s for s in sets if s.get('cardCount', {}).get('total', 0) > 0]
    print(f'  Sets com cartas: {len(valid_sets)}')

    all_cards = []
    for i, s in enumerate(valid_sets[:max_sets]):
        sid = s.get('id')
        set_name = s.get('name', sid)
        cards = fetch_set_cards(sid)
        all_cards.extend(cards)
        print(f'  Set {i+1}/{min(max_sets, len(valid_sets))}: {set_name} ({len(cards)} cartas, total: {len(all_cards)})')
        time.sleep(0.3)

    return all_cards


# ── 2. Parse (TCGdex → df) ─────────────────────────────────────────

def parse_card(c):
    """Extrai features de uma carta TCGdex."""
    set_info = c.get('_set', {})
    rel_date = set_info.get('set_release_date', '')
    rel_year = int(rel_date.split('-')[0]) if rel_date and '-' in rel_date else None

    types = c.get('types', [])
    dex_id = c.get('dexId', [])
    hp_str = c.get('hp')
    try:
        hp = float(hp_str) if hp_str else None
    except:
        hp = None

    return {
        'id': c.get('id', ''),
        'name': c.get('name', ''),           # pt-BR
        'name_en': c.get('name', ''),         # fallback
        'hp': hp,
        'supertype': c.get('category', 'Pokémon'),
        'subtypes_count': 1 if c.get('stage') not in (None, 'Basic') else 0,
        'primary_type': types[0] if types else 'Colorless',
        'rarity': c.get('rarity', 'Unknown'),
        'stage': c.get('stage', 'Basic'),
        'set_id': set_info.get('set_id', ''),
        'set_name': set_info.get('set_name', ''),
        'set_series': set_info.get('set_series', ''),
        'set_printed_total': set_info.get('set_printed_total', 0),
        'release_year': rel_year,
        'card_age_years': (datetime.now().year - rel_year) if rel_year else None,
        'pokedex_number': dex_id[0] if dex_id else None,
        'image': c.get('image'),
    }


# ── 3a. Merge BRL (Liga Pokémon) ────────────────────────────────────

LIGA_PATH = DATA_DIR / 'liga' / 'liga_all_cards.csv'

def build_liga_lookup():
    """Constrói lookups de BRL + iCO + tcg_set → liga_sigla."""
    import re
    
    # Carrega mapping TCGdex set_id → Liga sigla (via nome)
    liga_map_path = DATA_DIR / 'liga' / 'liga_set_sigla.json'
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
                    key = (sigla, num)
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
    """Busca pricing TCGPlayer USD via requisições paralelas."""
    cids = df['id'].str.replace('pt/', '', regex=False).tolist()
    total = len(cids)
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
    # Nome EN vindo do endpoint individual (mais confiável)
    en_names = df_prices['name_en'].fillna('')
    df['name_en'] = df['name_en'].combine_first(en_names)
    # TCGdex rarity pura (sem mapping)
    df['rarity'] = df['rarity_tcg']
    has_price = df['target_price'].notna().sum()
    print(f'  Cartas com preço: {has_price}/{total}')
    return df


# ── 4. Features ─────────────────────────────────────────────────────

CAT_FEATURES = ['rarity_tcg', 'primary_type', 'set_series', 'price_type', 'supertype', 'illustrator', 'trainer_gender']
EMBEDDINGS_FILE = DATA_DIR / 'pokemon_embeddings_16d.csv'

# Flags binárias de arte
ART_FEATURES = ['is_holo', 'is_reverse', 'is_normal', 'is_shiny', 'is_legendary']
# Grail score e popularidade
NUM_FEATURES = ['hp', 'subtypes_count', 'set_printed_total', 'release_year', 'card_age_years', 'pokedex_number', 'pokemon_popularity', 'iCO', 'pokemon_grail_score'] + ART_FEATURES + [f'emb_{i}' for i in range(16)]
NUM_FEATURES_BRL = NUM_FEATURES + ['target_price_usd']  # USD price como feature para modelo BRL
FEATURE_COLS = CAT_FEATURES + NUM_FEATURES

# ── 4a. Grail Score & Legendary ────────────────────────────────────

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
    if dex_id and int(dex_id) in LEGENDARY_DEX:
        return 4
    
    return 0

def is_legendary(dex_id):
    """Retorna 1 se o Pokémon é lendário/mítico."""
    if not dex_id:
        return 0
    return 1 if int(dex_id) in LEGENDARY_DEX else 0


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
        for i in range(16):
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

def train_model(max_sets=20):
    print('\n📦 Treinando modelo...')
    cards = fetch_all_cards(max_sets=max_sets)
    df = pd.DataFrame([parse_card(c) for c in cards])
    df = enrich_pricing(df)
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

def train_model_brl(max_sets=50):
    """Treina modelo com target BRL (preços brasileiros)."""
    print('\n📦 Treinando modelo BRL...')
    cards = fetch_all_cards(max_sets=max_sets)
    df = pd.DataFrame([parse_card(c) for c in cards])
    df = enrich_pricing(df)
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
    print(f'📊 Metadados: {df.shape}')

    df = enrich_pricing(df)
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
            X_brl = prepare_features(df_valid[brl_idx])
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
