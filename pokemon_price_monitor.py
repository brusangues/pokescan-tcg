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
from catboost import CatBoostRegressor
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, str(Path(__file__).parent))
import pokemon_popularity as pop

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
MONITOR_DIR = DATA_DIR / 'monitoring'
MODEL_PATH = DATA_DIR / 'catboost_model.cbm'
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
    """Busca pricing individual de uma carta (EN — tem TCGPlayer)."""
    clean_id = card_id.replace('pt/', '')
    data = fetch_json(f'{TCGDEX}/en/cards/{clean_id}')
    if not data:
        return {}
    pricing = data.get('pricing', {})
    tcg = pricing.get('tcgplayer', {}) if pricing else {}
    holofoil = tcg.get('holofoil', {}) if tcg else {}
    normal = tcg.get('normal', {}) if tcg else {}
    return {
        'target_price_usd': holofoil.get('marketPrice') or normal.get('marketPrice'),
        'price_type': 'holofoil' if holofoil.get('marketPrice') else ('normal' if normal.get('marketPrice') else None),
    }


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


# ── 3. Pricing (busca individual complementar) ─────────────────────

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
    has_price = df['target_price'].notna().sum()
    print(f'  Cartas com preço: {has_price}/{total}')
    return df


# ── 4. Features ─────────────────────────────────────────────────────

CAT_FEATURES = ['rarity', 'primary_type', 'set_series', 'price_type', 'supertype']
NUM_FEATURES = ['hp', 'subtypes_count', 'set_printed_total', 'release_year', 'card_age_years', 'pokedex_number', 'pokemon_popularity']
FEATURE_COLS = CAT_FEATURES + NUM_FEATURES


def prepare_features(df):
    # Adiciona popularidade se tiver nome
    X = df.copy()
    if 'name_en' in X.columns:
        X['pokemon_popularity'] = X['name_en'].apply(
            lambda n: pop.get_popularity(n) if pd.notna(n) else 10.0
        )
    elif 'pokemon_popularity' not in X.columns:
        X['pokemon_popularity'] = 10.0
    
    # Seleciona apenas as features
    avail = [c for c in FEATURE_COLS if c in X.columns]
    X = X[avail].copy()
    X['hp'] = X['hp'].fillna(X['hp'].median())
    X['set_printed_total'] = X['set_printed_total'].fillna(X['set_printed_total'].median())
    X['release_year'] = X['release_year'].fillna(2016)
    X['card_age_years'] = X['card_age_years'].fillna(10)
    X['pokedex_number'] = X['pokedex_number'].fillna(0)
    X = X.infer_objects(copy=False)
    return X


# ── 5. Modelo ───────────────────────────────────────────────────────

def train_model():
    print('\n📦 Treinando modelo...')
    cards = fetch_all_cards(max_sets=20)        # ~5000 cartas p/ treino
    df = pd.DataFrame([parse_card(c) for c in cards])
    df = enrich_pricing(df)
    df = df[df['target_price'].notna() & (df['target_price'] > 0)].copy()
    df['log_target'] = np.log1p(df['target_price'])

    X = prepare_features(df)
    y = df['log_target']
    cat_idx = [i for i, c in enumerate(FEATURE_COLS) if c in CAT_FEATURES]

    df_sorted = df.sort_values('release_year', na_position='first')
    split = int(len(df_sorted) * 0.8)
    X_train = prepare_features(df_sorted.iloc[:split])
    y_train = df_sorted['log_target'].iloc[:split]

    model = CatBoostRegressor(
        iterations=500, learning_rate=0.05, depth=6,
        l2_leaf_reg=3, loss_function='MAE', eval_metric='MAE',
        cat_features=cat_idx, verbose=0, random_seed=42,
        early_stopping_rounds=30,
    )
    model.fit(X_train, y_train)
    model.save_model(str(MODEL_PATH))
    print(f'✅ Modelo salvo em {MODEL_PATH}')
    return model


def load_model():
    if MODEL_PATH.exists():
        model = CatBoostRegressor()
        model.load_model(str(MODEL_PATH))
        print(f'📦 Modelo carregado de {MODEL_PATH}')
        return model
    return train_model()


# ── 6. Snapshot ─────────────────────────────────────────────────────

def run_snapshot(model=None):
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
    print(f'💰 Com preço: {len(df_valid)}')

    if model is None:
        model = load_model()

    X = prepare_features(df_valid)
    log_pred = model.predict(X)
    df_valid['predicted_price'] = np.expm1(log_pred)
    df_valid['residual'] = df_valid['target_price'] - df_valid['predicted_price']
    df_valid['residual_pct'] = (df_valid['residual'] / df_valid['target_price'] * 100).clip(-500, 500)
    df_valid['snapshot_date'] = datetime.now().strftime('%Y-%m-%d %H:%M')

    resid_std = df_valid['residual'].std()
    df_valid['is_outlier'] = df_valid['residual'].abs() > 2 * resid_std

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = MONITOR_DIR / f'snapshot_{ts}.csv'
    df_valid.to_csv(path, index=False)
    print(f'💾 Salvo: {path} ({len(df_valid)} cartas)')

    print(f'\n📈 RESUMO')
    print(f'  Preço real médio:    ${df_valid["target_price"].mean():.2f}')
    print(f'  Preço predito médio: ${df_valid["predicted_price"].mean():.2f}')
    print(f'  MAE:                 ${df_valid["residual"].abs().mean():.2f}')
    print(f'  Outliers detectados: {df_valid["is_outlier"].sum()}')

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
        import requests
        import time
        model = load_model()
        run_snapshot(model)
