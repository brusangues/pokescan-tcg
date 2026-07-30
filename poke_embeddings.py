"""
poke_embeddings.py
==================
Baixa imagens das cartas Pokémon e extrai embeddings via DINOv2-small (384d → 16d PCA).
Usa images.pokemontcg.io como fonte e cache local.
"""

import sys
from pathlib import Path
import re
import numpy as np
import pandas as pd
import requests
from PIL import Image
from io import BytesIO
from sklearn.decomposition import PCA
import torch
from tqdm import tqdm

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'data'
CACHE_DIR = DATA_DIR / 'img_cache'
EMBED_PATH = DATA_DIR / 'pokemon_embeddings.pt'
PCA_PATH = DATA_DIR / 'pca_16d.pkl'

CACHE_DIR.mkdir(parents=True, exist_ok=True)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
IMG_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# Mapeamento TCGdex set_id → pokemontcg.io image prefix
SET_TO_IMG = {
    # Scarlet & Violet
    'sv01': 'sv1', 'sv02': 'sv2', 'sv03': 'sv3', 'sv03.5': 'sv3',
    'sv04': 'sv4', 'sv04.5': 'sv4', 'sv05': 'sv5',
    'sv06': 'sv6', 'sv06.5': 'sv6', 'sv07': 'sv7',
    'sv08': 'sv8', 'sv08.5': 'sv8', 'sv09': 'sv9',
    'sv10': 'sv10', 'sv10.5w': 'sv10', 'sv10.5b': 'sv10',
    'svp': 'svp', 'sve': 'sve',
    # Sword & Shield
    'swsh1': 'swsh1', 'swsh2': 'swsh2', 'swsh3': 'swsh3',
    'swsh3.5': 'swsh3', 'swsh4': 'swsh4', 'swsh4.5': 'swsh4',
    'swsh4.5sv': 'swsh4', 'swsh5': 'swsh5', 'swsh6': 'swsh6',
    'swsh7': 'swsh7', 'swsh8': 'swsh8', 'swsh9': 'swsh9',
    'swsh9.5tg': 'swsh9', 'swsh10': 'swsh10', 'swsh10.5': 'swsh10',
    'swsh10.5tg': 'swsh10', 'swsh11': 'swsh11', 'swsh11.5tg': 'swsh11',
    'swsh12': 'swsh12', 'swsh12.5': 'swsh12', 'swsh12.5tg': 'swsh12',
    'swsh12.5gg': 'swsh12',
    # Sun & Moon
    'sm1': 'sm1', 'sm2': 'sm2', 'sm3': 'sm3', 'sm3.5': 'sm3',
    'sm4': 'sm4', 'sm5': 'sm5', 'sm6': 'sm6', 'sm7': 'sm7',
    'sm7.5': 'sm7', 'sm8': 'sm8', 'sm9': 'sm9',
    'sm10': 'sm10', 'sm11': 'sm11', 'sm12': 'sm12', 'sm115': 'sm115',
    # XY
    'xy1': 'xy1', 'xy2': 'xy2', 'xy3': 'xy3', 'xy4': 'xy4',
    'xy5': 'xy5', 'xy6': 'xy6', 'xy7': 'xy7', 'xy8': 'xy8',
    'xy9': 'xy9', 'xy10': 'xy10', 'xy11': 'xy11', 'xy12': 'xy12',
    'xy0': 'xy0',
    # Black & White
    'bw1': 'bw1', 'bw2': 'bw2', 'bw3': 'bw3', 'bw4': 'bw4',
    'bw5': 'bw5', 'bw6': 'bw6', 'bw7': 'bw7', 'bw8': 'bw8',
    'bw9': 'bw9', 'bw10': 'bw10', 'bw11': 'bw11',
}  # fmt: skip

def get_model():
    from transformers import AutoImageProcessor, AutoModel
    processor = AutoImageProcessor.from_pretrained('facebook/dinov2-small')
    model = AutoModel.from_pretrained('facebook/dinov2-small').to(device).eval()
    return processor, model

def download_image(card_id, image_url):
    """Baixa imagem do cache local ou da internet."""
    path = CACHE_DIR / f'{card_id}.png'
    if path.exists():
        return Image.open(path).convert('RGB')

    try:
        resp = requests.get(image_url, headers=IMG_HEADERS, timeout=15)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert('RGB')
        # Salva versão menor (256px) pra economizar espaço
        img_resized = img.resize((256, 256), Image.LANCZOS)
        img_resized.save(path, 'PNG')
        return img_resized
    except:
        return None

def build_image_url(tcgdex_id):
    """Constrói URL de imagem da pokemontcg.io a partir do ID TCGdex."""
    parts = str(tcgdex_id).split('-')
    if len(parts) != 2:
        return None
    set_id, local_id = parts[0], parts[1]
    img_prefix = SET_TO_IMG.get(set_id) or set_id
    card_num = re.sub(r'[^0-9]', '', local_id)
    if not card_num:
        return None
    return f'https://images.pokemontcg.io/{img_prefix}/{int(card_num)}.png'

def download_all_images(df, batch_size=50):
    """Baixa todas as imagens em lote."""
    cards = df[df['id'].notna() & df['image_url'].notna()].to_dict('records')
    
    já_tem = len(list(CACHE_DIR.glob('*.png')))
    if já_tem >= len(cards):
        print(f'Todas as {já_tem} imagens já em cache')
        return

    print(f'Baixando imagens para {len(cards)} cartas...')
    for i in tqdm(range(0, len(cards), batch_size)):
        batch = cards[i:i+batch_size]
        for c in batch:
            download_image(c['id'], c['image_url'])

def extract_embeddings(df, batch_size=32, force=False):
    """Extrai embeddings das imagens em cache."""
    já_existe = EMBED_PATH.exists() and not force
    if já_existe:
        embs = np.load(EMBED_PATH) if EMBED_PATH.suffix == '.npy' else torch.load(EMBED_PATH, weights_only=True)
        if torch.is_tensor(embs):
            embs = embs.numpy()
        print(f'Embeddings carregados do cache: {embs.shape}')
        return embs

    processor, model = get_model()
    all_embs = []

    cards = df[df['id'].notna()].to_dict('records')
    print(f'Extraindo embeddings de {len(cards)} cartas...')

    for i in tqdm(range(0, len(cards), batch_size)):
        batch = cards[i:i+batch_size]
        images = []
        for c in batch:
            path = CACHE_DIR / f'{c["id"]}.png'
            if path.exists():
                images.append(Image.open(path).convert('RGB'))

        if not images:
            continue

        inputs = processor(images=images, return_tensors='pt').to(device)
        with torch.no_grad():
            outputs = model(**inputs)
            emb = outputs.last_hidden_state[:, 0, :].cpu().numpy()
            all_embs.append(emb)
        torch.cuda.empty_cache()

    if not all_embs:
        print('Nenhuma imagem em cache!')
        return np.zeros((0, 384))

    embs = np.vstack(all_embs)
    print(f'Extraídos: {embs.shape}')
    np.save(EMBED_PATH.with_suffix('.npy'), embs)
    return embs


def fit_pca(embeddings, n_components=16):
    print(f'Aplicando PCA {embeddings.shape[1]}d → {n_components}d...')
    from sklearn.decomposition import PCA
    pca = PCA(n_components=n_components, whiten=True)
    reduced = pca.fit_transform(embeddings)
    import joblib
    joblib.dump(pca, PCA_PATH)
    print(f'Variância explicada: {pca.explained_variance_ratio_.sum():.1%}')
    return reduced


if __name__ == '__main__':
    force = '--force' in sys.argv
    skip_download = '--skip-download' in sys.argv

    from pokemon_price_monitor import fetch_all_cards
    cards = fetch_all_cards(max_sets=50)
    
    # Constrói df com URLs
    df = pd.DataFrame([{
        'id': c.get('id'),
        'image_url': build_image_url(c.get('id')),
    } for c in cards])

    url_col = 'image_url'
    print(f'Cartas: {len(df)}, com URL: {df[url_col].notna().sum()}')

    if not skip_download:
        download_all_images(df)

    embs = extract_embeddings(df, force=force)
    if len(embs) > 0:
        reduced = fit_pca(embs)
        df_emb = pd.DataFrame(reduced, columns=[f'emb_{i}' for i in range(reduced.shape[1])])
        # Match com IDs
        ids_ok = [c['id'] for c in cards[:len(embs)]]
        df_emb.insert(0, 'id', ids_ok)
        df_emb.to_csv(DATA_DIR / 'pokemon_embeddings_16d.csv', index=False)
        print(f'Salvo: data/pokemon_embeddings_16d.csv ({len(df_emb)} cartas)')
