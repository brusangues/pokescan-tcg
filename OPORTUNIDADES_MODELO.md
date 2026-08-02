# Relatório de Oportunidades de Modelagem
## Fonte: PokeDataDadGuy (19 transcrições + resumo com ideias) × Projeto pokescan-tcg

> Escopo: **somente modelagem**. Plataforma/website (Collectrics) fora do interesse.
> Data: 2026-08-02 | Projeto: `C:/projects/pokescan-tcg` (branch `hermes`)

---

## 1. Estado atual do nosso modelo (baseline para o cruzamento)

**Stack**: CatBoost (regressão `log1p(preço)` + classificador de 5 bins), split temporal 80/20, early stopping.

| Modelo | MAE teste | R² teste | Acc | F1 | Dados |
|---|---|---|---|---|---|
| USD | $5.61 | 0.289 | 85.0% | 0.839 | 18.694 cartas (1999–2026) |
| BRL | R$43.35 | 0.040 | 55.8% | 0.530 | 7.908 cartas (merge Liga) |

**Features atuais** (32):
- **Cat**: `rarity_tcg`, `primary_type`, `set_series`, `price_type`, `supertype`, `illustrator`, `trainer_gender`
- **Num**: `hp`, `subtypes_count`, `set_printed_total`, `release_year`, `card_age_years`, `pokedex_number`, `pokemon_popularity`, `iCO`, `pokemon_grail_score` + Cardmarket (`avg`, `avg1`, `avg7`, `avg30`, `trend`, `low`) + flags de arte (`is_holo`, `is_reverse`, `is_normal`, `is_shiny`, `is_legendary`) + embeddings DINOv2 16d (`emb_0..15`)
- **BRL extra**: `target_price_usd`

**Dados disponíveis**: cache completo pokemontcg.io (20.479 cartas, 174 sets até jul/2026, com `rarity`, `types`, `hp`, `artist`, `set.ptcgoCode`, `set.printedTotal`, `tcgplayer.market`, `cardmarket.avg1/7/30`), Liga Pokémon (`p1b`, `iCO`, snapshots semanais acumulando), embeddings DINOv2, mapping de 224 sets.

---

## 2. Lacunas identificadas (o que o Youtuber faz e nós não temos)

### 2.1. Supply: **Pull Cost** — a feature mais importante do modelo dele
Ele modela o lado da oferta como **custo monetário de puxar a carta**:
```
pull_cost = pull_rate × rarity_pool_size × pack_price
```
- Ex: Prismatic = 1/45 packs × 32 SIRs no pool → caro de puxar → preço alto.
- No nosso modelo, `rarity_tcg` e `set_printed_total` são proxies fracos: não capturam *quantas cartas competem no mesmo slot de raridade*.

**→ Oportunidade alta**: computar `rarity_pool_size` por set a partir do próprio cache (contagem de cartas por raridade dentro de cada set — já temos isso em 20.479 cartas). A `pull_rate` pode ser aproximada por `1 / rarity_pool_size` (fallback) ou estimada de dados públicos. Pack price = parâmetro simples por set (constante ~$4/booster).

### 2.2. Demand: **Desirability Index** (Character Premium + Universal Appeal)
O modelo dele (regressão linear, R²=0.88) usa:
- **Character Premium (45%)**: histórico de prêmio de preço por personagem (Charizard ~1.1, Umbreon ~1.3, Mew ~1.4).
- **Artwork/Appeal (45%)**: nota 1–10 (depois substituído por *Grading Intensity* objetivo).
- **Universal Appeal (10%)**: Google Trends.

**→ Oportunidade alta**: nosso `pokemon_popularity` é heurístico (contagem de cartas × gen × lendário). Podemos **calcular um verdadeiro Character Premium a partir dos nossos próprios dados**: preço médio histórico por espécie (agregar `target_price` por `pokedex_number`, normalizar vs. mediana do ano). É uma feature nova, derivável 100% offline do cache.

### 2.3. **Grading Dynamics** (PSA pop, gem rate, grading intensity)
O maior multiplicador de valor do hobby moderno: `psa10_value / raw_price` chega a 10–30× em cartas certas. Ele usa:
- `psa_total_pop`, `psa10_gem_rate`, `grading_intensity` (frequência de submissão mensal normalizada por popularidade do hobby), `grading_gain_multiplier`.

**→ Oportunidade média**: não temos dados PSA. Fonte pública: PSA pop reports (API não oficial) + gemrate. É a única feature do relatório que exige **fonte externa nova**. Alta recompensa: nosso modelo USD tem R² 0.289; a componente gradada (PSA 10) explica muito da variância em cartas modernas que hoje cai no erro.

### 2.4. **Liquidez real-time** (demand pressure, supply saturation)
Ele raspa eBay diariamente e calcula:
```
demand_pressure = vendidos / (ativos + vendidos)
supply_saturation_shift = (7d novos+ativos) / (30d)
```
Rótulos: *Demand Tightening* (preço vai subir), *Market Cooling* (vai cair). Ele provou que comprar 18 cartas de Nacli não move o preço (inventário profundo), mas buyout de Bewear/Riolu (pouco inventário) dispara 100% de pressure.

**→ Oportunidade média**: nós temos `iCO` (nº de ofertantes na Liga) como proxy de liquidez, mas é um **snapshot pontual**. Os **snapshots semanais estão acumulando** (`data/liga/snapshots/`) — dá para construir **séries temporais de iCO e preço por carta** e derivar features de tendência (ΔiCO 7d, Δpreço 7d, pressão de demanda aproximada = vendas implícitas). Sem scrape de eBay; só explora o que já coletamos.

### 2.5. **Guardrails anti-manipulação (anomaly suppression)**
Ele demonstrou que 4 vendas baratas na TCGplayer derrubaram o preço "de mercado" do Mega Gengar de $1.300 → $730 nos agregadores, e que guardrails (volume mínimo diário + variação máxima) preservam o preço real.

**→ Oportunidade alta e barata**: nossas fontes (pokemontcg `market`, cardmarket `avg1/7/30`, Liga `p1b`) são igualmente vulneráveis. Podemos criar um **preço normalizado multi-fonte** por carta:
```
price_norm = média ponderada(tcgplayer.market, cardmarket.avg30 × câmbio, liga.p1b)
+ flag de anomalia quando fontes divergem > X% ou volume (iCO) < limiar
```
Isso melhora o **target** dos modelos (menos ruído de outliers) e a **escoragem** (menos falso positivo de "subvalorizada" por pico falso).

### 2.6. **Sazonalidade (Google Trends + Summer Slump)**
Ele documenta o **summer slump recorrente (maio–julho)** e a recuperação outono/inverno, usando Google Trends para prever ciclos.

**→ Oportunidade baixa/média**: já temos `card_age_years` (captura a curva de decaimento pós-lançamento). Adicionar **`seasonality_sin/cos` do mês de release** é trivial. Google Trends exigiria `pytrends` (rate-limit, frágil) — prioridade baixa, mas a **encoding cíclica do mês** é 10 linhas e testável já.

### 2.7. **Pre-market prediction (JP→EN)**
Ele prevê preço de set EN antes do lançamento usando razão de preços JP/EN + multiplicador de set especial + curva de decaimento (~42% no Mês 1) + pull rates.

**→ Oportunidade média**: nosso cache cobre só o mercado EN (sets japoneses têm `ptcgoCode=None`, mas são 34 sets sem código — provavelmente promos, não os sets JP completos). Sem dados JP no cache, **não dá para implementar agora**. Porém, a **curva de decaimento pós-release** dá para modelar com o que temos: `card_age_years` + interação com `release_year` recente.

### 2.8. **Modelagem por cluster** (insight de engenharia dele)
Ele descobriu na prática que **não dá para um modelo único cobrir tudo**: "você precisa fazer clustering primeiro e modelar em cima dos clusters — vários modelos trabalhando simultaneamente".

**→ Oportunidade alta**: é exatamente o nosso problema! Nosso R² USD 0.289 com um CatBoost único esconde realidades heterogêneas:
- Cartas antigas (WOTC 1999–2003): preços dominados por raridade histórica/pop.
- Cartas modernas 2014–2026: dominadas por pull cost, arte, meta.
- Nossos erros grosseiros (ex: Shining Charizard R$32.863 real vs. pred R$31) sugerem que **clusters por era/raridade + modelos especializados** melhorariam muito o ajuste.

---

## 3. Oportunidades priorizadas (roteiro de experimentos)

| # | Oportunidade | Esforço | Impacto esperado | Dados necessários | Origem |
|---|---|---|---|---|---|
| **E1** | **Pull Cost + rarity_pool_size** como features (supply) | Baixo (1–2h) | Alto: captura a variável #1 do modelo dele | Cache atual (contagem por set×raridade) | T3, T7, T13 |
| **E2** | **Character Premium real** (agregação de preço médio por pokedex, normalizado por era) | Baixo | Alto: demanda de verdade, substitui/refina `pokemon_popularity` heurístico | Cache atual | T7, T13, T18 |
| **E3** | **Preço normalizado multi-fonte + flag de anomalia** (guardrails) | Médio (3–4h) | Alto: melhora target e escoragem (menos falsos "subvalorizada") | Cache + Liga p1b + cardmarket (já temos tudo) | T6, T11 |
| **E4** | **Modelos por cluster** (era × raridade) em vez de 1 CatBoost único | Médio | Alto: ataca o erro estrutural (WOTC vs. moderno) | Cache atual | T8, T18 |
| **E5** | **Features de liquidez temporal** (ΔiCO, Δpreço 7d/30d a partir dos snapshots acumulados) | Médio | Médio: sinal de momentum/leading indicator | Snapshots semanais (já acumulando) | T5, T8, T9 |
| **E6** | **Sazonalidade cíclica** (sin/cos do mês) + interação com card_age | Baixo (30 min) | Médio: captura summer slump | Cache (release date) | T14, T19 |
| **E7** | **PSA pop / gem rate / grading intensity** | Alto (fonte externa nova) | Alto: maior multiplicador do mercado moderno | PSA pop reports / gemrate | T1, T13, T15 |
| **E8** | **EV de abertura de pacotes (ROV)** por set | Médio-Alto | Médio: rank de "set vale abrir?" — exige pull rates reais | Pull rates públicos + pack price | T1, T2, T4 |
| E9 | JP→EN pre-market | Alto (sem dados JP no cache) | Médio | Sets JP (fonte nova) | T3 |

---

## 4. Detalhamento dos experimentos prioritários

### E1 — Pull Cost & rarity_pool_size (supply)
```python
# Por set: quantas cartas competem em cada slot de raridade?
pool = df.groupby(['set_id', 'rarity_tcg']).size()   # já temos tudo no cache
# pull_cost ≈ pack_price / pull_rate_odds × pool_size
#   pull_rate_odds ≈ 1/pool_size (fallback) OU tabela pública por era
```
- **Como testar**: adicionar 2 features (`rarity_pool_size`, `pull_cost_log`), retreinar, comparar R²/MAE vs. baseline. Esperado: melhora em cartas modernas (2020+) onde o pool de SIR/IR domina o preço.
- **Armadilha conhecida**: vazar informação do set inteiro para a carta (usar só features agregadas por raridade, não por carta).

### E2 — Character Premium real (demand)
```python
# Preço médio histórico por espécie, normalizado por era
prem = df.groupby('pokedex_number')['target_price'].median()
prem_era = df.groupby(['pokedex_number', 'release_year_decade'])['target_price'].median()
character_premium = prem_era / mediana_do_ano
```
- Substitui ou complementa `pokemon_popularity` (que hoje é contagem × gen × lendário).
- **Como testar**: A/B — modelo com `pokemon_popularity` vs. com `character_premium` vs. ambos; medir importância (feature importance CatBoost) e R² no split temporal.
- **Bônus**: derivar `artist_premium` do mesmo jeito (agregar por `illustrator` — temos artista em 19.202 cartas!). O Youtuber cita o "Artista Clout" do Magikarp do Shinji Kanda como anomalia que o modelo não pega — nosso `illustrator` já é feature, mas **categórico cru**; um score numérico agregado por artista seria mais forte.

### E3 — Preço normalizado multi-fonte + guardrail (target de qualidade)
- Hoje o `target_price` vem só do `tcgplayer.market` da pokemontcg.io (vulnerável a 1–4 vendas/dia, como ele demonstrou).
- **Proposta**: `target_price_limpo` = média ponderada de `tcgplayer.market`, `cardmarket.avg30 × câmbio EUR/USD`, `liga.p1b / câmbio`; se fontes divergirem > 50% OU `iCO==0` E cardmarket sem dados → flag `anomalia_preco=1` (excluir do treino ou dar peso menor).
- **Como testar**: retreinar com target limpo; medir se MAE cai e se a escoragem gera menos falsos positivos.
- Isso também alimenta o **watchlist/alertas**: "preço anômalo (4 vendas)" vs. "preço confirmado (30+ vendas)".

### E4 — Modelos por cluster (era × raridade)
- Clusters sugeridos: (1) WOTC 1999–2003, (2) 2004–2013, (3) 2014–2020, (4) 2021+ comum/rare, (5) 2021+ SIR/UR/secret, (6) Treinadores/supporter.
- Treinar 1 CatBoost por cluster + manter o global como fallback para cartas sem cluster.
- **Como testar**: comparar MAE por cluster do modelo único vs. especializado. Esperado: o maior ganho em cartas antigas (hoje nosso modelo erra feio em WOTC holo) e em SIRs modernas.
- Também ataca o problema BRL: hoje R² 0.04 — cluster BRL por faixa de preço (comum vs. cara) pode ajudar.

### E5 — Liquidez temporal (snapshots acumulados)
- Os snapshots semanais (`data/liga/snapshots/liga_snapshot_*.json`) já têm 3 execuções. A cada semana, calcular por carta:
  - `delta_ico_7d` (oferta subindo = cooling)
  - `delta_preco_7d` (momento)
  - `demand_pressure_aprox` = (preço subiu + iCO caiu) → sinal de tightening
- **Como testar**: feature engineering sobre a série temporal; depois validar se `delta_ico_7d` prediz direção de preço (correlação/backtest simples antes de entrar no modelo).

---

## 5. O que NÃO fazer (filtros do nosso contexto)

- ❌ **Plataforma/website** (leaderboards, watchlists, dark mode, planos pagos) — fora do escopo declarado.
- ❌ **Scraping de eBay em tempo real** por enquanto — alto custo operacional (anti-bot, Cloudflare); usar snapshots da Liga como proxy (E5).
- ❌ **Google Trends** (pytrends) como prioridade inicial — frágil e rate-limitado; a encoding cíclica (E6) cobre o essencial da sazonalidade.
- ⚠️ **E8 (EV de ripping)** e **E9 (JP→EN)** dependem de dados que não temos (pull rates oficiais, sets JP) — deixar para depois.

---

## 6. Ordem recomendada de execução

1. **E6** (30 min) — sazonalidade cíclica: ganho imediato trivial.
2. **E1 + E2** (meio dia) — as duas features mais importantes do modelo dele, 100% deriváveis do nosso cache.
3. **E3** (1 dia) — target limpo multi-fonte: melhora tudo que vem depois (retreinos).
4. **E4** (1 dia) — modelos por cluster: maior ganho estrutural esperado.
5. **E5** (contínuo) — alimentar com os snapshots que já acumulam; feature de momentum.
6. **E7** (semanas) — PSA/grading: única fonte externa nova, maior recompensa de longo prazo.

---

## 7. Métricas de sucesso (como medir cada experimento)

| Experimento | Métrica |
|---|---|
| E1, E2, E4 | ΔR² e ΔMAE no split temporal (teste = 20% mais recentes) vs. baseline atual (R² 0.289 / MAE $5.61 USD) |
| E3 | % de cartas com flag de anomalia; ΔMAE com target limpo; redução de falsos "🔥 subvalorizada" na escoragem |
| E5 | Correlação entre ΔiCO/Δpreço 7d e direção futura do preço (backtest simples) |
| E7 | ΔR² em cartas modernas com dados PSA vs. sem |
| Global | Manter Acc do classificador de bins ≥ 85% enquanto R² sobe (não trocar regressão por classificação) |
