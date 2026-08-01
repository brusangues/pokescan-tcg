# Model Card — Previsão de Preço Pokémon TCG

## Objetivo
Prever o preço de mercado de cartas Pokémon TCG (USD TCGPlayer + BRL Liga Pokémon) usando features da API pokemontcg.io, e monitorar oportunidades de compra (cartas subvalorizadas vs. predição).

---

## Etapas da Pipeline

```
pokemontcg.io API → Coleta (174 sets, ~20k cartas, até 2026)
                 ↓
          Metadados (nome, raridade, tipos, hp, set, release_date)
                 ↓
          Pricing embutido (TCGPlayer USD + Cardmarket EUR avg1/7/30)
                 ↓
          Merge BRL (Liga Pokémon via mapping de siglas + iCO)
                 ↓
          Feature Engineering (embeddings DINOv2, grail, popularidade)
                 ↓
          CatBoost Regressor + Classificador de bins
                 ↓
          Escoragem (hits diários, snapshots, sets recentes)
```

---

## Fontes de Dados

| Fonte | Dados | Cobertura |
|---|---|---|
| **pokemontcg.io** | Features (rarity, types, hp, set, release_date), USD TCGPlayer (`market`), Cardmarket EUR (`avg1/7/30`, trend) — embutidos no payload | 174 sets, até jul/2026 |
| **Liga Pokémon** | Preços BRL (`p1b`), `iCO` (nº vendedores), nome pt-BR — **fonte canônica pt-BR** | atualizado |
| TCGdex | Legado (descontinuado — sem sets 2024+) | até 2023 |

---

## Features (Variáveis)

### Categóricas
| Variável | Descrição | Exemplos |
|---|---|---|
| `rarity` | Raridade da carta | Rare Holo, Ultra Rare, Common |
| `primary_type` | Tipo principal do Pokémon | Fire, Water, Psychic |
| `set_series` | Série da coleção | Sword & Shield, Scarlet & Violet |
| `price_type` | Qual preço foi usado (holofoil ou normal) | holofoil, normal |
| `supertype` | Super tipo | Pokémon, Trainer, Energy |

### Numéricas
| Variável | Descrição |
|---|---|
| `hp` | Pontos de vida |
| `subtypes_count` | Quantidade de subtipos (ex: V, VMAX) |
| `set_printed_total` | Total de cartas no set |
| `release_year` | Ano de lançamento |
| `card_age_years` | Idade da carta em anos |
| `pokedex_number` | Número na Pokédex Nacional |
| **`pokemon_popularity`** | Score de popularidade do Pokémon (0-100) |

### Target
| Variável | Descrição | Transformação |
|---|---|---|
| `target_price` | Preço de mercado TCGPlayer USD | log1p (log_target) |

---

## Score de Popularidade (`pokemon_popularity`)

### Fórmula
```
card_score = log1p(n_cartas) × 3 + log1p(n_sets) × 2
score_final = card_score × gen_multiplier × legendary_boost
normalizado para 0-100
```

### Fatores
| Fator | Peso | Detalhes |
|---|---|---|
| Quantidade de cartas | 3× log1p | Mais cartas = mais popular |
| Quantidade de sets | 2× log1p | Presença em várias coleções |
| Geração | 1.0–1.5× | Gen 1 = 1.5×, Gen 2 = 1.3×, decrescente |
| Boost lendário | 1.5× | Charizard, Pikachu, Eeveelutions, etc |

### Top 10 Pokémon por Popularidade
```
1. Pikachu       100.0  ⭐
2. Lucario        88.8  ⭐
3. Gardevoir      87.4  ⭐
4. Charizard      84.1  ⭐
5. Eevee          84.1  ⭐
6. Mewtwo         83.0  ⭐
7. Rayquaza       78.6  ★
8. Umbreon        78.6  ★
9. Blastoise      78.1  ★
10. Espeon        76.6  ★
```

---

## Modelo: CatBoost Regressor

### Hiperparâmetros
| Parâmetro | Valor |
|---|---|
| iterations | 500 |
| learning_rate | 0.05 |
| depth | 6 |
| l2_leaf_reg | 3 |
| loss_function | MAE |
| eval_metric | MAE |
| early_stopping_rounds | 30 |
| random_seed | 42 |

### Validação
- Split temporal (80% treino / 20% teste) ordenado por `release_year`
- Cartas mais antigas no treino, recentes no teste

---

## Histórico de Métricas

> A partir de v5, o MAE reportado é no **conjunto de teste** (20% mais recentes, split temporal).
> Antes disso, o MAE era calculado sobre o dataset inteiro (otimista).

| Data | Versão | MAE USD (teste) | MAE BRL (teste) | R² USD | R² BRL | Fonte | Mudança |
|---|---|---|---|---|---|---|---|
| 2026-07-29 | v1 | — | — | — | — | pokemontcg.io | Pipeline inicial (2500 cartas) |
| 2026-07-29 | v2 | — | — | — | — | TCGdex | Migração p/ TCGdex (5176 cartas) |
| 2026-07-29 | v3 | — | — | — | — | TCGdex | Feature pokemon_popularity |
| 2026-07-29 | v4 | — | — | — | — | TCGdex + Liga | Integração preços BRL |
| 2026-07-29 | **v5** | $6.90 | R$14.11 | 0.077 | 0.006 | TCGdex + Liga (bulk) | Split temporal corrigido + eval_set pra early stopping |
| 2026-07-29 | v6 | $4.20 | — | 0.279 | — | TCGdex | Features cardmarket avg1/7/30/trend + rarity_tcg + grail + illustrator |
| 2026-07-31 | **v7** | $5.61 | R$43.35 | 0.289 | 0.040 | **pokemontcg.io** (20.479 cartas) | Migração p/ pokemontcg.io, 174 sets até 2026; merge BRL 7.908 cartas; USD Acc 85% / BRL Acc 56% |

---

## Arquivos

| Arquivo | Descrição |
|---|---|
| `pokemon_price_monitor.py` | Pipeline completa (coleta → features → predição → escoragem) |
| `ptcg_io.py` | Cliente da API pokemontcg.io (fetch/parse/pricing) |
| `poke_embeddings.py` | Embeddings DINOv2-small → PCA 16d |
| `pokemon_popularity.py` | Geração do score de popularidade |
| `script/score_sets_recentes.py` | Escoragem de sets recentes (ano parametrizável) |
| `crawler/crawler_liga_hits.py` | Crawler de cartas em alta/queda da Liga |
| `crawler/crawler_liga_snapshot.py` | Snapshot semanal da Liga |
| `PIPELINE.md` | **Documentação completa do pipeline (scripts, parâmetros, dados)** |
| `data/catboost_model.cbm` | Modelo USD serializado |
| `data/catboost_model_brl.cbm` | Modelo BRL serializado |
| `data/ptcg_cards_cache.json` | Cache de cartas pokemontcg.io (20.479, com pricing) |
| `data/scored/scored_*.csv` | Resultados de escoragem (hits, snapshots, recentes) |

---

## Próximas Melhorias Potenciais
- [x] Preços brasileiros (BRL) via crawler Liga Pokémon — integrado no snapshot
- [x] Modelo de previsão em BRL (target separado)
- [x] Migração para pokemontcg.io (sets até 2026)
- [x] Escoragem de oportunidades (subvalorizadas vs. predição)
- [ ] Modelo de previsão temporal (preço futuro) usando snapshots acumulados
- [ ] Features de texto (nome do artista, flavor text via embeddings)
- [ ] Data augmentation (preços históricos)
