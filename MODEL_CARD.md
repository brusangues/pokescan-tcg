# Model Card — Previsão de Preço Pokémon TCG

## Objetivo
Prever o preço de mercado (TCGPlayer USD) de cartas Pokémon TCG usando dados da API TCGdex, e monitorar periodicamente outliers e variações de preço.

---

## Etapas da Pipeline

```
TCGdex API → Coleta de sets (50 sets, ~5800 cartas)
                 ↓
          Metadados (nome, raridade, tipo, etc.)
                 ↓
          Enrich Pricing (TCGPlayer USD via TCGdex individual)
                 ↓
          Feature Engineering
                 ↓
          CatBoost Regressor
                 ↓
          Snapshot CSV (preço real, predito, resíduo, outliers)
```

---

## Fontes de Dados

| Fonte | Dados | Estabilidade |
|---|---|---|
| **TCGdex** | Metadados das cartas em pt-BR (nome, raridade, tipo, set, HP, estágio, Pokédex #) | ✅ Estável, sem Cloudflare |
| **TCGdex (pricing EN)** | Preço TCGPlayer USD (holofoil/normal) via endpoint individual | ✅ Estável (~0.3s por carta) |
| **Popularidade** | Score heurístico calculado a partir da própria base TCGdex | ✅ Offline, sem dependência externa |

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

---

## Arquivos

| Arquivo | Descrição |
|---|---|
| `pokemon_price_monitor.py` | Pipeline completa (coleta → features → predição → snapshot) |
| `pokemon_popularity.py` | Geração do score de popularidade |
| `01_coleta.ipynb` | Coleta via TCGdex |
| `02_eda_features.ipynb` | EDA e feature engineering |
| `03_modelagem.ipynb` | Treino e avaliação do modelo |
| `data/catboost_model.cbm` | Modelo serializado |
| `data/pokemon_popularity.json` | Cache dos scores de popularidade |
| `data/monitoring/snapshot_*.csv` | Snapshots periódicos com predições |

---

## Próximas Melhorias Potenciais
- [x] Preços brasileiros (BRL) via crawler Liga Pokémon — integrado no snapshot
- [ ] Modelo de previsão em BRL (target separado)
- [ ] R² na pipeline de monitoramento
- [ ] Features de texto (nome do artista, flavor text via embeddings)
- [ ] Data augmentation (preços históricos)
