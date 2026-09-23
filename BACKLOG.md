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

### [P2] 49. Mapeamento sigla↔set inglês: corrigir entradas erradas e casar edições EN
- **Estado (23/09)**: ao ingerir as 411 edições que faltavam na Liga, **43.774 cartas ficaram liga_only**. O grosso é legítimo (JP/chinês/promos sem par em inglês: MC 766, XYPJ 470, SMPJ 437, S4A 330, SV4A 360...). Mas parte são edições **inglesas** hospedadas na Liga (ex.: ROS = 112 cartas) que deveriam **casar** com o set EN e hoje não casam.
- **Causa**: `data/liga/liga_set_sigla_ptcg.json` tem entradas erradas/legadas (ex.: `xy6` → `SV3`, quando o cache do pokemontcg.io diz `ptcgoCode=ROS` para xy6). O `rebuild_set_mapping.py` casa por nome+número (heurística, limiar 4) e **não sobrescreve** entrada existente.
- **Resta**: passe de auditoria no mapping (comparar `ptcgoCode` do cache com a sigla mapeada, listar divergências), decidir o que sobrescrever, re-rodar catálogo + índice. Efeito: menos arte duplicada no índice do scanner (menos ambiguidade no match).
- Tags: catalogo, liga, mapeamento, indice

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