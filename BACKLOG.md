# PokeScan TCG — Backlog

Centraliza melhorias, bugs e ideias **pendentes**. Prioridade: P0 (crítico) → P1 (alto) → P2 (médio) → P3 (baixo/ideia).

> ✅ **Resolvidos não ficam aqui** — migram para [`FEATURES.md`](FEATURES.md) (lista de features desenvolvidas). Regra do projeto desde 07/08/2026.

---

## 🚀 P1 — Próxima feature

> **Vazio** — P1.35 e P1.36 resolvidos/descartados em 02/09. Próximo candidato: P2.32 matching (embedding fraco/segmentação).

### [P1] 36. ~~Link `/card?card_id=...` retorna 404~~ → NÃO-BUG (descartado)
- **Verificado (02/09)**: a rota `/card/?card_id={idE}-{lang}-{num}` **funciona** — `411-en-4` (Charmander), `298-en-13` (Ninetales), `71-en-60`, `722-en-109` abrem. O formato canônico do `card_id` é `{idE}-{lang}-{num}` (base `71-en-60`), não `base1-4`.
- **Falso-positivo**: o teste de integração original usava `card_id=base1-4` (formato do ID do scanner), que é errado para a rota `/card`. Nenhum código do produto gera `card_id` nesse formato (o `ScoredCardRow` usa `card.card_id` = `{idE}-{lang}-{num}`).
- Teste atualizado p/ cobrir a rota canônica (`--card-id-canonic`); **9/9 checks** no site publicado.
- Tags: frontend, rota, não-bug, teste-integracao

---

## 💡 P2 — Melhorias de produto

### [P2] 32. Scanner matching: sinal independente p/ fechar gap até teto top-5
- **Estado (02/09 — indexação RESOLVIDA)**: diagnosticado que 17.296 cartas do catálogo da Liga NÃO estavam no índice (só 20.741 de 31.281). `build_search_index` agora anexa todas as cartas da Liga fora do índice (imagem `img_liga` baixada por `script/baixar_imagens_liga.py`); índice reconstruído 20.741→**37.679** (+16.938). Self-match das novas validadas (~0.97-0.99 @top1=id); deploy publicado. Commit `1de0650` + deploy.
- **Limite conhecido**: `Lílian`, `Pikachu do Ash`, `Sistema de Pressão Baixa`, `Energia Misturada` NÃO existem no catálogo Liga (ausência de dados, não de índice).
- **Resta (matching)**: ORB descartado (26/08) — o gap ao teto está em cartas fora do top-5 por **embedding fraco** (Team Aqua/Magma ~0.49-0.68, Juiz, Vileplume = cosseno baixo) e **segmentação** (cartas não detectadas). Próximos passos: augmentação do índice p/ as cartas com cosseno baixo; melhorar segmentação p/ recuperar cartas não detectadas.
- **Evidência** (base rotulada manual, `docs/AVALIACAO_LABELS.md`): acerto@1 = 74%, teto top-5 = 83% (~9pp recuperáveis). Re-rank com sinais leves + CatBoost LOFO foi NEGATIVO (−0,8pp, `0901db4`).
- Tags: scanner, matching, cv, indexação

### [P2] 49. Mapeamento sigla↔set inglês: **100% correto e monitorado** (nunca errado em silêncio)
- **Regra do Bruno (30/09)**: o mapeamento tem de estar **100% a todo momento** — `en_id` errado contamina página da carta, preço, hits e índice do scanner. Vale mais ficar liga_only do que casar errado.
- **Estado (28/09)**: 411 edições novas ingeridas; liga_only chegou a 43.774. **Aliases entregues**: 21 edições da Liga que são o mesmo set EN foram casadas (`liga_siglas_alias.json`), **join 17.082 → 20.564** e **liga_only 43.774 → 40.340**; índice do scanner caiu de 63.082 → **56.873** (−6,2 mil duplicatas). Commit `0d6635a`.
- **Diagnóstico corrigido (importante)**: o comparador de nome+número **funciona** (LOR casa 171/217 com `swsh11`). Os dois defeitos reais eram: (a) eu escolher o candidato errado quando dois sets compartilham o `ptcgoCode` (peguei o subset TG de 30 cartas em vez do set de 217); (b) o arquivo 1:1 não comportar duas edições da Liga para o mesmo set EN.
- **Critério do alias** (2 sinais + cobertura): `ptcgoCode` + sobreposição real ≥10 cartas e ≥70% das cartas da edição. O limiar frouxo (25%) aliasava **sets de reimpressão** (TOT24 → `sv6`), que casam com a origem por construção — 70% os recusa corretamente.
- **PENDENTE (o "100%" ainda não está garantido)**:
  1. **join exige nome?** O join casa por **número**, sem exigir o nome: nas edições com cobertura <100% (LOR = 79%) as cartas restantes entram com `en_id` possivelmente errado. Apertar para exigir nome (conservador) ou investigar caso a caso.
  2. **auditoria contínua**: rodar a auditoria no ciclo da macro e **alertar** se aparecer edição nova sem mapeamento, par ambíguo ou divergência de `ptcgoCode` — é isso que sustenta "100% a todo momento".
  3. **451 edições abaixo do limiar** a triar (a maioria é JP/CN/promo legítimo; incluir os casos JP no P3.17).
  4. **`xy6 → SV3`** e outras entradas divergentes do `ptcgoCode` a revisar uma a uma.
- Tags: catalogo, liga, mapeamento, indice, en_id

### [P2] 50. Próximas coleções: prospecção → gap de mapeamento (fechar antes de aparecer no crawl)
- **Estado (28/09)**: base criada em `data/liga/proximas_colecoes.json` (nome EN, nome pt-BR, código, sigla/idE da Liga, contraparte JP, lançamentos EN/BR/JP, tipo, capa, principais, status, fontes) + rotina semanal `proximas-colecoes-pokemon` (sábado 20:00, job `a90b63242a5f`, com regra de só afirmar o que tem URL).
- **Resta**: `discover_set_ids` **não lê** esse arquivo ainda — hoje a prospecção grava e reporta, mas a sondagem automática da edição nova na Liga (pelo nome) não está plugada. É o que fecha o gap sem esperar a fronteira.
- Tags: catalogo, liga, cron, mapeamento

### [P2] 51. Sinal de lançamento no modelo (hype do Pokémon de capa)
- **Ideia (Bruno)**: a capa de uma coleção anunciada infla cartas **já existentes** daquele Pokémon só por expectativa, e o efeito tende a recuar depois do lançamento. Ex.: **Reinado Delta (Delta Reign, ME06, 06/11/2026, capa Mega Rayquaza ex)** → Rayquaza antigos inflados antes, recuo depois.
- **Features propostas**: `hype_lancamento` (o Pokémon da carta é capa/principal de coleção anunciada?) + `dias_para_lancamento` + `dias_desde_lancamento` (o efeito não é permanente — o modelo precisa aprender a **subida e a volta**).
- **Experimento natural disponível**: a contraparte JP (**Storm Emeralda / M6**) **já está no catálogo** (idE 806, 113 cartas) desde 31/07/2026 → dá para medir Rayquaza antes/depois de 06/11/2026. Segundo caso: 30 Anos (Pikachu/Mew).
- Tags: modelo, temporal, lancamento, precos

### [P2] 52. EV por booster (página "preço por booster")
- **Decidido (24-25/09)**: régua = pacote **pt-BR de 6 cartas**; taxas do proxy EN escaladas **×0,6** (premissa de mesma estrutura de slots, declarada no site); regra de idade: **agregado só para coleção >6 meses**; saída em número quando medido, **faixa** quando não fixado. Documentado em `docs/metodologia-ev-booster.md`.
- **Nomes pt-BR das edições** gravados (`data/liga/nomes_edicoes_ptbr.json`): Celebração de 30 Anos (30C/30C-C/30THP/30C-R), Megaevolução — Heróis Excelsos (ASC), Escarlate e Violeta — Evoluções Prismáticas (PRE).
- **Resta**: a **tabela de raridades** (tiers do TCGplayer ↔ códigos `iR` da Liga) — sem ela a soma cai em balde errado. Depois: EV das Prismáticas (única com taxa medida ✓), 30 Anos (faixa), Heróis Excelsos (sem taxa publicada → piso ou estimativa por comparáveis declarada).
- Tags: ev, booster, precos, site

### [P2] 53. Harness de teste: servidor local single-thread gera falha falsa
- **Estado (28/09)**: a suíte local deu **19/38** com falhas espalhadas por todas as páginas (card, coleção, tendências, header) e **404 do `python -m http.server`** — que é **single-thread** e serializa 48 MB de índice + 15 MB de cards.json. O **mesmo teste contra o Pages passa 38/38**. Custo: horas caçando fantasma.
- **Resta**: servir o `out/` com servidor multi-thread (ou `ThreadingHTTPServer`) no harness, e registrar no teste a distinção local×publicado.
- Tags: testes, harness, infra

### [P3] 48. Filtro do pacote no scanner (proporção de carta)
- **Estado (23/09)**: no scan da foto do Trick or Trade, o **pacote** foi detectado como carta (razão de aspecto ≈0,56 cai dentro da janela aceita 0,45-0,95). Mexe em recall → **só mudar medindo na base rotulada** (lição do P3.34).
- Tags: scanner, segmentacao, cv

### [P2] 33. Base rotulada manual — continuar crescendo (retreinar re-rank no futuro)
- **Estado**: `C:/Projects/pokescan-tcg-labels` — 29 fotos/137 cartas rotuladas 100% manual (99% corretas). Harness completo pronto: `experiments/rerank_sinais.py` (gera dataset de pares) + `treinar_rerank.py` (CatBoost LOFO com folhas agrupadas).
- **Gatilho**: com ~3x a base atual, retreinar o re-rank — hoje não generaliza (dataset pequeno). Cada nova foto rotulada também melhora a avaliação de segmentação/matching.
- Tags: scanner, dados, rotulagem

### [P2] 45. Coleção: busca, filtros, ordenação e completude por set
- **Ideia**: com 50+ cartas a lista fica crua. Busca por nome, filtros (raw × graduada, com × sem preço, idioma, tipo) e ordenação (valor, upside, data, set). Agrupar por set com completude ("MEW: 34 de 165, faltam 131") e, opcionalmente, a lista de faltantes.
- **Base pronta**: `listarColecao`/`unidadesDe` (P2.43) e o preço por condição/tipo (P2.44) já dão o que filtrar.
- Tags: produto, coleção, frontend

### [P2] 46. Coleção: histórico do valor do acervo (snapshot + gráfico)
- **Ideia**: guardar um snapshot diário do valor da coleção (localStorage) e mostrar a evolução em gráfico ("R$ 8.200 em 01/09 → R$ 9.100 hoje"). É o gancho de retorno ao site.
- **Cuidado**: valor só do que tem referência; marcar claramente as unidades sem preço para o gráfico não mentir.
- Tags: produto, coleção, dados

---

## 🔬 P3 — Experimentos / ideias

### [P3] 49. Semanal: ~4h não explicadas no orçamento cheio
- **Estado (27/09)**: primeira execução da semanal (domingo 02:00) morreu no limite de 6h. Os passos conhecidos somam ~2h (descoberta ~30 min + snapshot dos 793 sets ~55 + enriquecedor 18 fixo + hits/escore ~10) → **~4h sem explicação**, e o script morto não deixou rastro (resumo final não é escrito).
- **Já feito**: heartbeat por passo **em arquivo** (`data/liga/macro_run.log`, commit `7b14c36`) — agora um script morto deixa o último passo registrado; orçamentos apertados (buracos 400→200); job movido para **sábado 22:00** (9h de folga, sem colidir com a diária das 07:00 — a colisão aconteceu de fato em 27/09: as duas rodaram juntas por ~1h).
- **Resta**: ler o log da execução de **03/10** e apontar o passo que estoura; depois limitar esse passo (não o job inteiro). Descartado como suspeito: o enriquecedor (fixo em 400 cartas/18 min).
- Tags: cron, macro, infra, orcamento

### [P3] 50. Cartas JP/CN recém-ingeridas mudam o peso do modelo JP
- **Estado (28/09)**: as 411 edições novas trouxeram ~40 mil cartas liga_only, em maioria **japonesas/chinesas** (MC 766, XYPJ 470, SMPJ 437, S4A 330, SV4A 360, S8B 293...). Isso **soma ao P3.17** (modelo dedicado a cartas JP + subsets): deixou de ser ideia e virou gargalo de qualidade do match — hoje o índice trata JP e EN com o mesmo embedding.
- Tags: modelo, jp, scanner, matching

### [P3] 34. Segmentação: binder com fundo preto perde a fileira inferior
- **Evidência**: foto `20260822_115216` (binder 9-pocket fundo preto, 3000x4000, 8 cartas) — Canny+Otsu globais acham 4-6 quads de 8; as perdidas ficam nas bordas (topo/fundo) contra o fundo escuro. Grade real detectável pelas costuras (vinil) = 3 col × 3 linhas. Overlays em `experiments/debug_crops/`.
- **Medido (26/08)**: diagnótico confirma grade 3x3; detecção por célula com grade FIXA 3x3 recupera 8/8 (baseline 6). Mas **portar ao browser por "busca por validação de todas as grades" (2x2..4x2) gerou FALSOS** — `detectCardQuads` passou a detectar 10 caixas em fotos de 8/9 cartas, e o matching confiável não melhorou (apareceram nomes errados). Protótipos em `experiments/{diag_grid,detectar_grid_binder,recall_deteccao_grid,matching_gain_grid}.py`.
- **Conclusão**: detectar a grade **por busca de todas as grades** é ruim no browser (super-detecta). **Rumo certo**: detectar a grade SÓ pelas COSTURAS robustas do binder (linhas escuras contínuas de vinil) e preencher apenas as células que ficaram vazias no passe global — nunca testar grades múltiplas. Medir de novo na base rotulada antes de portar (mesma lição do P2.32: validar matching real no browser, não só detecção offline).
- Tags: scanner, segmentação, cv

### [P3] 17. Modelo dedicado para cartas JP + subsets japoneses
- Hoje JP usa o modelo global EN via fallback (mapeamento de 62 siglas); usuário pediu modelo JP dedicado, mas sem features exclusivas decidiu-se pelo fallback.
- **Subsets JP (restante do P1.31)**: subsets japoneses da era SWSH têm correspondência EN APENAS PARCIAL (cov 30-70%) e numeração ≠ EN — mapeá-los a 1 set daria nome/número errado; hoje resolvem por fallback de NOME (mais correto). Reavaliar caso o projeto decida suportar os sets JP nativos.
- **Ideia futura**: coletar mais dados JP (histórico de preços da Liga) e treinar modelo separado.
- Tags: modelagem, JP, mapeamento

### [P3] 18. Embeddings: testar dinov2-large em produção
- Ablações: `large/cls+mean/pca32` teve R² 0.2948 vs `base` 0.2870 (+0.008); base foi integrado por custo/velocidade
- **Ideia**: rodar large quando GPU estiver ociosa e comparar em produção (A/B)
- Tags: modelagem, embeddings

### [P3] 19. Ensembling USD+BRL
- BRL usa USD como feature; **Ideia**: testar blend (média ponderada) ou stacked model
- Tags: modelagem

### [P3] 30.ext. Alerta de tendência + integrar previsão ao scanner (extensão do P1.30)
- P1.30 concluído (`/tendencias`, FEATURES). **Resta**: disparar alerta quando carta entra no top de subida prevista (relacionado ao P2.10 já feito); integrar a previsão ao scanner/similaridade (mostrar tendência no resultado de scan evitando cartas em queda).
- Tags: dados, TCGCSV, modelagem, produto

### [P3] 20. Alertas de cartas da coleção do usuário
- **Ideia**: usuário marca cartas que possui; o sistema avisa quando elas sobem/descem
- Tags: produto

### [P3] 21. App mobile / PWA
- Front é responsivo e acessível via rede local; **Ideia**: transformar em PWA (manifest + service worker) para instalar no celular
- Tags: frontend, produto

### [P3] 26. Alternativa jsfeat para o clipping (sem OpenCV.js)
- **Contexto**: Fase 1 do clipping implementada com OpenCV.js (`@techstark/opencv-js`, `/scanner/opencv.js` ~13 MB WASM embutido) em `app/lib/cardClip.ts` — Canny multi-passada + contorno + warpPerspective
- **Ideia (usuário)**: implementar tudo na mão com **jsfeat** (~150 KB, JS puro) para reduzir o download (~53 MB → ~40 MB) e eliminar a dependência do WASM
- **O que falta no jsfeat**: não tem `approxPolyDP`/`warpPerspective` nativos — precisaria implementar (Douglas-Peucker ~40 linhas; transform de perspectiva via math manual ou rasterização) — e validar razão de aspecto igual
- **Plano**: só se o download virar problema real (GitHub Pages/dados móveis); manter OpenCV.js como implementação canônica da Fase 1
- Tags: scanner, clipping, frontend, P3

### [P3] 44. Histórico de preços longo (6–12 meses) — série completa exige login
- **Estado (11/09)**: existe aba "Histórico de Preços" na página de carta e página dedicada `?view=cards/pricehistory`, com períodos de 1/3/6/12 meses e lista de vendas individuais — **só para usuário logado**; a página dedicada também cai em challenge anti-bot para browser automatizado (curl → 403; `web_extract` passa).
- **O que dá para consumir sem login** (feito no P2.42): resumo de vendas dos últimos **3 meses** (menor/média/maior + faixa de volume) e preço de venda por tipo (Normal/Foil).
- **Ideias**: avaliar conta de serviço própria para a série completa (checar termos de uso) **ou** manter só o link "Ver na Liga" para o histórico longo; o endpoint de vendas exige sessão.
- Referência: `references/liga-historico-precos-graduacao.md` (skill pokescan-tcg).
- Tags: dados, crawler, produto

### [P3] 45. Coleção: portabilidade — CSV, backup e link compartilhável
- **Contexto**: a coleção vive só em localStorage (some ao limpar o navegador). Hoje existe exportar/importar JSON.
- **Ideias**: exportar **CSV** (abre em planilha), lembrete/backup automático (com data do último), **link somente-leitura com a coleção comprimida em base64 na URL** (trocar lista com amigo sem backend) e, se um dia houver backend, sincronizar entre dispositivos.
- Tags: produto, coleção, dados

### [P3] 46. Coleção: foto e nota por unidade
- **Ideia**: anexar foto da carta real (IndexedDB, não localStorage) e nota livre por unidade ("comprada na loja X", "canto com defeito", "assinada"). Útil em venda/troca e para conferir o estado real.
- Tags: produto, coleção, frontend

### [P3] 47. Coleção: modo binder, edição em massa e conferência com o scanner
- **Ideias**: grade visual de imagens na ordem física do fichário; aplicar condição/tipo/idioma a N unidades de uma vez e duplicar unidade; adicionar em lote as cartas detectadas no scan, com um "modo conferência" (bater o binder físico contra a coleção).
- Tags: produto, coleção, scanner