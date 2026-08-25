# Liga Pokémon como fonte primária — Plano de inversão do cruzamento de dados

> **Para Hermes:** implementar task-a-task (ver skill `plan`/`subagent-driven-development`).

**Goal:** Inverter o pipeline de dados do PokeScan TCG para que a **Liga Pokémon** seja a fonte primária (driver) de todo o catálogo — cartas, edições, nomes pt-BR, numeração e preços BRL — e que pokemontcg.io + TCGCSV entrem como **LEFT JOIN** (enriquecer imagem, preço USD/EUR e features temporais) apenas onde houver correspondência. Re-alinhar chave e mapeamentos.

**Arquitetura:** Hoje o catálogo nasce do pokemontcg (EN) e a Liga é cruzada como complemento. Passa a nascer da **Liga** (todas as edições), com chave `{idE}-{lang}-{sN}` derivada DA LIGA, e as fontes EN/TCGCSV são um join enriquecedor. Coleções pt-BR exclusivas (ex. "Parceiro Inicial"/MEP) passam a ser capturadas pela própria Liga.

**Tech stack:** Python (json/pandas), crawler da Liga (crawler_liga_snapshot/hits), modelos CatBoost (BRL+USD), frontend Next.js estático.

---

## Status deste plano (atualizado 21/08, execução da frente "coleções pt-BR")

**Concluído (fonte = Liga):**
- Confirmado que a coleção "Parceiro Inicial" está na **Liga edição 733 (MEP)**, numeração `#037–#054`; mapeamento bate 18/18 com os nomes pt-BR da Liga.
- **Mecanismo**: `build_search_index.py` lê coleções pt-BR via `data/liga/ptbr_edicoes.json` (nomes `nPT`, números `sN` de `set_{idE}.json`), generalizável. A edição entra como `{idE}-{sN}` (ex `733-43`).
- **Imagens da Liga descobertas**: domínio `repositorio.sbrauble.com` (sP). `crawler/baixar_imagens_ptbr.py` baixa as imagens conforme a mask (`MEP_PT-BR_{num}.png`, `MEPR_PT-BR_{num}.png`). Baixadas 111 (MEP 733) + 152 (MEPR 732).
- **Curadoria das edições pt-BR concluída**: das 197 edições da Liga sem correspondência EN, após agrupar por numeração própria (`∞`/`/M-P`) + idioma + inspeção de nomes, **só MEP (733) e MEPR (732) são coleções pt-BR verdadeiras**. As ~195 restantes são subsets japoneses (`s5a`, `S9A`, `sm-*`), coleções chinesas (`CS*`) e promos/trainer japonesas (`MC` "da Érica", `VS`) — **decisão: NÃO entrar no catálogo pt-BR** (ficam por fallback de nome). Análise em `experiments/curadoria_ptbr.csv`.

**Frente "coleções pt-BR" CONCLUÍDA** (MEP + MEPR, 263 cartas no scanner via Liga).

**Fase 2.2 — Catálogo consolidado Liga-first: FEITO.** `script/build_catalogo_liga.py` gera `data/catalogo_liga.json` (31.281 cartas da LIGA; chave `{idE}-{num}`) com LEFT JOIN EN via `set_mapping`+número (imagem/nome/preço USD) → **13.774 mapeadas EN (44%)**, **17.507 liga_only (56%)** (pt-BR/JP, preço BRL). Sendo o artefato que o site/scanner/modelos passam a consumir.

**Fase 2.3 — Site consome o catálogo Liga (lookup pt-BR): FEITO.** `cards_basico` em `build_static_data.py` lê o `catalogo_liga.json` e anexa as coleções pt-BR verdadeiras (MEP/MEPR) ao `cards.json` do site com preço BRL + imagem (repositorio.sbrauble.com). `cards.json`: 20.478 EN + **299 pt-BR**.

**Fase 3 — Modelos BRL Liga-first: FEITO (25/08).** A/B head-to-head aprovado (`fase3_ab_head2head.py`, mesmas 2603 cartas do holdout): MAE R$39,16→R$22,77 (−42%), R² 0,162→0,611, erroRelMed 44,8%→25,4%. Integração: `script/brl_liga.py` (CatBoost no catálogo da Liga, 23.295 cartas; USD como feature) + `predict_base` sobrepõe `pred_brl` onde cobre (**55%** da base; resto mantém o modelo atual — sem risco de regressão fora da cobertura). Efeito real no snapshot: Inflacionadas 6047→4605, Preço Justo 3311→4225. TAG `pre-liga-first-brl` marca o estado anterior.

**Em andamento / pendente:**
- Inversão total (Liga dirigindo catálogo/modelos) segue as Fases 1–4.

---

## Contexto atual (levantado por auditoria — 21/08)

- **Card id atual:** `{idE}-{lang}-{sN}`, onde `idE` = edição da Liga, `sN` = número. Mas é DERIVADO do EN: em `score_apos_crawl.py` a base é o `ptcg_cards_cache.json` (pokemontcg EN), e `card_id` é montado resolvendo o set EN → `idE` via `liga_set_sigla`. **A chave é da Liga, mas o universo é dirigido pelo EN.**
- **Liga:** 31.273 linhas de cartas em `data/liga/set_*.json` (337 arquivos), **100% com `nEN`** (número EN); 335 edições em `edicoes_liga.json`; camp: `idE`, `idNC`, `nPT` (nome pt-BR), `sN` (número), `nEN`, `sSigla`, preços BRL (`precoMenor/Maior`, `p1a..c`), `iCO`, `sP` (imagem).
- **set_mapping.json:** 66 pares `{set_EN → sigla_Liga}` (ex. `me01→PGOJP`, `sm1→s8`).
- **Merge atual (EN base, Liga join):** `score_apos_crawl.py ~linha 205` faz `df_jp.merge(..., by nome+número)` contra a base EN.
- **Bug conceitual concretizado:** a coleção "Parceiro Inicial" (MEP) foi mapeada manualmente via pokemon.com/br como `MEP_PT-BR_37–54` (18 cartas). A **Liga** cataloga MEP/MEPR de forma diferente (**733**=Meganium/Inteleon/Alakazam+Staff; **732/MEPR**=Chikorita/Lapras/Munkidori) — evidenciou que a fonte usada foi a errada (EN/pokemon.com) e a nomenclatura pode estar desalinhada da Liga.

---

## Fase 0 — Auditoria completa (sem mudar nada)

- **0.1** Inventariar TODOS os pontos onde o catálogo nasce do EN e a Liga é o join:
  - `script/refresh_ptcg_cache.py`, `ptcg_io.py` (alimenta a base).
  - `script/score_apos_crawl.py` (merge), `pokemon_price_monitor.py` (modelos), `script/build_static_data.py` (site), `script/build_search_index.py` (scan), `script/tcgcsv_pricing.py` (USD), `script/score_sets_recentes.py`, `poke_embeddings.py`.
- **0.2** Medir o gap real (dimensionamento): quantas cartas da Liga têm imagem EN (pokemontcg) e quantas **não** (só-Liga, sem USD). Hipótese: `nEN` presente = 100%, mas a **imagem/preço** podem cobrir menos.
- **0.3** Documentar o formato do `card_id` histórico (snapshots antigos usam `liga_id 'CL-75'` e `card_id '25-en-75'`) p/ garantir compatibilidade de série temporal na migração.
- **Entregável:** relatório `experiments/auditar_ligasource.md` + tabela de cobertura (Liga×EN imagem/preço).

## Fase 1 — Nova chave canônica (Liga-first)

- **1.1** Definir o identificador primário: usar `idNC` quando >0, senão `{idE}-{sN}`. Campo `card_id` pasa a ser **sempre derivado da linha da Liga** (não do EN).
- **1.2** `nEN`/`nPT`/nome pt-BR viram **campos de informação** (join keys), nunca mais a chave.
- **1.3** Manter retrocompat: um mapa `{card_id_novo → card_id_antigo}` para a série temporal do histórico.
- **Teste:** para uma amostra, `card_id` novo bate com o da Liga e com o histórico.

## Fase 2 — Inverter o pipeline de dados

- **2.1** `script/gerar_edicoes_liga.py` passa a ser o **driver do catálogo**: itera todas as edições da Liga (não filtra por correspondência EN).
- **2.2** Novo `script/build_catalogo_liga.py`: monta o catálogo a partir de `set_*.json` (todas as edições) com chave `{idE}-{lang}-{sN}` + `idNC`.
- **2.3** LEFT JOIN enriquecedor:
  - Imagem + preço USD/EUR: pokemontcg EN, via `set_mapping` (set_EN→sigla) + `nEN` (número).
  - Preço USD temporal: TCGCSV (já em `tcgcsv_lib.py`), join similar.
  - Cartas **sem** correspondência EN: ficam no catálogo com preço BRL, imagem/pt-BR da própria Liga, e `price_type` marcado como `liga_only`.
- **2.4** `refresh_ptcg_cache.py` deixa de ser a base → vira "sincronizador" de enriquecimento (baixa imagem/preço EN para as cartas da Liga que mapeiam).
- **Teste:** catálogo resultante contém MEP/pt-BR; cada carta tem `card_id` da Liga; join só adiciona, nunca remove.

## Fase 3 — Modelos (BRL primário)

- **3.1** `pokemon_price_monitor.py`: base de treino passa a ser o catálogo da Liga (BRL alvo). USD continua como feature via join (só a coluna, não dirige a base).
- **3.2** Re-treinar e comparar (holdout) vs pipeline atual — migração só avança se não piorar o MAPE BRL (referência atual: safra 2026 ~18,9% com temporais).
- **Teste:** retrain + `score_apos_crawl --tipo snapshot` mantém/melhora métricas; cartas `liga_only` ganham predição BRL.

## Fase 4 — Scanner / índice

- **4.1** `script/build_search_index.py`: base = catálogo da Liga (não só EN). `cards.json` de busca reflete todas as cartas da Liga (inclui pt-BR/MEP) — sem precisar de `mep_extra.json` manual.
- **4.2** Validar na foto do usuário (6 parceiros iniciais) que identifica pela base da Liga.
- **Teste:** self-match 100% e recall nas `fotos_teste`.

## Fase 5 — Coleções pt-BR capturadas pela Liga

- **5.1** Deprecar `data/mep_cards/mep_extra.json`: as 18 e futuras "Parceiro Inicial" devem vir do crawler da **Liga** (edição certa). Alinhar a nomenclatura MEP detectada (733/MEPR note) com o que a Liga usa.
- **5.2** Verificar com o usuário qual a edição da Liga correta para a "Parceiro Inicial" e re-mapear com os nomes da Liga (não pokemon.com).
- **Teste:** coleção MEP identificada no scanner sem influxo manual.

## Fase 6 — Site / frontend

- **6.1** `script/build_static_data.py` + `cardLookup` do front: consumir o novo `cards.json`/catálogo da Liga (card_id já compatível).
- **6.2** Tela de cartas sem USD: mostrar preço BRL e sinalizar `liga_only`.
- **Teste:** `/collect` e `/card?` funcionam com o novo catálogo sem quebrar.

---

## Arquivos que mudam (mapeamento)

- `script/gerar_edicoes_liga.py` (driver do catálogo)
- `script/refresh_ptcg_cache.py` (redutor: sincronizador de enriquecimento)
- `script/score_apos_crawl.py` (merge invertido)
- `pokemon_price_monitor.py` (modelo: base Liga)
- `script/build_static_data.py` (site)
- `script/build_search_index.py` (scan: base Liga)
- `script/retrain_models.py`, `script/train_temporal_prod.py`, `script/prever_temporal.py`
- `script/tcgcsv_lib.py` / `tcgcsv_pricing.py` (join USD)
- `data/liga/set_mapping.json` (mapeamentos a corresponder)
- `ptcg_io.py`

## Validação / teste

- Teste de cobertura: catálogo da Liga ⊇ edições; join never remove.
- Recall do scanner (fotos_teste) e identificação da foto dos 6 "parceiros iniciais".
- MAPE BRL no holdout não piora (referência: 18,9% safra 2026).
- Histórico/snapshot antigo continua legível (mapa de chave).

## Riscos / tradeoffs / questões abertas

- **Risco de chave:** snapshots antigos usam `liga_id`/`card_id` diferentes → exige mapa de migração para não quebrar série BRL (17 snapshots desde 31/07).
- **Cartas só-Liga sem USD:** entram no BRL; faltam features USD → decidir backfill/ausência (não zerar preço).
- **Crawler da Liga é lento** (~raspagem pesada) → catálogo completo exige execução longa/incremental.
- **Abre:** qual exatamente o gap o usuário quer fechar primeiro? (a) cartas pt-BR exclusivas fora do EN, (b) preço BRL como primário, ou (c) modelo apenas BRL? Isso define a ordem das fases.
- **Abrir:** manter modelo/features USD em paralelo ou substituir por BRL-only?

---

**Próximo passo proposto:** rodar a Fase 0 (0.1–0.3) — auditoria objetiva do fluxo + dif da cobertura Liga×EN — e trazer o relatório antes de abrir a Fase 1.