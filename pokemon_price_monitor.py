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


# ── 3a. Merge BRL (Liga Pokémon) ────────────────────────────────────

LIGA_PATH = DATA_DIR / 'liga' / 'liga_all_cards.csv'

def build_liga_lookup():
    """Constrói lookups de BRL + iCO."""
    import re
    
    # Carrega mapping TCGdex set_id → Liga sigla
    mapping_path = BASE_DIR / 'set_mapping.json'
    if mapping_path.exists():
        set_mapping = json.loads(mapping_path.read_text())
    else:
        set_mapping = {}
    
    # Lookup Liga: (sigla, num) → preços
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
                    key = (sigla, num)
                    if key not in lookup_brl or p_med < lookup_brl[key].get('preco_medio_brl', float('inf')):
                        lookup_brl[key] = {
                            'preco_min_brl': float(c.get('p1a', 0) or 0),
                            'preco_medio_brl': p_med,
                            'preco_max_brl': float(c.get('p1c', 0) or 0),
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
        if len(parts) == 2:
            tcg_set = parts[0]
            try: local_id = int(parts[1])
            except: local_id = None
            
            liga_sigla = set_mapping.get(tcg_set)
            if liga_sigla and local_id is not None:
                key = (liga_sigla, local_id)
                if key in lookup_brl:
                    brl = lookup_brl[key]
                    ico_data = lookup_ico.get(key, (0, 0))
                    matched += 1
                    results['target_price_brl'].append(brl.get('preco_medio_brl'))
                    results['preco_min_brl'].append(brl.get('preco_min_brl'))
                    results['preco_max_brl'].append(brl.get('preco_max_brl'))
                    results['iCO'].append(ico_data[0])
                    continue
        
        results['target_price_brl'].append(None)
        results['preco_min_brl'].append(None)
        results['preco_max_brl'].append(None)
        results['iCO'].append(0)
    
    df_out = df_tcgdex.copy()
    for col, vals in results.items():
        df_out[col] = vals
    
    print(f'💰 BRL (merge por set+número): {matched}/{len(df_out)} cartas')
    return df_out


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
    has_price = df['target_price'].notna().sum()
    print(f'  Cartas com preço: {has_price}/{total}')
    return df


# ── 4. Features ─────────────────────────────────────────────────────

CAT_FEATURES = ['rarity', 'primary_type', 'set_series', 'price_type', 'supertype']
EMBEDDINGS_FILE = DATA_DIR / 'pokemon_embeddings_16d.csv'

NUM_FEATURES = ['hp', 'subtypes_count', 'set_printed_total', 'release_year', 'card_age_years', 'pokedex_number', 'pokemon_popularity', 'iCO'] + [f'emb_{i}' for i in range(16)]
FEATURE_COLS = CAT_FEATURES + NUM_FEATURES


def prepare_features(df):
    """Prepara features (numéricas + categóricas) para o modelo."""
    # Carrega embeddings
    emb_cache = getattr(prepare_features, '_emb_cache', None)
    if emb_cache is None:
        if EMBEDDINGS_FILE.exists():
            emb_cache = pd.read_csv(EMBEDDINGS_FILE)
            emb_cache.columns = emb_cache.columns.str.strip()
            prepare_features._emb_cache = emb_cache
        else:
            prepare_features._emb_cache = pd.DataFrame()
    
    X = df[[c for c in ['id'] + CAT_FEATURES + NUM_FEATURES if c in df.columns]].copy() if df is not None else pd.DataFrame()
    
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
    avail = [c for c in FEATURE_COLS if c in X.columns]
    X = X[avail].copy()
    X['hp'] = X['hp'].fillna(X['hp'].median())
    X['set_printed_total'] = X['set_printed_total'].fillna(X['set_printed_total'].median())
    X['release_year'] = X['release_year'].fillna(2016)
    X['card_age_years'] = X['card_age_years'].fillna(10)
    X['pokedex_number'] = X['pokedex_number'].fillna(0)
    X['iCO'] = X.get('iCO', 0).fillna(0)
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
    return model


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
    
    cat_idx = [i for i, c in enumerate(FEATURE_COLS) if c in CAT_FEATURES]
    
    # Split temporal: 80% antigas treino, 20% recentes teste
    df_sorted = df.sort_values('release_year', na_position='first')
    split = int(len(df_sorted) * 0.8)
    train_df = df_sorted.iloc[:split]
    test_df = df_sorted.iloc[split:]
    
    X_train = prepare_features(train_df)
    y_train = train_df['log_target_brl']
    X_test = prepare_features(test_df)
    y_test = test_df['log_target_brl']
    
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
