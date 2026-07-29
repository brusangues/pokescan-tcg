# Plano: Previsão de Preço de Cartas Pokémon TCG

## Objetivo
Pipeline completo de ML para prever o preço de mercado (TCGPlayer) de cartas Pokémon TCG,
com monitoramento contínuo de outliers.

## Etapas

### ✅ 1. Coleta de dados (feito)
- Pokémon TCG API → 1000 cartas
- Salvo em `data/cards_raw.json`

### ✅ 2. EDA + Feature Engineering (feito)
- 892 cartas válidas com preço
- Feature: raridade, tipo, HP, ano de lançamento, idade, etc.
- Dataset em `data/cards_processed.csv`

### ✅ 3. Modelagem (feito)
- CatBoost → MAE $3.47, R² -0.47 (baseline)
- Features categóricas + numéricas simples
- Gráfico: `catboost_results.png`

### 4. Script de Monitoramento (pendente)
Script único que:
- Faz o pipeline inteiro: coleta → features → predição
- Salva resultado em `data/monitoring/` com timestamp
- Gera CSV com: id, nome, rarity, preço_real, preço_predito, resíduo, data_coleta
- Identifica outliers (resíduo > 2 desvios)
- Compara com snapshot anterior (delta de preço)

### 5. Cron job (pendente)
- Roda o script a cada N horas/dias via `quota-status.sh`
- `no_agent=True` — salva CSV silenciosamente
- Alerta se encontrar outlier grande

## Dataset
- **Fonte:** `https://api.pokemontcg.io/v2/cards`
- **Campos:** name, supertype, hp, types, rarity, set, tcgplayer.prices
- **Volume:** ~1000 cartas por execução

## Stack
- Python 3.11+
- pandas, numpy, requests
- CatBoost
- cron (Hermes cronjob no_agent)
