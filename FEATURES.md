# PokeScan TCG — Features Desenvolvidas

Lista de features, correções e melhorias **entregues**. Itens resolvidos do
[`BACKLOG.md`](BACKLOG.md) migram para cá (regra do projeto desde 07/08/2026).

---

## Scanner & Clipping (100% browser)

| Feature | Commit / quando |
|---|---|
| **Scanner browser completo** — DINOv2-small uint8 (onnxruntime-web) + índice PCA128 fp16 de 20.426 cartas (recall@1 97.4%), sem servidor — superou P0.1 e P3.24 | Ago/2026 |
| **Clipping OpenCV.js (Fase 1)** — Canny multi-passada + contorno + warpPerspective; boxPoints manual (quebrado no OpenCV.js 5.0); calibrado 8/8 com fotos reais | `cfde707` + `e460486` |
| **Busca por texto no /scanner** (nome, número, coleção, raridade, id — top 10, debounce, sem precisar carregar o modelo) + **radio auto crop** (OpenCV ligado/desligado no pipeline) | `715edc0` |
| **Scanner multi-carta (Fase 1)** — detecta até 10 quadriláteros por foto, warpeia e identifica cada um; avisos "carta pequena" (<300px) e "não identificada" (<55%), alternativas e link /card | `15821f6` |
| **Fixes QA rodada 2+3** — BUG 1-4/obs 3-4 (rodada 2) + BUG 3 (rodada 3): upload após busca por texto escondia o scan (agora limpa a busca no onDrop) | `3c9dacf` + `90b14d6` |
| Fallback offline do scanner + badge de carta JP | `4f53558` |

## Site (export estático — GitHub Pages)

| Feature | Commit |
|---|---|
| **Export 100% estático sem backend** (tag `pre-static-export`) — todas as páginas em estático, dados via `build_static_data.py` → `public/data/*.json` | `87f186a` |
| Página /features (debug: predições + todas as features) | `b56162a` |
| Página /changelog (commits + ablações) | `f214b7f` |
| P0.2-P0.5: inflacionadas visíveis + build TS + cache por mtime + paths robustos | `44a2f3e` |
| Bug do link da Liga no /card (Mew ex MEW vs Celebrations) + mapping completo | `07b5679` |
| **Site responsivo (mobile)** — menu hambúrguer, tabelas com scroll, colunas compactas, sem overflow em 375/320px (9 páginas validadas) + `lang="pt-BR"` | `ff50441` |
| **Fixes do relatório de QA (11/08)** — html.unescape em nomes PT (BUG 1 alta), painel do /colecoes inline (BUG 2), aviso de janela antiga no 1º clique (Obs 3), números da landing reais (Obs 4) | `3c9dacf` |

## Modelo & Dados

| Feature | Commit |
|---|---|
| Embeddings DINOv2-base cls+mean PCA32 integrados (N_EMB=32) | `b2c9e1b` |
| Ablações de embeddings (large vs base) | `6b943bf` |
| ensure_embeddings incremental nos crons | `0e8a81b` |
| **Refresh incremental do cache ptcg** no cron semanal (30 dias, retry, backup) — P2.12 | `5b8d210` |
| Gênero de treinadores correto (dicionário explícito) — P1.7 | `8167f16` |
| Predição BRL no fluxo legado com `extra_features` — P1.8 | `8167f16` |
| **Mapping corrigido** (11 duplicatas → 1, 18 fantasmas removidos, me5→M5) — P2.15 | `8167f16` |
| **JP mapping** corrigido (0 alvos fantasmas; chaves UPPER) — P2.16 | `8167f16` |
| Limpeza de dados órfãos (83 embeddings + 83 imagens; lixo fora do git) — P2.14 | `d1a0065` (`script/limpar_orfao.py`) |
| **Preços TCGCSV como fonte primária (P1.28)** — target/price_type do TCGCSV (última semana, fallback cache; 17.919/20.479 cartas), mapeamento catálogo↔TCGCSV 91,7%, validado no A/B (R² 0.206→0.240, MAE $7.02→$6.73 no alvo real); cardmarket EUR e imagens continuam do pokemontcg.io | `4347fda` |
| **Features temporais TCGCSV no modelo BRL** — ret/4w/8w, momentum, spread por subtype (12 feats) via `script/tcgcsv_lib.py` + `script/tcgcsv_pricing.py`; safra 2026: erro 33,8% → **18,9%** (não há série BR própria ainda) | `4347fda` |
| **Histórico semanal TCGCSV no cron** — puxa a semana mais recente antes do retrain (`puxar_historico_semanal.py --semanas 1`); cron **liga-snapshot-diario** (06:30) acumula série BRL diária (5 snapshots úteis já) | `4347fda` |

## Identidade de carta (chave canônica)

| Feature | Commit |
|---|---|
| **card_id canônico `{idE}-{lang}-{sN}`** em todo o pipeline (índice `edicoes_liga.json` por overlap; corrige sv3→OBF, sv4→PAR, me1→MEG; set_map com sigla E edid; lookup com fallbacks) | `c9e7acf` |
| Linguagem JP por sufixo da sigla (PGOJP/EPJP/SVPJp) + nomes normalizados no lookup + modelo por card_id exato | `18acbf8` + `05e9512` |
| **Mesma carta em outros idiomas** — seção no /card com as versões JP/PT/EN (índice por nome EN normalizado: produtos da Liga + catálogo TCGAPI; chip do card atual marcado) | `801f6c4` |
| **Retrain automático no cron semanal** (P1.6) — `retrain_models.py` depois da escoragem + rebuild/deploy do site em seguida (`liga-snapshot.sh`) | cron 07:30 (fora do repo) |
| Limpeza: deps não usadas removidas (P3.22) + `crawl_tcgdex.py` removido (P3.23) + typos de prints já corrigidos (P3.25) | `f9f23af` |

## Coleções & EV do booster

| Feature | Commit |
|---|---|
| **EV do booster por coleção** (/colecoes) — pull rates ThePriceDex/TCGPlayer ×6/11, preços da Liga por edição, slider de custo, badge de cobertura | `3fd2e43` + `6d438a7` |
| **Sets de Megaevolução (me1-me5)** + filtro de ano de lançamento no /colecoes | `934882b` |
| Preço USD movido para a seção "Previsão do Modelo" + links da Liga em nova aba — P2.17 | `18acbf8` |

## Dashboard & Análise

| Feature | Commit |
|---|---|
| **Dashboard ampliado** — evolução de oportunidades por dia (SVG), top 10 sets por upside médio, distribuição de iCO — P2.13 | `23ca399` |
| Nome do set no /snapshot — P2.9 | `6ca38e0` |
| Histórico de preços por carta (gráfico SVG real vs predito) — P2.11 | `6ca38e0` |
| **Explicabilidade (P3.27)** — importance por grupo (Cardmarket 68%/USD, iCO no BRL) + SHAP values por carta na página /features (top-4 features em R$/$ com barras) — P3.27 | `2d78238` + `6690db8` |

---

## Em aberto no backlog

Ver [`BACKLOG.md`](BACKLOG.md): P1.29 (modelo de previsão temporal USD),
P2.10 (alertas Telegram), P2.29 (calibrar threshold multi-carta),
P3.17-23, P3.25-27 (incl. explicabilidade via SHAP — P3.27), P3.30
(multi-carta Fase 2).
