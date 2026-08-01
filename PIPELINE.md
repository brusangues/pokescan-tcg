# Pipeline de Predição de Preços — PokéScan TCG

Sistema de predição de preços de Pokémon TCG (USD e BRL) com coleta, treino e escoragem.
**Fonte canônica pt-BR: Liga Pokémon** (preços BRL + ID canônico). **Fonte de features: pokemontcg.io** (até 2026).

---

## Arquivos Principais

| Arquivo | Papel |
|---|---|
| `pokemon_price_monitor.py` | Pipeline completo: fetch → parse → pricing → merge BRL → features → treino CatBoost (USD/BRL) → snapshot → escoragem |
| `ptcg_io.py` | Cliente da API pokemontcg.io: fetch/parse/pricing (fonte de features) |
| `poke_embeddings.py` | Embeddings DINOv2-small (384d) → PCA 16d por imagem |
| `pokemon_popularity.py` | Score de popularidade por nome de Pokémon |
| `script/score_sets_recentes.py` | Escora sets recentes e sinaliza subvalorizadas |
| `crawler/crawler_liga_hits.py` | Raspa cartas em alta/queda da Liga (6 combinações) |
| `crawler/crawler_liga_snapshot.py` | Snapshot semanal completo da Liga |
| `crawler/crawler_liga_bulk.py` | Crawl em massa dos sets da Liga (descobre IDs, baixa set_N.json) |
| `crawler/scrapers.py` | Driver undetected-chromedriver (Chrome) p/ bypass de Cloudflare |
| `crawler/crawl_tcgdex.py` | Legado: coleta TCGdex (descontinuado, TCGdex para em 2023) |

---

## Fontes de Dados

| Fonte | Uso | Cobertura |
|---|---|---|
| **pokemontcg.io** | Features (rarity, types, hp, set, release_date), preço USD TCGPlayer (`market`), Cardmarket EUR (`avg1/7/30`, `trendPrice`) — tudo embutido no payload | 174 sets, até jul/2026 |
| **Liga Pokémon** | Preços BRL (`p1b` = médio), `iCO` (nº vendedores), nome pt-BR — **fonte canônica** | 194+ sets, atualizado |
| TCGdex | Legado (mapping `liga_set_sigla.json`) | até 2023 |

---

## Treinamento

```bash
# Python do projeto (com torch/CUDA)
C:/Models/hermes/hermes-agent/venv/Scripts/python

# Treinar USD + BRL com todos os sets
python -c "import pokemon_price_monitor as pm; pm.train_model(max_sets=174); pm.train_model_brl(max_sets=174)"
```

- **Split temporal 80/20** por `release_year` (antigas → treino, recentes → teste), `eval_set` + early stopping.
- **Target**: `log1p(preço)`; regressão CatBoost + classificador de 5 bins de preço (Acc/F1).
- Features: hp, rarity_tcg, types, set, release_year, idade, pokedex, popularidade, iCO, grail score, lendário/shiny/holo, illustrator, trainer_gender, embeddings DINOv2 (16d), cardmarket avg1/7/30/trend/low.
- Modelo BRL usa `target_price_usd` como feature extra.
- **Métricas (último treino)**: USD MAE $5.61 / R² 0.289 / Acc 85%; BRL MAE R$43 / R² 0.04 / Acc 56%. (R² BRL baixo = mercado BR ruidoso; usar classificador de bins como sinal.)

**Atenção**: 1º fetch de todas as cartas (~20k) leva ~10 min (rate limit); usa cache em `data/ptcg_cards_cache.json` (43MB, fora do git).

---

## Escoragem (oportunidades)

```bash
# Sets recentes (padrão: 2025+, real >= 8, upside > 25%)
python script/score_sets_recentes.py --ano 2025 --min-preco 10 --min-upside 25 --top 30 --salvar data/scored/scored_recentes.csv

# Hits diários da Liga (cartas em alta/queda)
python -c "import pokemon_price_monitor as pm; pm.score_hits()"

# Snapshot semanal
python -c "import pokemon_price_monitor as pm; pm.score_snapshot()"
```

- `score_hits`/`score_snapshot` marcam 🔥 Subvalorizada (pred > real +25%), 👍 Leve, ⚖️ Justa, 💀 Inflacionada.
- `score_sets_recentes.py` usa **BRL quando disponível** (moeda `R$`), senão USD (`$`).
- Parâmetros: `--ano` (corte), `--min-preco`, `--min-upside`, `--top`, `--salvar`.

---

## Crawlers (Liga Pokémon)

```bash
# 1. Hits diários: 6 combinações (day/week/month × alta/queda), 50 cartas cada
python crawler/crawler_liga_hits.py --tipo all        # ou day|week|month
# Saída: data/liga/{day|week|month}_{alta|queda}_YYYYMMDD_HHMMSS.json

# 2. Snapshot semanal completo (todos os sets)
python crawler/crawler_liga_snapshot.py --max-sets 999
# Saída: data/liga/snapshots/liga_snapshot_YYYYMMDD_HHMMSS.json

# 3. Bulk (uma vez): descobre IDs e baixa sets
python crawler/crawler_liga_bulk.py --discover-only    # descobre IDs
python crawler/crawler_liga_bulk.py --max-sets 200     # baixa sets
# Saída: data/liga/liga_set_ids.json, data/liga/set_{id}.json
```

**Crons ativos** (Hermes):
- `liga-hits-diario` — diário 08:00 — crawler_liga_hits.py --tipo all
- `liga-snapshot-semanal` — seg 08:00 — crawler_liga_snapshot.py

---

## Onde os dados ficam

| Local | Conteúdo |
|---|---|
| `data/ptcg_cards_cache.json` | Cache de todas as cartas pokemontcg.io (20.479, com pricing embutido) |
| `data/liga/liga_set_sigla_ptcg.json` | **Mapping canônico** set_id pokemontcg → sigla Liga (224 sets) |
| `data/liga/liga_set_sigla.json` | Mapping legado TCGdex → sigla Liga (228) |
| `data/liga/liga_all_cards.csv` | Todas as cartas BRL da Liga (17.474) |
| `data/liga/set_{id}.json` | Cartas por set da Liga (com p1a/p1b/p1c, iCO, sSigla, nEN) |
| `data/liga/{periodo}_{tipo}_*.json` | Hits diários (day/week/month × alta/queda) |
| `data/liga/snapshots/liga_snapshot_*.json` | Snapshots semanais da Liga |
| `data/monitoring/snapshot_*.csv` | Snapshots TCGdex/pokemontcg com predições (USD+BRL) |
| `data/scored/scored_hits_*.csv` | Resultado da escoragem de hits |
| `data/scored/scored_snapshot_*.csv` | Resultado da escoragem de snapshots |
| `data/scored/scored_recentes.csv` | Escoragem de sets recentes |
| `data/pokemon_embeddings_16d.csv` | Embeddings DINOv2 PCA-16d (5.608 cartas) |
| `data/img_cache/` | Imagens baixadas (para embeddings) |
| `data/catboost_model.cbm` | Modelo USD treinado |
| `data/catboost_model_brl.cbm` | Modelo BRL treinado |

---

## ID Canônico

`SIGLA-NÚMERO` (ex: `SV1-3`) — construído dos campos da Liga `sSigla` (maiúsculo) + `sNumber` (sem zeros à esquerda). Todas as fontes (pokemontcg.io, TCGdex) são convertidas para esse ID via `liga_set_sigla_ptcg.json`. A Liga é a verdade pt-BR.
