"""
script/ensure_embeddings.py
===========================
Garante que todas as cartas da base tenham imagem + embedding no cache,
de forma INCREMENTAL (só processa o que falta, somando ao existente).

Fluxo:
1. Lê a base (data/ptcg_cards_cache.json) e o CSV de embeddings atual
   (data/pokemon_embeddings_base32.csv).
2. Identifica cartas sem imagem (data/img_cache/) e baixa do pokemontcg.io.
3. Identifica cartas sem embedding e extrai com DINOv2-base (cls+mean → PCA32),
   reutilizando o PCA já ajustado (data/pca_base32.pkl).
4. Faz append ao CSV de embeddings existente.

Seguro para crons: idempotente, incremental, usa cache local existente.

Uso:
  python script/ensure_embeddings.py             # roda tudo (download + extração)
  python script/ensure_embeddings.py --no-download
  python script/ensure_embeddings.py --no-extract
"""

import sys, json, argparse
from pathlib import Path
import numpy as np
import pandas as pd
import requests
from PIL import Image
from io import BytesIO

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
CACHE_DIR = DATA_DIR / 'img_cache'
EMBED_CSV = DATA_DIR / 'pokemon_embeddings_base32.csv'
PCA_PATH = DATA_DIR / 'pca_base32.pkl'

IMG_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
MODEL_ID = 'facebook/dinov2-base'
N_COMP = 32

# ── 1. Baixa imagens faltantes ─────────────────────────────────────

def download_one(card):
    cid = card['id']
    path = CACHE_DIR / f'{cid}.png'
    if path.exists():
        return cid, 'cache'
    url = card.get('images', {}).get('small')
    if not url:
        return cid, 'no-url'
    try:
        resp = requests.get(url, headers=IMG_HEADERS, timeout=15)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert('RGB')
        img_resized = img.resize((256, 256), Image.LANCZOS)
        img_resized.save(path, 'PNG')
        return cid, 'ok'
    except Exception:
        return cid, 'fail'


def ensure_images(cards):
    """Baixa imagens faltantes, incremental."""
    faltam = [c for c in cards if not (CACHE_DIR / f'{c["id"]}.png').exists()]
    if not faltam:
        print('  ✅ Todas as imagens já em cache')
        return 0

    print(f'  📥 Baixando {len(faltam)} imagens faltantes...')
    stats = {'ok': 0, 'fail': 0, 'no-url': 0}
    for c in faltam:
        _, status = download_one(c)
        stats[status] += 1
        if stats['ok'] % 100 == 0 and stats['ok'] > 0:
            print(f'    ...{stats["ok"]} baixadas')
    print(f'  ✅ Download: {stats["ok"]} ok, {stats["fail"]} falha, {stats["no-url"]} sem URL')
    return stats['ok']


# ── 2. Extrai embeddings faltantes (incremental) ───────────────────

def ensure_embeddings(cards):
    """Extrai embeddings só das cartas sem embedding no CSV atual."""
    import joblib

    # CSV atual
    emb_df = pd.read_csv(EMBED_CSV) if EMBED_CSV.exists() else pd.DataFrame(columns=['id'])
    emb_df['id'] = emb_df['id'].astype(str)
    ids_com_emb = set(emb_df['id'])

    faltam = [c for c in cards
              if c['id'] not in ids_com_emb and (CACHE_DIR / f'{c["id"]}.png').exists()]
    if not faltam:
        print(f'  ✅ Todos com embedding ({len(ids_com_emb)})')
        return 0

    print(f'  🧠 Extraindo embeddings de {len(faltam)} cartas faltantes...')

    import torch
    from transformers import AutoImageProcessor, AutoModel
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    processor = AutoImageProcessor.from_pretrained(MODEL_ID)
    model = AutoModel.from_pretrained(MODEL_ID).to(device).eval()

    # PCA (carrega existente ou ajusta com o raw completo p/ consistência)
    if PCA_PATH.exists():
        pca = joblib.load(PCA_PATH)
    else:
        pca = None

    new_embs = []
    new_ids = []
    with torch.no_grad():
        for i in range(0, len(faltam), 64):
            batch = faltam[i:i+64]
            imgs, ids = [], []
            for c in batch:
                try:
                    imgs.append(Image.open(CACHE_DIR / f'{c["id"]}.png').convert('RGB'))
                    ids.append(c['id'])
                except Exception:
                    continue
            if not imgs:
                continue
            inputs = processor(images=imgs, return_tensors='pt').to(device)
            hs = model(**inputs).last_hidden_state
            cls_e = hs[:, 0, :]
            mean_e = hs[:, 1:, :].mean(dim=1)
            emb = torch.cat([cls_e, mean_e], dim=1).cpu().numpy()
            new_embs.append(emb)
            new_ids.extend(ids)
            torch.cuda.empty_cache()

    if not new_embs:
        print('  ⚠️ Nenhum embedding extraído')
        return 0

    new_embs = np.vstack(new_embs)

    # PCA: ajusta com raw completo existente + novos (consistente com produção)
    if pca is None:
        from sklearn.decomposition import PCA
        all_embs_file = DATA_DIR / 'exp_embeddings' / 'embs_base_cls+mean.npy'
        if all_embs_file.exists():
            old_raw = np.load(all_embs_file)
            print(f'  Ajustando PCA32 com {old_raw.shape[0]} raws existentes + {new_embs.shape[0]} novos...')
            pca = PCA(n_components=N_COMP, whiten=True)
            pca.fit(np.vstack([old_raw, new_embs]))
        else:
            print('  ⚠️ Raw base não encontrado — fitando só com novos (inconsistente!)')
            pca = PCA(n_components=N_COMP, whiten=True)
            pca.fit(new_embs)
        joblib.dump(pca, PCA_PATH)

    reduced = pca.transform(new_embs)
    df_new = pd.DataFrame(reduced, columns=[f'emb_{i}' for i in range(N_COMP)])
    df_new.insert(0, 'id', new_ids)

    # Append ao CSV existente
    df_all = pd.concat([emb_df, df_new], ignore_index=True)
    df_all.to_csv(EMBED_CSV, index=False)
    print(f'  ✅ Embeddings: +{len(df_new)} novas → {len(df_all)} total')
    return len(df_new)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-download', action='store_true')
    parser.add_argument('--no-extract', action='store_true')
    args = parser.parse_args()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    cards = json.loads((DATA_DIR / 'ptcg_cards_cache.json').read_text(encoding='utf-8'))
    print(f'📦 Base: {len(cards)} cartas')

    if not args.no_download:
        ensure_images(cards)
    if not args.no_extract:
        ensure_embeddings(cards)

    # Resumo final
    emb_df = pd.read_csv(EMBED_CSV) if EMBED_CSV.exists() else pd.DataFrame(columns=['id'])
    n_imgs = len(list(CACHE_DIR.glob('*.png')))
    print(f'\n✅ Cache final: {n_imgs} imagens | {len(emb_df)} embeddings')


if __name__ == '__main__':
    main()
