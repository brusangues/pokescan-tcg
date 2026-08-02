"""
score_sets_recentes.py
======================
Escora cartas de sets a partir de um ano de corte.
Prediz preço BRL (quando disponível) ou USD, e sinaliza oportunidades
onde o modelo vê valor acima do preço de mercado.

Uso:
  python script/score_sets_recentes.py --ano 2025 --min-preco 10 --min-upside 25
"""

import sys, json, argparse
from pathlib import Path
import pandas as pd
import numpy as np

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
import pokemon_price_monitor as pm


def main():
    parser = argparse.ArgumentParser(description='Escora sets recentes')
    parser.add_argument('--ano', type=int, default=2025, help='Ano de corte (ex: 2025 para 2025+)')
    parser.add_argument('--min-preco', type=float, default=8, help='Preço mínimo real (BRL ou USD)')
    parser.add_argument('--min-upside', type=float, default=25, help='Upside mínimo em %')
    parser.add_argument('--top', type=int, default=30, help='Top N resultados')
    parser.add_argument('--salvar', default='data/scored/scored_recentes.csv', help='Onde salvar o CSV')
    args = parser.parse_args()

    # 1. Carregar cache de cartas (buscado uma única vez)
    cache_path = Path('data/ptcg_cards_cache.json')
    if not cache_path.exists():
        print('⚠️  Cache não encontrado. Baixando todas as cartas (pode levar alguns minutos)...')
        cards = pm.ptcg_io.fetch_all_cards_global()
        cache_path.write_text(json.dumps(cards, ensure_ascii=False), encoding='utf-8')
    else:
        cards = json.loads(cache_path.read_text(encoding='utf-8'))
    print(f'📦 Cache: {len(cards)} cartas')

    # 2. Filtrar por ano
    novos = [c for c in cards
             if int((c.get('set') or {}).get('releaseDate', '0/0/0').split('/')[0]) >= args.ano]
    print(f'📅 Sets >= {args.ano}: {len(novos)} cartas')

    if not novos:
        print(f'  Nenhuma carta encontrada para ano >= {args.ano}.')
        return

    # 3. Parse + pricing embutido
    df = pd.DataFrame([pm.parse_card(c) for c in novos])
    df['_raw'] = novos
    df = pm.enrich_pricing(df)
    df = pm.add_supply_features(df)  # E1: rarity_pool_size + pull_cost (antes do filtro)
    df = df[df['target_price'].notna() & (df['target_price'] > 0)].copy()

    # 4. Merge BRL (Liga Pokémon)
    lookup_brl, lookup_ico, set_map = pm.build_liga_lookup()
    df = pm.enrich_brl(df, lookup_brl, lookup_ico, set_map)

    n_brl = df['target_price_brl'].notna().sum()
    print(f'💰 Cartas com USD: {len(df)} | com BRL: {n_brl}')

    if len(df) == 0:
        print('  Nenhuma carta com preço disponível.')
        return

    # 5. Carregar modelos treinados
    model = pm.load_model()
    model_brl = pm.load_model_brl()
    print(f'🤖 Modelos carregados')

    # 6. Predizer USD
    X = pm.prepare_features(df)
    for c in pm.CAT_FEATURES:
        if c in X.columns:
            X[c] = X[c].fillna('Unknown').astype(str)
    df['pred_usd'] = np.expm1(model.predict(X))

    # 7. Predizer BRL (precisa de target_price_usd como feature)
    df['target_price_usd'] = df['target_price'].fillna(df['target_price'].median())
    X_brl = pm.prepare_features(df, extra_features=['target_price_usd'])
    for c in pm.CAT_FEATURES:
        if c in X_brl.columns:
            X_brl[c] = X_brl[c].fillna('Unknown').astype(str)
    df['pred_brl'] = np.expm1(model_brl.predict(X_brl))

    # 8. Referência: BRL quando disponível, USD caso contrário
    df['tem_brl'] = df['target_price_brl'].notna() & (df['target_price_brl'] > 0)
    df['moeda'] = np.where(df['tem_brl'], 'R$', '$')
    df['real_ref'] = np.where(df['tem_brl'], df['target_price_brl'], df['target_price'])
    df['pred_ref'] = np.where(df['tem_brl'], df['pred_brl'], df['pred_usd'])
    df['upside_pct'] = ((df['pred_ref'] / df['real_ref']) - 1) * 100
    df['oportunidade'] = df['upside_pct'].apply(
        lambda x: '🔥 Subvalorizada' if x > args.min_upside
        else ('👍 Leve Desconto' if x > 10
              else ('💀 Inflacionada' if x < -25
                    else '⚖️ Preço Justo'))
    )

    # 9. Filtrar oportunidades
    sub = df[(df['upside_pct'] > args.min_upside) & (df['real_ref'] >= args.min_preco)]
    sub = sub.sort_values('upside_pct', ascending=False)

    print(f'\n{"="*60}')
    print(f'🏆 OPORTUNIDADES — Sets >= {args.ano}')
    print(f'{"="*60}')
    print(f'Total: {len(df)} cartas escoradas')
    print(f'🔥 Subvalorizadas (upside > {args.min_upside}% e real >= {args.min_preco}): {len(sub)}')
    print(f'👍 Leve Desconto (10-{args.min_upside}%): {len(df[df["oportunidade"] == "👍 Leve Desconto"])}')
    print(f'⚖️  Preço Justo: {len(df[df["oportunidade"] == "⚖️ Preço Justo"])}')
    print(f'💀 Inflacionadas (real > pred +25%): {len(df[df["oportunidade"] == "💀 Inflacionada"])}')

    if len(sub) > 0:
        print(f'\n{"─"*60}')
        print(f'Top {min(args.top, len(sub))} Subvalorizadas')
        print(f'{"─"*60}')
        print(f'{"Carta":32s} | {"Set":24s} (Ano) | {"Real":>10s} | {"Pred":>10s} | {"Upside":>7s} | iCO')
        print(f'{"─"*60}')
        for _, r in sub.head(args.top).iterrows():
            nome = str(r['name'])[:32]
            set_n = str(r['set_name'])[:24]
            ano = int(r['release_year']) if pd.notna(r['release_year']) else 0
            ico = int(r['iCO']) if pd.notna(r['iCO']) else 0
            moeda = r['moeda']
            print(f'{nome:32s} | {set_n:24s} ({ano}) | {moeda}{r["real_ref"]:>8.2f} | {moeda}{r["pred_ref"]:>8.2f} | +{r["upside_pct"]:5.0f}% | {ico}')

    # 10. Salvar CSV completo
    out = Path(args.salvar)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f'\n💾 Salvo: {out} ({len(df)} linhas)')


if __name__ == '__main__':
    main()