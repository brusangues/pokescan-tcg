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
| **Alertas de oportunidade no Telegram (P2.10)** — cron dedicado `alertas-oportunidade-pokemon` (diário 07:05) dispara só quando cartas do CSV escorado cruzam upside ≥50% E iCO ≥3, com link do `/card`. Padrão watchdog (`no_agent`): stdout vazio + exit 0 = silêncio quando nada cruza. `script/alertas_oportunidade.py` lê o `scored_*_latest` (leve, sem re-escravar). Testado: hits 24, snapshot 136, silêncio OK | `56bb0b5` |
| **Previsão temporal no card detail (P1.29)** — modelo CatBoost prediz o preço USD da próxima semana (MAPE 5,0% no holdout; estáticas + 12 temporais TCGCSV); exibido como "Previsão — próxima semana" com badge ▲/▼ de tendência; treinado no retrain automático | `6ec7538` |
| **Ranking de tendência da próxima semana (P1.30)** — página `/tendencias` com top 25 subidas ▲ (verde) e quedas ▼ (vermelho); preço atual riscado → previsto; faixa [$2,$150] exclui preços-lixo e Gold Stars $1000+ (tendência = ruído); USD, nunca mistura moedas; mapeamento validado 0 erro em 50 cartas | `7b2bc03` |
| **Threshold multi-carta calibrado (P2.29)** — base rotulada da QA (9 fotos, `qa/base_rotulada.json`) × resultado real do scanner: 18 TP concordantes 56.7–81.0 / 38 NA 33.4–55.0 → **THRESH 0.50** (decisão: capturar mais, aceitando FP). Nota: foto_02 revela limitação de DETECÇÃO (perde 2 cartas), não de limiar | `1bc83aa` |
| **Scanner multi-carta Fase 2 (P3.30)** — (B) segmentação por fundo (threshold Otsu) somada ao Canny no `detectCardQuads` (só soma candidatos, validação sem regressão: 1 carta 1/1, multi-carta 58→59); (D) crop MANUAL (desenhar retângulo p/ escanear carta perdida) + botão ✕ p/ remover detecção. YOLO descartado | `9181aa9` |
| **Auditoria de dados: set-mapping completo (P1.31)** — 14 sets 1:1 re-mapeados ao set EN correto por nomes distintivos (`experiments/revisar_setmap.py`): 405 SV3→sv3, 771 M4→me4, 398 Pt1→pl1, 658 MIFO→ex12, 335 s5R→swsh5, 386 BW6b→bw7, 662 GSSO→ex10, 643 GM25→swsh45sv, 711 CS4AC→swsh7, 712 CS4BC→swsh8, 746 CS6AC→swsh12pt5, 357 CP4→xy4, 303 GHDPt→pl1, 537 SD→swsh1. Subsets japoneses (s5a/s6*) ficam por fallback de nome (mapear daria numeração errada) | `31892d4` |
| **Auditoria de dados: moedas separadas** — ranking subvalorizadas/inflacionadas do snapshot deixou de misturar US$ e R$ (cartas só-USD vão a listas próprias com aviso no /snapshot) | `31892d4` |
| **Coleções pt-BR da LIGA no scanner (fonte primária pt-BR)** — `build_search_index.py` lê coleções pt-BR via `data/liga/ptbr_edicoes.json` (nomes `nPT`, números `sN` de `set_{idE}.json`). "Parceiro Inicial" (MEP/733 + MEPR/732) = **263 cartas pt-BR** no índice (IDs `733-N`). Domínio de imagem descoberto (`repositorio.sbrauble.com`); `crawler/baixar_imagens_ptbr.py` baixa conforme a mask. Curadoria: das 197 edições da Liga sem EN, só MEP/MEPR são pt-BR verdadeiras; o resto é subset JP/chino (/CS*)/promo JP → NÃO entra (fica por fallback). | `0f62488`,`978ccc7` |
| **Catálogo consolidado Liga-first (Fase 2.2)** — `script/build_catalogo_liga.py` gera `data/catalogo_liga.json`: 31.281 cartas da LIGA (chave `{idE}-{num}`), LEFT JOIN EN (imagem/nome/preço USD) → 13.774 mapeadas (44%) + 17.507 liga_only. Artefato canônico p/ site/scanner/modelos. | `fb8d694` |
| **Site consome o catálogo da Liga (Fase 2.3)** — `cards_basico` anexa MEP/MEPR ao `cards.json` do site (+299 pt-BR c/ preço BRL e imagem da Liga); TAG `migracao-liga-inicio` marca o início da migração (`12d21a1`). | `7842750` |
| **Scanner: avaliação contra base rotulada MANUAL + calibrações** — base `pokescan-tcg-labels` (137 cartas 100% manuais): detecção 117≈115; matching 62%→74% acerto@1 (teto top-5 83%); pct NÃO discrimina (THRESH mantido 0.40). **(1)** Fix score>100%: clamp [0,1]+guard NaN/Inf no `scannerEngine.search` (query corrompido de crop degenerado — índice verificado normalizado). **(2)** Re-rank por MARGEM top1−top2: `ScanResult.margin`; MARGEM_MIN=3pp → match ambíguo vira "⚠ Incerto" em vez de verde confiante (elimina ~73% dos falsos confiantes mantendo ~75% dos acertos). **(3)** Segmentação ADAPTATIVA: minArea .02 + 2º passe .008 se ≥4 quads (62%→64% sem regressão nas solitárias). Réplica Python fiel p/ debug visual: `debug_segmentacao.py` (+overlays em `experiments/debug_crops/`), `sweep_detecao.py`. Relatório: `docs/AVALIACAO_LABELS.md`. Loop de teste: dev tem bug de hidratação (`output:export`+`next dev`) → usar build estático Node20 + http.server. | `c4b237f`,`0334c09`,`20f481f` |
| **Re-rank aprendido: estudado e NEGATIVO (não integrar)** — sinais leves (centro-zoom, HSV, rank, margens) + CatBoost LOFO (folhas agrupadas) sobre 615 pares: 73,2% vs 74,0% baseline (−0,8pp) — só reaprende o cosseno. Teto top-5=83% exige sinal independente (ORB) ou mais labels. Dataset/harness ficam (`rerank_sinais.py`, `treinar_rerank.py`, `rerank_pares.json`). | `0901db4` |

## Frontend — tema & copia

| Feature | Commit |
|---|---|
| Tema A "Guia de colecionador" em todo o site (P2.34) + copy institucional (P2.38) — creme/papel, Baloo2+Nunito, pokébola, vermelho ação, sem indigo/roxo; "preço em reais", link "Ver na Liga" mantido | `d6954ed` |
| Scanner mobile abas Foto/Buscar (P2.35) + copy motor "Ativar motor de busca", MBs em `<details>` (P2.36) + seletor de dias do /hits em dropdown `‹ ›` | `b1f9c0d`,`ae042ae` |
| Hero do scanner "Escaneie ou busque pelo nome" (P3.37) | `b1f9c0d` |
| **Nome pt-BR da Liga nas cartas (P1.33)** — `cards_basico` anexa nPT/nEN via en_id do catálogo (13.728 cartas/66%); `cardLookup` prioriza nPT; EN vira secundário na /card. Ex.: Brás, Professor Carvalho Impostor | `72c9b47` |
| **Busca multicritério no scanner (P1.34)** — consulta vira tokens; cada token casa com QUALQUER campo (nome, nome pt-BR /nPT, set, número, id, raridade); carta só entra se TODOS os tokens casam. Ex.: "gengar stormfront" → Gengar do Stormfront; "charizard 201" → Reshiram & Charizard-GX; "carvalho" → Professor Carvalho/Impostor | `d148df1` |
| **Fallback completo cartas EN-only (P2.41)** — cartas sem presença direta na Liga (ex. `smp-SM108` Ash's Pikachu, base2, promos) ganham predição BRL do modelo (features usd/rar/types derivadas do cache EN; 6.729 cartas cobertas) + link de **busca na Liga por nome** (não link direto, pois não há sigla/edição correta). Fix `parseInt('SM108')=NaN` que quebrava promos alfanuméricas | `35e9ed5` |

## Liga-first — Fase 3 (modelos)


| Feature | Commit / quando |
|---|---|
| **Modelo BRL LIGA-FIRST (P1.32)** — A/B head-to-head aprovado nas mesmas 2603 cartas do holdout: MAE R$39,16→**R$22,77** (−42%), R² 0,162→**0,611**, erroRelMed 44,8%→**25,4%**, grails 59,5%→26% (`fase3_ab_head2head.py`; TAG `pre-liga-first-brl`). `script/brl_liga.py`: CatBoost treinado NO catálogo da Liga (23.295 cartas c/ p1b>0; features iR/iCO/sigla/rar/types; USD como feature via join). Integração: `predict_base` sobrepõe pred_brl onde cobre (**55%** da base; resto mantém modelo atual) — snapshot: Inflacionadas 6047→4605, Preço Justo 3311→4225. Plots real-vs-predito em `experiments/plots/`. | `ce77b86`,`630e848`,`cb92ecb` |
| **Fix /card: registro escorado por NOME prioriza o SET da página** — `?set=me3&num=50&nome=Gengar` mostrava preço do hit PPPS3 #66 em vez da linha POR #50 (sort só bônusava sigla da URL). Bônus +9 quando `setMap[sigla_registro] == card.s`. Auditoria (`audita_scored_fallback.py`): 7.319 páginas corrigidas. | `66b5dfc` |
| **Guard anti-homônimo + fallback Liga-first na /card** — sem candidato do próprio set no snapshot, NÃO empresta preço de homônimo (bloco oculto; 7.463 páginas deixavam de mostrar dado errado). Em seguida, fallback com `pred_liga.json` (31.267 chaves `{idE}-{num}` + 13.750 alias EN; gerado por `script/gera_pred_liga.py`): bloco "Previsão do Modelo" com Fonte "Modelo Liga-first (Fase 3)" para ~1.653 páginas antes sem nada. Fix promise-cache no loader. E2E: Blastoise bw10 ✓, Gengar POR ✓, base2 (fora da Liga) sem bloco ✓. | `d3da68c`,`622f2d1` |

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
