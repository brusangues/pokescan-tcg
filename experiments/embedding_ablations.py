"""
experiments/embedding_ablations.py
===================================
Ablações de embeddings de imagem para o modelo de preço USD.

Testa:
- Modelos: dinov2-small (384d), dinov2-base (768d), dinov2-large (1024d)
- Agregações: CLS token, mean-pool, CLS+mean concat
- PCA: 16, 32, 64 componentes

Para cada combinação: treina CatBoost USD com split temporal honesto
(cutoff 2024-01-01) e reporta MAE / R² / Acc.

Uso:
  python experiments/embedding_ablations.py                # roda tudo
  python experiments/embedding_ablations.py --only-base    # só base (rápido)
  python experiments/embedding_ablations.py --models small,base
  python experiments/embedding_ablations.py --skip-extract # usa .npy já extraídos
"""

import sys, argparse, time, re, json
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from PIL import Image
from sklearn.decomposition import PCA
from catboost import CatBoostRegressor
from sklearn.metrics import mean_absolute_error, r2_score

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
CACHE_DIR = DATA_DIR / 'img_cache'
OUT_DIR = BASE_DIR / 'data' / 'exp_embeddings'
OUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BASE_DIR))
import pokemon_price_monitor as pm

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# Modelos DINOv2: (id HF, dim, params)
MODELS = {
    'small': ('facebook/dinov2-small', 384, '22M'),
    'base': ('facebook/dinov2-base', 768, '86M'),
    'large': ('facebook/dinov2-large', 1024, '300M'),
}

# Agregações disponíveis
AGGS = ['cls', 'mean', 'cls+mean']

CUTOFF = '2024-01-01'  # split temporal honesto


def load_image_set():
    """Carrega pares (id, imagem) do cache."""
    cards = []
    for p in sorted(CACHE_DIR.glob('*.png')):
        cards.append((p.stem, str(p)))
    return cards


def extract_all(model_key, batch_size=64):
    """Extrai embeddings de todas as imagens com o modelo, gerando as 3
    agregações (cls, mean, cls+mean) numa única passada."""
    hf_id, dim, _ = MODELS[model_key]
    from transformers import AutoImageProcessor, AutoModel
    print(f'  Carregando {hf_id} ({MODELS[model_key][2]}, {dim}d)...')
    processor = AutoImageProcessor.from_pretrained(hf_id)
    model = AutoModel.from_pretrained(hf_id).to(device).eval()

    pairs = load_image_set()
    out = {agg: [] for agg in AGGS}
    all_ids = []

    with torch.no_grad():
        for i in range(0, len(pairs), batch_size):
            batch = pairs[i:i+batch_size]
            imgs, ids = [], []
            for cid, path in batch:
                try:
                    imgs.append(Image.open(path).convert('RGB'))
                    ids.append(cid)
                except Exception:
                    continue
            if not imgs:
                continue
            inputs = processor(images=imgs, return_tensors='pt').to(device)
            hs = model(**inputs).last_hidden_state  # [B, 1+196, D]

            cls_e = hs[:, 0, :]
            mean_e = hs[:, 1:, :].mean(dim=1)
            out['cls'].append(cls_e.cpu().numpy())
            out['mean'].append(mean_e.cpu().numpy())
            out['cls+mean'].append(torch.cat([cls_e, mean_e], dim=1).cpu().numpy())
            all_ids.extend(ids)
            torch.cuda.empty_cache()

    result = {}
    for agg in AGGS:
        if not out[agg]:
            result[agg] = np.zeros((0, dim * (2 if agg == 'cls+mean' else 1)))
        else:
            result[agg] = np.vstack(out[agg])
    return result, all_ids


def fit_pca(embs, n_components):
    pca = PCA(n_components=n_components, whiten=True)
    reduced = pca.fit_transform(embs)
    return reduced, pca


def run_model_ablation(df, emb_csv_path, label, top_metrics=True):
    """Treina CatBoost USD com embeddings e retorna métricas."""
    # Prepara df com embeddings
    emb_df = pd.read_csv(emb_csv_path)
    emb_df.columns = emb_df.columns.str.strip()
    emb_df['id'] = emb_df['id'].astype(str)

    # NÃO injeta o CSV — seta cache vazio para o prepare_features não fazer
    # merge interno (evita _x/_y). O df_m já tem as colunas emb mergeadas.
    pm.prepare_features._emb_cache = pd.DataFrame()

    # Merge manual + remove colunas emb do df base para evitar _x/_y
    df_m = df.copy()
    emb_cols = [c for c in emb_df.columns if c.startswith('emb_')]
    for c in emb_cols:
        if c in df_m.columns:
            df_m = df_m.drop(columns=[c])
    df_m = df_m.merge(emb_df, on='id', how='left')
    n_emb = len(emb_cols)
    print(f'  Merge: {len(df_m)} linhas, {df_m["emb_0"].notna().sum()} com emb, {n_emb} componentes')

    # Garante colunas emb_0..emb_{n_emb-1} (preenche 0 onde faltar)
    for i in range(n_emb):
        col = f'emb_{i}'
        if col in df_m.columns:
            df_m[col] = df_m[col].fillna(0.0)
        else:
            df_m[col] = 0.0

    # Amplia NUM_FEATURES com os componentes extras (16 fixos no pm)
    # Reset antes para não acumular de iterações anteriores
    pm.NUM_FEATURES = [c for c in pm.NUM_FEATURES if not c.startswith('emb_')]
    pm.NUM_FEATURES += [f'emb_{i}' for i in range(16)]
    if n_emb > 16:
        pm.NUM_FEATURES += [f'emb_{i}' for i in range(16, n_emb)]
    pm.FEATURE_COLS = pm.CAT_FEATURES + pm.NUM_FEATURES

    # Split temporal (parse_card gera release_year)
    train = df_m[df_m['release_year'] < 2024]
    test = df_m[df_m['release_year'] >= 2024]

    train = train[train['target_price'].notna() & (train['target_price'] > 0)]
    test = test[test['target_price'].notna() & (test['target_price'] > 0)]

    X_train = pm.prepare_features(train)
    X_test = pm.prepare_features(test)
    y_train = np.log1p(train['target_price'].values)
    y_test = np.log1p(test['target_price'].values)

    # Índices das features categóricas (mesmo padrão do train_model)
    cat_idx = [i for i, c in enumerate(X_train.columns) if c in pm.CAT_FEATURES]

    model = CatBoostRegressor(
        iterations=300, depth=8, learning_rate=0.05,
        loss_function='RMSE', random_seed=42, verbose=0,
    )
    model.fit(X_train, y_train, cat_features=cat_idx)

    pred = np.expm1(model.predict(X_test))
    real = np.expm1(y_test)
    mae = mean_absolute_error(real, pred)
    r2 = r2_score(real, pred)

    print(f'  → {label}: MAE=${mae:.2f} | R²={r2:.4f} | n_train={len(train)} n_test={len(test)}')
    return {'label': label, 'mae': mae, 'r2': r2, 'n_train': len(train), 'n_test': len(test)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--models', default='small,base,large', help='modelos separados por vírgula')
    parser.add_argument('--aggs', default='cls,mean,cls+mean', help='agregações separadas por vírgula')
    parser.add_argument('--pca', default='16,32,64', help='componentes PCA separados por vírgula')
    parser.add_argument('--skip-extract', action='store_true', help='usa .npy já existentes')
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(',')]
    aggs = [a.strip() for a in args.aggs.split(',')]
    pca_list = [int(p) for p in args.pca.split(',')]

    # Carrega df base
    print('📦 Carregando dados de cartas...')
    cards = json.loads((DATA_DIR / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
    df = pd.DataFrame([pm.parse_card(c) for c in cards])
    df['_raw'] = cards  # payload bruto com pricing embutido (pokemontcg.io)
    df = pm.enrich_pricing(df)
    df = pm.add_supply_features(df)
    df['id'] = df['id'].astype(str)
    print(f'  Base: {len(df)} cartas, {df["target_price"].notna().sum()} com preço')

    results = []
    for model_key in models:
        # Extrai uma única vez por modelo — gera as 3 agregações
        npy_prefix = OUT_DIR / f'embs_{model_key}'
        if not args.skip_extract or not (OUT_DIR / f'embs_{model_key}_cls.npy').exists():
            print(f'\n🔬 Extraindo {model_key} (3 agregações em 1 passada)...')
            t0 = time.time()
            embs_dict, ids = extract_all(model_key)
            for agg, embs in embs_dict.items():
                np.save(OUT_DIR / f'embs_{model_key}_{agg}.npy', embs)
                print(f'  {agg}: {embs.shape} em {time.time()-t0:.0f}s')
            (OUT_DIR / f'embs_{model_key}_ids.json').write_text(json.dumps(ids))
        else:
            ids = json.loads((OUT_DIR / f'embs_{model_key}_ids.json').read_text())
            embs_dict = {
                agg: np.load(OUT_DIR / f'embs_{model_key}_{agg}.npy')
                for agg in aggs
            }
            print(f'\n🔬 {model_key}: carregado cache')

        for agg in aggs:
            embs = embs_dict[agg]
            for n_comp in pca_list:
                label = f'{model_key}/{agg}/pca{n_comp}'
                csv_path = OUT_DIR / f'{model_key}_{agg}_pca{n_comp}.csv'
                if not csv_path.exists():
                    reduced, _ = fit_pca(embs, n_comp)
                    df_emb = pd.DataFrame(reduced, columns=[f'emb_{i}' for i in range(n_comp)])
                    df_emb.insert(0, 'id', ids)
                    df_emb.to_csv(csv_path, index=False)
                res = run_model_ablation(df, csv_path, label)
                results.append(res)

    # Tabela final
    print('\n' + '='*70)
    print('📊 ABLAÇÕES — Embeddings (modelo USD, split temporal)')
    print('='*70)
    df_res = pd.DataFrame(results).sort_values('mae')
    print(df_res.to_string(index=False))
    df_res.to_csv(OUT_DIR / 'ablation_results.csv', index=False)
    print(f'\n💾 Salvo: {OUT_DIR / "ablation_results.csv"}')


if __name__ == '__main__':
    main()
