"""
script/gen_embeddings_prod.py
=============================
Gera o PCA32 definitivo (dinov2-base cls+mean) e o CSV de embeddings de
produção CONSISTENTE (todas as cartas transformadas com o MESMO PCA).

Roda UMA vez após integrar o vencedor das ablações. Depois disso, o
script/ensure_embeddings.py mantém o cache incrementalmente (reutilizando
pca_base32.pkl).

Uso:
  python script/gen_embeddings_prod.py
"""

import sys, json
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from sklearn.decomposition import PCA

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
RAW_FILE = DATA_DIR / 'exp_embeddings' / 'embs_base_cls+mean.npy'
IDS_FILE = DATA_DIR / 'exp_embeddings' / 'embs_base_ids.json'
PCA_PATH = DATA_DIR / 'pca_base32.pkl'
EMBED_CSV = DATA_DIR / 'pokemon_embeddings_base32.csv'
N_COMP = 32

print('📦 Gerando PCA32 definitivo + CSV de produção consistente...')

raw = np.load(RAW_FILE)
ids = json.loads(IDS_FILE.read_text())
print(f'  Raw: {raw.shape} | IDs: {len(ids)}')

pca = PCA(n_components=N_COMP, whiten=True)
reduced = pca.fit_transform(raw)
joblib.dump(pca, PCA_PATH)
print(f'  PCA salvo: {PCA_PATH} (variância: {pca.explained_variance_ratio_.sum():.1%})')

df = pd.DataFrame(reduced, columns=[f'emb_{i}' for i in range(N_COMP)])
df.insert(0, 'id', ids)
df['id'] = df['id'].astype(str)
df.to_csv(EMBED_CSV, index=False)
print(f'  CSV salvo: {EMBED_CSV} ({len(df)} linhas)')

# Sanity: quanto da base real tem embedding
cards = json.loads((DATA_DIR / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
base_ids = set(c['id'] for c in cards)
emb_ids = set(df['id'])
print(f'  Cobertura base: {len(base_ids & emb_ids)}/{len(base_ids)} = {len(base_ids & emb_ids)/len(base_ids)*100:.1f}%')
