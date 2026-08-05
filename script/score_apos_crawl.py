"""
script/score_apos_crawl.py
==========================
Escora hits diários ou snapshot semanal recém-raspados da Liga Pokémon.
Usa o cache local de features pokemontcg.io (data/ptcg_cards_cache.json),
SEM bater na API. Mostra no final as cartas com maior oportunidade
(cartas baratas com predição alta do modelo).

Uso:
  python script/score_apos_crawl.py --tipo hits      # escora hits do dia
  python script/score_apos_crawl.py --tipo snapshot  # escora snapshot mais recente

Melhorias:
  - Fallback JP: mapeia siglas japonesas para set EN equivalente
  - iCO_real: usa iCO enriquecido da página da carta quando disponível
"""

import sys, json, re, glob, argparse
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
import pokemon_price_monitor as pm
import ptcg_io

CACHE_PATH = BASE / 'data' / 'ptcg_cards_cache.json'
LIGA_DIR = BASE / 'data' / 'liga'
SNAP_DIR = LIGA_DIR / 'snapshots'
SCORE_DIR = BASE / 'data' / 'scored'
SCORE_DIR.mkdir(parents=True, exist_ok=True)

# Mapeamento de siglas JP → set EN (carregado lazy)
_JP_MAPPING = None

def _load_jp_mapping():
    global _JP_MAPPING
    if _JP_MAPPING is None:
        jp_file = LIGA_DIR / 'jp_mapping.py'
        if jp_file.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location('jp_mapping', jp_file)
            jp_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(jp_mod)
            _JP_MAPPING = jp_mod.JP_TO_EN_SET
        else:
            _JP_MAPPING = {}
    return _JP_MAPPING


def load_base_features():
    """Carrega features do cache local (sem API)."""
    if not CACHE_PATH.exists():
        print(f'⚠️  Cache não encontrado ({CACHE_PATH}). Baixando via paginação global...')
        cards = ptcg_io.fetch_all_cards_global()
        CACHE_PATH.write_text(json.dumps(cards, ensure_ascii=False), encoding='utf-8')
    else:
        cards = json.loads(CACHE_PATH.read_text(encoding='utf-8'))

    df_base = pd.DataFrame([pm.parse_card(c) for c in cards])
    df_base['_raw'] = cards
    df_base = pm.enrich_pricing(df_base)
    df_base = pm.add_supply_features(df_base)  # E1: rarity_pool_size + pull_cost
    df_base['id'] = df_base['id'].astype(str)
    return df_base


def build_liga_id_from_base(df_base):
    """Cria liga_id (SIGLA-NUMERO) para cada carta da base pokemontcg."""
    set_map_path = LIGA_DIR / 'liga_set_sigla_ptcg.json'
    if not set_map_path.exists():
        set_map_path = LIGA_DIR / 'liga_set_sigla.json'
    set_sigla = json.loads(set_map_path.read_text()) if set_map_path.exists() else {}

    def tcgdex_to_liga_id(tcg_id):
        parts = str(tcg_id).split('-')
        if len(parts) != 2:
            return None
        sigla = set_sigla.get(parts[0])
        if not sigla:
            return None
        return sigla.upper() + '-' + parts[1].lstrip('0')

    df_base['liga_id'] = df_base['id'].apply(tcgdex_to_liga_id)
    return df_base


def predict_base(df_base):
    """Prediz USD e BRL para a base inteira."""
    model = pm.load_model()
    model_brl = pm.load_model_brl()

    X = pm.prepare_features(df_base)
    for c in pm.CAT_FEATURES:
        if c in X.columns:
            X[c] = X[c].fillna('Unknown').astype(str)
    df_base['pred_usd'] = np.expm1(model.predict(X))

    # BRL: usa USD como feature extra (igual ao treino)
    df_base['target_price_usd'] = df_base['target_price'].fillna(df_base['target_price'].median())
    X_brl = pm.prepare_features(df_base, extra_features=['target_price_usd'])
    for c in pm.CAT_FEATURES:
        if c in X_brl.columns:
            X_brl[c] = X_brl[c].fillna('Unknown').astype(str)
    try:
        df_base['pred_brl'] = np.expm1(model_brl.predict(X_brl))
    except Exception as e:
        print(f'  ⚠️ BRL predict falhou: {e}')
        df_base['pred_brl'] = np.nan
    return df_base, model, model_brl


def normalize_liga_num(s):
    """Extrai o número puro de sNumber/nEN (ex: '153JP' -> 153, '(#1/108)' -> 1)."""
    if s is None:
        return None
    s = str(s)
    m = re.search(r'(\d+)', s)
    return m.group(1).lstrip('0') if m else None


def map_jp_to_en_base(df_hits, df_base):
    """Fallback para cartas japonesas: mapeia sigla JP → set EN equivalente.

    Cartas JP não existem na base pokemontcg.io (a API não cobre sets
    japoneses). Este fallback mapeia a sigla da Liga para o set EN
    equivalente e junta por nome + set, usando o preço predito da carta
    EN (mesma raridade, artista, ilustração — o modelo é transferível).
    """
    JP = _load_jp_mapping()
    df = df_hits.copy()
    sigs = df.get('sSigla', pd.Series(dtype=str)).str.strip().str.upper()
    mask = sigs.isin(set(JP))
    if not mask.any():
        return df

    df_jp = df[mask].copy()
    df_jp['set_en'] = df_jp['sSigla'].str.strip().str.upper().map(JP)
    df_jp['nome_limpo'] = df_jp.get('nEN', pd.Series(dtype=str)).str.split('(').str[0].str.strip().str.lower()

    # Match por nome + set EN (ignora numeração, que difere entre JP e EN)
    df_base['nome_b'] = df_base['name'].str.lower().str.strip()
    df_base['set_en_base'] = df_base['id'].str.split('-').str[:-1].str.join('-')

    matched = df_jp.merge(
        df_base[['nome_b', 'set_en_base', 'pred_usd', 'pred_brl', 'target_price']],
        left_on=['nome_limpo', 'set_en'],
        right_on=['nome_b', 'set_en_base'],
        how='inner'
    )
    if len(matched) == 0:
        return pd.DataFrame()  # nada casou — retorna vazio (não inflar)

    # Marca como carta japonesa (preço estimado do equivalente EN)
    matched['is_jp'] = True

    # Deduplica: mesma carta JP pode bater com varias variantes EN (foil, holo, etc.)
    idx_col = df_jp.index.name or df_jp.iloc[:0, 0].name  # primeira coluna
    matched = matched.drop_duplicates(subset=idx_col, keep='first')
    matched = matched.drop(columns=['set_en', 'nome_limpo', 'nome_b', 'set_en_base'])
    # Retorna SÓ as linhas matched (não concat com df original — senão as
    # cartas JP aparecem 2x: cruas + matched, inflando df_out no chamador)
    return matched


def escorar_hits(df_base, top=10):
    """Para obter todos os arquivos de hits do dia e imprime top oportunidades."""
    files = sorted(glob.glob(str(LIGA_DIR / '*alta*.json')) + glob.glob(str(LIGA_DIR / '*queda*.json')))
    if not files:
        print('  Nenhum arquivo de hits encontrado.')
        return None

    print(f'\n📊 Escorando {len(files)} arquivos de hits...')
    resultados = []
    total_match = 0
    total_sem_match = 0
    for fpath in files:
        fname = Path(fpath).name
        try:
            data = json.loads(Path(fpath).read_text(encoding='utf-8'))
        except Exception:
            continue
        if not data:
            continue
        df_h = pd.DataFrame(data)
        if 'sSigla' not in df_h.columns or 'sNumber' not in df_h.columns:
            continue

        df_h['num'] = df_h['sNumber'].apply(normalize_liga_num)
        df_h['liga_id'] = df_h['sSigla'].str.strip().str.upper() + '-' + df_h['num']
        df_h['preco_real_brl'] = pd.to_numeric(df_h.get('p1b'), errors='coerce')
        # iCO real (enriquecido da página individual) quando disponível
        if 'iCO_real' in df_h.columns:
            df_h['iCO'] = pd.to_numeric(df_h.get('iCO_real'), errors='coerce').fillna(
                pd.to_numeric(df_h.get('iCO'), errors='coerce')).fillna(0)
        else:
            df_h['iCO'] = pd.to_numeric(df_h.get('iCO'), errors='coerce').fillna(0)

        # Nome EN puro (remove "(numero/...)" do nEN)
        if 'nEN' in df_h.columns:
            df_h['nome_en'] = df_h['nEN'].str.split('(').str[0].str.strip().str.lower()
        else:
            df_h['nome_en'] = ''

        df_m = df_h.merge(
            df_base[['liga_id', 'pred_usd', 'pred_brl', 'target_price']], on='liga_id', how='inner')

        # Fallback JP + nome+numero (cobre siglas sem mapping)
        if len(df_m) < len(df_h):
            ids_casados = set(df_m['liga_id']) if len(df_m) > 0 else set()
            rest = df_h[~df_h['liga_id'].isin(ids_casados)].copy()
            if len(rest) > 0:
                # JP fallback: já retorna linhas COM pred (match por nome+set EN)
                jp_matched = map_jp_to_en_base(rest, df_base)
                if len(jp_matched) > 0 and 'pred_usd' in jp_matched.columns:
                    jp_prontas = jp_matched[jp_matched['pred_usd'].notna()].copy()
                    if len(jp_prontas) > 0:
                        # Mantém apenas as que realmente casaram (tem pred da base)
                        df_m = pd.concat([df_m, jp_prontas], ignore_index=True) if len(df_m) > 0 else jp_prontas
                        # As não-casadas pelo JP seguem para o fallback nome+num
                        jp_ids = set(jp_prontas['liga_id']) if 'liga_id' in jp_prontas.columns else set()
                        rest = rest[~rest['liga_id'].isin(jp_ids)] if jp_ids else rest

                df_base['nome_en_b'] = df_base['name'].str.lower().str.strip()
                df_base['num_b'] = df_base['id'].str.split('-').str[-1].str.lstrip('0')
                base_com_preco = df_base[df_base['target_price'].notna() & (df_base['target_price'] > 0)]
                if len(rest) > 0:
                    mais = rest.merge(
                        base_com_preco[['nome_en_b', 'num_b', 'pred_usd', 'pred_brl', 'target_price']],
                        left_on=['nome_en', 'num'], right_on=['nome_en_b', 'num_b'], how='inner')
                    mais = mais.drop(columns=['nome_en_b', 'num_b'])
                    if len(mais) > 0:
                        df_m = pd.concat([df_m, mais], ignore_index=True) if len(df_m) > 0 else mais

        # Colapsa liga_ids duplicados (base com sets ptcg → mesma sigla Liga)
        if len(df_m) > 0:
            df_m = df_m.drop_duplicates(subset=['liga_id'], keep='first')

        total_match += len(df_m)
        total_sem_match += len(df_h) - len(df_m)
        if len(df_m) == 0:
            continue
        df_m['fonte'] = fname
        resultados.append(df_m)

    if not resultados:
        print(f'  Nenhum hit com match (sem match: {total_sem_match}).')
        return None

    print(f'  Match: {total_match} | Sem match: {total_sem_match}')
    df_out = pd.concat(resultados, ignore_index=True)
    return finalizar(df_out, top, prefixo='HITS')


def escorar_snapshot(df_base, top=15):
    """Escora o snapshot mais recente da Liga e imprime top oportunidades."""
    snaps = sorted(SNAP_DIR.glob('liga_snapshot_*.json'))
    if not snaps:
        print('  Nenhum snapshot encontrado em data/liga/snapshots/.')
        return None
    fpath = snaps[-1]
    print(f'\n📊 Escorando snapshot: {fpath.name}')
    data = json.loads(fpath.read_text(encoding='utf-8'))
    if not data:
        print('  Snapshot vazio.')
        return None

    df_s = pd.DataFrame(data)
    if 'sSigla' not in df_s.columns:
        print('  Snapshot sem coluna sSigla.')
        return None

    # Número: usa sN se existir, senão extrai de nEN "(#1/108)"
    if 'sN' in df_s.columns:
        df_s['num'] = df_s['sN'].apply(normalize_liga_num)
    else:
        df_s['num'] = df_s['nEN'].apply(normalize_liga_num)
    df_s['liga_id'] = df_s['sSigla'].str.strip().str.upper() + '-' + df_s['num']
    df_s['preco_real_brl'] = pd.to_numeric(df_s.get('p1b'), errors='coerce')
    df_s['iCO'] = pd.to_numeric(df_s.get('iCO'), errors='coerce').fillna(0)

    # Nome EN puro (remove "(parma/...)" do nEN)
    if 'nEN' in df_s.columns:
        df_s['nome_en'] = df_s['nEN'].str.split('(').str[0].str.strip().str.lower()
    else:
        df_s['nome_en'] = ''

    df_out = df_s.merge(
        df_base[['liga_id', 'pred_usd', 'pred_brl', 'target_price']], on='liga_id', how='inner')

    # Fallback JP + nome+numero
    if len(df_out) < len(df_s):
        ids_casados = set(df_out['liga_id']) if len(df_out) > 0 else set()
        rest = df_s[~df_s['liga_id'].isin(ids_casados)].copy()
        if len(rest) > 0:
            # JP fallback: já retorna linhas COM pred (match por nome+set EN)
            jp_matched = map_jp_to_en_base(rest, df_base)
            if len(jp_matched) > 0 and 'pred_usd' in jp_matched.columns:
                jp_prontas = jp_matched[jp_matched['pred_usd'].notna()].copy()
                if len(jp_prontas) > 0:
                    df_out = pd.concat([df_out, jp_prontas], ignore_index=True) if len(df_out) > 0 else jp_prontas
                    jp_ids = set(jp_prontas['liga_id']) if 'liga_id' in jp_prontas.columns else set()
                    rest = rest[~rest['liga_id'].isin(jp_ids)] if jp_ids else rest

            df_base['nome_en_b'] = df_base['name'].str.lower().str.strip()
            df_base['num_b'] = df_base['id'].str.split('-').str[-1].str.lstrip('0')
            base_com_preco = df_base[df_base['target_price'].notna() & (df_base['target_price'] > 0)]
            if len(rest) > 0:
                mais = rest.merge(
                    base_com_preco[['nome_en_b', 'num_b', 'pred_usd', 'pred_brl', 'target_price']],
                    left_on=['nome_en', 'num'], right_on=['nome_en_b', 'num_b'], how='inner')
                mais = mais.drop(columns=['nome_en_b', 'num_b'])
                if len(mais) > 0:
                    df_out = pd.concat([df_out, mais], ignore_index=True) if len(df_out) > 0 else mais

    # Deduplica ANTES da contagem: base com liga_id duplicado (101 casos:
    # sets ptcg diferentes → mesma sigla Liga) e snapshot com variantes
    # (ex: WAK-45 ×8). O merge multiplica linhas; aqui colapsa para o
    # primeiro match (o dedup final por liga_id faria o mesmo, mas a
    # contagem de Sem match sairia negativa).
    if len(df_out) > 0 and 'liga_id' in df_out.columns:
        antes = len(df_out)
        df_out = df_out.drop_duplicates(subset=['liga_id'], keep='first')
        if len(df_out) < antes:
            print(f'  ↳ Colapsado no merge: {antes} → {len(df_out)} (liga_ids duplicados)')

    print(f'  Match: {len(df_out)} | Sem match: {len(df_s) - len(df_out)}')
    if len(df_out) == 0:
        print('  Nenhum match com a base (verifique o mapping).')
        return None

    return finalizar(df_out, top, prefixo='SNAPSHOT')


def _set_nome_cache():
    """Cache do mapa sigla-Liga → nome do set (via mapping inverso + cache ptcg)."""
    if not hasattr(_set_nome_cache, '_cache'):
        import json
        from pathlib import Path
        base_dir = Path(__file__).resolve().parent.parent
        _set_nome_cache._cache = {}
        # mapping ptcg→sigla Liga
        map_path = base_dir / 'data' / 'liga' / 'liga_set_sigla_ptcg.json'
        if map_path.exists():
            ptcg2liga = json.loads(map_path.read_text(encoding='utf-8'))
        else:
            ptcg2liga = {}
        liga2ptcg = {v: k for k, v in ptcg2liga.items()}
        # nomes dos sets ptcg no cache
        cache_path = base_dir / 'data' / 'ptcg_cards_cache.json'
        if cache_path.exists():
            cards = json.loads(cache_path.read_text(encoding='utf-8'))
            set_nomes = {}
            for c in cards:
                sid = (c.get('set') or {}).get('id', '')
                if sid and sid not in set_nomes:
                    set_nomes[sid] = (c.get('set') or {}).get('name', '')
            for sigla, ptcg_id in liga2ptcg.items():
                nome = set_nomes.get(ptcg_id)
                if nome:
                    _set_nome_cache._cache[sigla.upper()] = nome
    return _set_nome_cache._cache


def finalizar(df, top, prefixo):
    """Calcula upside (BRL preferencial), marca oportunidades, imprime top e salva."""
    # Nome do set: usa ed_sNome se existir; senão resolve via mapping
    if 'ed_sNome' not in df.columns:
        df['ed_sNome'] = ''
    nomes = _set_nome_cache()
    sem_nome = df['ed_sNome'].fillna('').astype(str).str.strip() == ''
    if sem_nome.any() and 'sSigla' in df.columns:
        df.loc[sem_nome, 'ed_sNome'] = df.loc[sem_nome, 'sSigla'].astype(str).str.strip().str.upper().map(nomes).fillna('')

    # Real BRL se tiver preço; pred BRL se tiver; senão USD
    tem_brl = df['preco_real_brl'].notna() & (df['preco_real_brl'] > 0)
    df['moeda'] = np.where(tem_brl, 'R$', '$')
    df['real_ref'] = np.where(tem_brl, df['preco_real_brl'], np.nan)
    df['pred_ref'] = np.where(tem_brl & df['pred_brl'].notna(), df['pred_brl'], df['pred_usd'])

    # Cartas SEM preço BRL: usa preço USD da base pokemontcg como real
    sem_brl = ~tem_brl
    if sem_brl.any():
        df.loc[sem_brl, 'real_ref'] = df.loc[sem_brl, 'target_price'] if 'target_price' in df.columns else np.nan

    df = df[df['real_ref'].notna() & (df['real_ref'] > 0)].copy()
    df['upside_pct'] = ((df['pred_ref'] - df['real_ref']) / df['real_ref'] * 100).clip(-500, 500)
    df['oportunidade'] = df['upside_pct'].apply(
        lambda x: '🔥 Subvalorizada' if x > 25 else
                  ('👍 Leve Desconto' if x > 10 else
                   ('💀 Inflacionada' if x < -25 else '⚖️ Preço Justo')))

    # Deduplica: mesma carta aparece em varios arquivos de hits
    # Prioriza linhas com iCO_real (enriquecidas) sobre iCO=0 (hits crus)
    if 'liga_id' in df.columns:
        antes = len(df)
        df['_tem_ico_real'] = df.get('iCO_real', pd.Series(0, index=df.index)).fillna(0).astype(int) > 0
        df = df.sort_values(['_tem_ico_real', 'upside_pct'], ascending=[False, False]) \
               .drop_duplicates(subset=['liga_id'], keep='first')
        df = df.drop(columns=['_tem_ico_real'])
        if len(df) < antes:
            print(f'  ↳ Deduplicado: {antes} → {len(df)} cartas únicas')

    baratas = df[df['oportunidade'] == '🔥 Subvalorizada'].sort_values('upside_pct', ascending=False)
    caras = df[df['oportunidade'] == '💀 Inflacionada'].sort_values('upside_pct')

    print(f'\n{"="*64}')
    print(f'🏆 OPORTUNIDADES — {prefixo}')
    print(f'{"="*64}')
    print(f'  Total cartas enscoradas: {len(df)}')
    print(f'  🔥 Subvalorizadas (Pred > Real +25%): {len(baratas)}')
    print(f'  👍 Leve Desconto (Pred > Real +10-25%): {len(df[df["oportunidade"] == "👍 Leve Desconto"])}')
    print(f'  ⚖️  Preço Justo (-25% a +10%):          {len(df[df["oportunidade"] == "⚖️ Preço Justo"])}')
    print(f'  💀 Inflacionadas (Real > Pred +25%):   {len(caras)}')

    # Oportunidades acionáveis: preço real >= 5 (BRL) ou >= 2 (USD)
    baratas_acao = baratas[(baratas['real_ref'] >= 5) | ((baratas['moeda'] == '$') & (baratas['real_ref'] >= 2))].copy()
    if len(baratas_acao) > 0:
        baratas_acao['tem_ico'] = baratas_acao['iCO'].fillna(0).astype(int) > 0
        baratas_acao = baratas_acao.sort_values(['tem_ico', 'upside_pct'], ascending=[False, False])
    if len(baratas) > 0:
        print(f'\n🔥 TOP {min(top, len(baratas_acao))} SUBVALORIZADAS (comprar) — real >= R$5/$2:')
        print(f'  {"Carta":30s} | {"Set":12s} | {"Real":>10s} | {"Pred":>10s} | {"Upside":>7s} | iCO')
        print(f'  {"-"*84}')
        for _, r in baratas_acao.head(top).iterrows():
            nome = str(r.get('nPT', r.get('name', r.get('nome', '?'))))[:30]
            sigla = str(r.get('sSigla', r.get('set_id', '?')))[:12]
            moeda = r['moeda']
            ico = int(r.get('iCO', 0) or 0)
            print(f'  {nome:30s} | {sigla:12s} | {moeda}{float(r["real_ref"]):>8.2f} | {moeda}{float(r["pred_ref"]):>8.2f} | +{float(r["upside_pct"]):5.0f}% | {ico}')

    if len(caras) > 0:
        print(f'\n💀 TOP 10 INFLACIONADAS (evitar):')
        print(f'  {"Carta":30s} | {"Set":12s} | {"Real":>10s} | {"Pred":>10s} | {"Upside":>7s} | iCO')
        print(f'  {"-"*84}')
        for _, r in caras.head(10).iterrows():
            nome = str(r.get('nPT', r.get('name', r.get('nome', '?'))))[:30]
            sigla = str(r.get('sSigla', r.get('set_id', '?')))[:12]
            moeda = r['moeda']
            ico = int(r.get('iCO', 0) or 0)
            print(f'  {nome:30s} | {sigla:12s} | {moeda}{float(r["real_ref"]):>8.2f} | {moeda}{float(r["pred_ref"]):>8.2f} | {float(r["upside_pct"]):+5.0f}% | {ico}')

    # Salvar CSV
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    tipo = prefixo.lower()
    out = SCORE_DIR / f'scored_{tipo}_{ts}.csv'
    df.to_csv(out, index=False)
    print(f'\n💾 Salvo: {out} ({len(df)} linhas)')
    return df


def main():
    parser = argparse.ArgumentParser(description='Escra hits/snapshot com cache local')
    parser.add_argument('--tipo', choices=['hits', 'snapshot'], required=True)
    parser.add_argument('--top', type=int, default=10)
    args = parser.parse_args()

    print('📦 Carregando features do cache local...')
    df_base = load_base_features()
    df_base = build_liga_id_from_base(df_base)
    df_base, _, _ = predict_base(df_base)
    print(f'  Base: {len(df_base)} cartas com predição')

    if args.tipo == 'hits':
        escorar_hits(df_base, top=args.top)
    else:
        escorar_snapshot(df_base, top=args.top)


if __name__ == '__main__':
    main()