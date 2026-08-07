# PokeScan TCG — Backlog

Centraliza melhorias, bugs e ideias pendentes. Prioridade: P0 (crítico) → P1 (alto) → P2 (médio) → P3 (baixo/idea).

---

## 🐛 P0 — Bugs / riscos ativos

### [P0] 1. Scanner limitado a 5 cartas do Base Set
- `frontend/app/components/Scanner.tsx` usa index fixo de 5 cartas (`base1`) com modelo vit-base no browser (Transformers.js)
- Agora temos **20.426 embeddings DINOv2-base (PCA32)** no servidor (`data/pokemon_embeddings_base32.csv`)
- **Ideia**: nova API `/api/search?embedding=...` que recebe o embedding da foto e retorna top-k por similaridade coseno contra a base completa; scanner passa a buscar na base inteira
- **Ganho**: de 5 para 20k cartas identificáveis
- Tags: frontend, embeddings, scanner

### [P0] 2. ⚠️ Typo "Inlacionada" faz as inflacionadas SUMIREM do frontend (auditoria 05/08)
- `script/score_apos_crawl.py` grava a categoria `💀 Inlacionada` (sem "f", 3 ocorrências: linhas ~393, ~415, ~435) mas TODOS os filtros do frontend buscam `💀 Inflacionada` (com "f"): `/api/hits`, `/api/snapshots`, `/api/dashboard`
- **Impacto real**: abas "💀 Evitar" de /hits e /snapshot ficam SEMPRE vazias; dashboard mostra inflacionadas=0. CSV do snapshot tem **3.454** cartas "Inlacionada" invisíveis; hits tem 172
- `script/score_sets_recentes.py` usa a string correta → inconsistência entre scripts
- **Fix**: normalizar a string no `score_apos_crawl.py` (ou aceitar ambas no frontend)
- Tags: backend, frontend, dados
- **Status**: ✅ corrigido em `44a2f3e`

### [P0] 3. Build de produção quebra: 5 erros de TypeScript (auditoria 05/08)
- `npx tsc --noEmit` acusa 5 erros → `next build` falha (dev tolera via HMR, produção não):
  - `app/api/card/route.ts(114)`: `key.startsWith` — key é `string | number` (Map do cache)
  - `app/card/CardDetailContent.tsx(313)`: `p.low` possibly undefined no preço TCGPlayer
  - `app/card/CardDetailContent.tsx(408)`: `'⚪'.repeat(card.retreatCost)` — retreatCost é `string[]` (array de custos), não número
  - `app/hits/page.tsx(113)` e `app/snapshot/page.tsx(141)`: `selectedFile` pode ser `null` no onClick
- **Fix**: correções pontuais de tipo (String(key), optional chaining, repeat com length, `?? undefined`)
- Tags: frontend, build
- **Status**: ✅ corrigido em `44a2f3e`

### [P0] 4. Cache de módulo do /api/card nunca é invalidado
- `_cacheMap` (ptcg_cards_cache.json) e `_scoredLatest` (CSVs escorados) são variáveis de módulo **sem invalidação**
- Em produção (long-running), o servidor NÃO vê: novos CSVs do cron das 07:00, cartas novas do refresh semanal, nem mudanças no mapping — só após restart
- **Fix**: cache com TTL (ex. 5 min) ou invalidação por mtime dos arquivos
- Tags: frontend, API
- **Status**: ✅ corrigido em `44a2f3e`

### [P0] 5. `process.cwd()` como base de paths nas APIs — frágil
- TODAS as rotas de API usam `join(process.cwd(), '..', 'data', ...)` para achar o repo
- Se o servidor subir de outro diretório (ex. `cd / && npm run dev --prefix ...`), **todas as APIs quebram** silenciosamente (404/500)
- **Fix**: usar caminho absoluto derivado de `__dirname` ou variável de ambiente
- Tags: frontend, API, robustez
- **Status**: ✅ corrigido em `44a2f3e`

---

## 🟡 P1 — Alto

### [P1] 6. Nenhum cron re-treina os modelos
- Refresh do cache ptcg roda semanalmente (adiciona sets novos como me5), mas os modelos USD/BRL só são re-treinados manualmente (`script/retrain_models.py`)
- **Ideia**: adicionar `retrain_models.py` ao cron semanal (depois do refresh, antes do snapshot) — ou rodar mensalmente
- Tags: backend, modelagem, crons
- **Status**: ✅ corrigido em 8167f16 (dicionário explícito TRAINER_GENDER)

### [P1] 7. `infer_trainer_gender` retorna gênero errado para vários treinadores
- `pokemon_price_monitor.py`: 'Hop', 'Bede', 'Nanu' aparecem nas listas masculina E feminina → a feminina ganha → retornam `female` (são masculinos)
- Vários outros (Misty, Sabrina, Erika, etc.) estão nas duas listas por redundância (feminina correta)
- **Fix**: remover duplicatas da lista masculina ou verificar masculino primeiro
- Tags: backend, features
- **Status**: ✅ corrigido em 8167f16 (extra_features target_price_usd)

### [P1] 8. `run_snapshot` do pm.py faz predição BRL com shape errado
- `pokemon_price_monitor.py:817`: `prepare_features(df_valid[brl_idx])` SEM `extra_features=['target_price_usd']` — mas o modelo BRL foi treinado COM essa feature
- Impacto: predição BRL falha ou diverge no fluxo legado (o fluxo de produção `score_apos_crawl.predict_base` está correto — só o `run_snapshot` legado está quebrado)
- **Fix**: passar `extra_features=['target_price_usd']` na linha 817
- Tags: backend, modelagem
- **Status**: ✅ corrigido em 8167f16 (extra_features target_price_usd)

---

## 💡 P2 — Melhorias de produto

### [P2] 9. Nome do set completo no `/snapshot`
- Tabela de hits mostra "sigla + nome do set" (`ed_sNome`); snapshot não tem `ed_sNome` no CSV → mostra só sigla
- **Ideia**: incluir `ed_sNome` no CSV do snapshot (crawler já tem o dado?) ou resolver via mapping no front
- Tags: frontend, snapshot
- **Status**: ✅ `finalizar` resolve `ed_sNome` via mapping inverso (sigla → ptcg → nome); 91% dos sets com nome (`6ca38e0`)

### [P2] 10. Alertas de oportunidade (Telegram)
- Crons já escoram e formatam top 10; **Ideia**: alerta dedicado quando uma carta cruza thresholds (ex. upside > +50% e iCO >= 3) — hoje é só na listagem
- Tags: crons, notificações

### [P2] 11. Histórico de preços por carta (time series)
- Temos snapshots semanais + hits diários acumulando; **Ideia**: gráfico de evolução de preço real vs predito por carta no `/card`
- Tags: frontend, dados
- **Status**: ✅ API `/api/historico` + componente `PriceHistory` (SVG puro) no `/card` — real vs predito, hits + snapshots (`6ca38e0`)

### [P2] 12. Cache de cartas ptcg desatualizado
- `data/ptcg_cards_cache.json` tem 20.479 cartas; sets novos (ex. sv8pt5 Prismatic Evolutions) foram adicionados manualmente no mapping mas o cache precisa refresh periódico
- **Ideia**: script de refresh incremental do cache (pokemontcg.io paginado) + rodar no cron mensal
- Tags: backend, dados
- **Status**: ✅ `script/refresh_ptcg_cache.py` integrado ao liga-snapshot.sh (antes do crawler) — incremental (30 dias), retry anti-rate-limit, backup automático (`5b8d210`)

### [P2] 13. Dashboard com mais métricas
- `/dashboard` tem métricas agregadas; **Ideia**: adicionar evolução temporal de oportunidades (subvalorizadas por dia), top sets por upside médio, distribuição de iCO
- Tags: frontend, dashboard

### [P2] 14. Limpar dados órfãos e duplicatas (auditoria 05/08)
- **83 embeddings + 83 imagens órfãs** no cache (cartas que saíram do ptcg_cards_cache — ex. ids renomeados); 53 cartas do cache sem imagem/embedding (IDs especiais sem URL)
- `data/liga/cache_enrich/cache_enrich_YYYYMMDD.json` versionado no git (lixo transitório do crawler que acumula diariamente)
- `fetch_result.json` na raiz (2 cartas, obsoleto) vs `frontend/public/fetch_result.json` (29 cartas, atual) — duplicata stale versionada
- `pokéscan-tcg.zip` ainda rastreado no git (marcado D no working tree, commit pendente)
- **Fix**: script de limpeza (prune órfãos + git rm dos lixos) rodando no cron ou manual

### [P2] 17. Links para a Liga abrirem em nova aba + preço USD na seção do modelo
- **Pedido do usuário (07/08)**: todos os links externos para a Liga Pokémon devem abrir em **nova aba** (`target="_blank" rel="noopener noreferrer"`) — verificado: já é o caso nos 2 lugares (ScoredCardRow, CardDetailContent); manter o padrão em links novos
- **Pedido do usuário (07/08)**: o preço de mercado em **dólares** (TCGPlayer/Cardmarket) não deve ficar no topo da página de carta — mover para a seção "Previsão do Modelo" junto dos outros preços. **Status**: ✅ removido do bloco da imagem; agora é a linha "Mercado global (USD)" na seção do modelo (CardDetailContent)
- Tags: dados, repo, manutenção

### [P2] 15. Mapping: 11 siglas Liga duplicadas + 25 sets sem mapping (auditoria 05/08)
- 11 siglas Liga com 2 sets ptcg mapeados (EX: SV3A←sv3+sv3a, SV4A←sv4+sv4a, UF←ex10+exu, PR←4 sets...) → colisão de `liga_id` (cartas de sets diferentes viram o mesmo id na escoragem)
- 25 sets ptcg sem sigla Liga (incl. **me5** que o refresh adicionou ao cache — precisa mapear)
- **Fix**: revisar duplicatas (qual set ptcg é o "oficial" de cada sigla); me5 → descobrir sigla na Liga
- Tags: backend, mapping, dados
- **Status**: ✅ corrigido em `8167f16` — sv8→SSP, sv6→TWM, sv9→JTG, bwp→BWPR, sv6pt5→SFA, me5→M5; 18 fantasmas removidos; duplicatas 11→1 (HIF legítima); snapshot +549 matches

### [P2] 16. JP mapping: 4 alvos sem set no cache (auditoria 05/08)
- `JP_TO_EN_SET` aponta SV9A→sv9pt5, s3A→swsh3pt5, s4A→swsh4pt5, s6A→swsh6pt5 — sets **não existem** no ptcg_cards_cache (fallback JP falha silenciosamente para essas siglas)
- **Fix**: adicionar os sets ao cache (refresh --full) ou corrigir o mapeamento
- Tags: backend, fallback JP, dados
- **Status**: ✅ corrigido em `8167f16` — alvos corrigidos p/ sets reais (SV9A→sv10, s3A→swsh35, s4A→swsh45, s6A→swsh7) + 28 chaves mixed-case normalizadas p/ UPPER (nunca casavam) — 0 alvos fantasmas

---

## 🔬 P3 — Experimentos / ideias

### [P3] 17. Modelo dedicado para cartas JP
- Hoje JP usa o modelo global EN via fallback (mapeamento de 62 siglas); usuário pediu modelo JP dedicado, mas sem features exclusivas decidiu-se pelo fallback
- **Ideia futura**: coletar mais dados JP (histórico de preços da Liga) e treinar modelo separado
- Tags: modelagem, JP

### [P3] 18. Embeddings: testar dinov2-large em produção
- Ablações: `large/cls+mean/pca32` teve R² 0.2948 vs `base` 0.2870 (+0.008); base foi integrado por custo/velocidade
- **Ideia**: rodar large quando GPU estiver ociosa e comparar em produção (A/B)
- Tags: modelagem, embeddings

### [P3] 19. Ensembling USD+BRL
- BRL usa USD como feature; **Ideia**: testar blend (média ponderada) ou stacked model
- Tags: modelagem

### [P3] 20. Alertas de cartas da coleção do usuário
- **Ideia**: usuário marca cartas que possui; o sistema avisa quando elas sobem/descem
- Tags: produto

### [P3] 21. App mobile / PWA
- Front é responsivo e acessível via `192.168.0.8:3000` na rede local; **Ideia**: transformar em PWA (manifest + service worker) para instalar no celular
- Tags: frontend, produto

### [P3] 22. Deps não usadas no frontend (auditoria 05/08)
- `@google/genai`, `motion`, `class-variance-authority`, `@hookform/resolvers` estão no package.json mas **não são importados** em lugar nenhum do app
- **Fix**: `npm uninstall` (reduz bundle/instalação)
- Tags: frontend, limpeza

### [P3] 23. `crawler/crawl_tcgdex.py` quebrado (auditoria 05/08)
- `await` fora de função na linha 6 → SyntaxError — script nunca roda
- Já substituído pelo fluxo crawler_liga (legado morto); **Fix**: remover ou corrigir
- Tags: backend, limpeza

### [P3] 24. Scanner usa vit-base (embeddings incompatíveis com DINOv2 do servidor)
- `pipeline.ts` usa `Xenova/vit-base-patch16-224` (768d) mas o servidor indexa com dinov2-base/PCA32
- Se o P0.1 (busca na base completa) for implementado, os embeddings do browser NÃO comparam com os do servidor
- **Fix**: usar modelo DINOv2 no browser (Xenova/dinov2-base) ou fazer a extração no servidor
- Tags: frontend, scanner, embeddings

### [P3] 25. Typos cosméticos em prints (auditoria 05/08)
- `score_apos_crawl.py` linha ~435: "INF vancadas" (sem espaços), linha ~436: `{"Cape":30s}` em vez de `{"Carta":30s}`, linha ~393: "Inlacionada" (ligado ao P0.2)
- `layout.tsx`: `lang="en"` em app pt-BR
- Tags: cosmético

### [P3] 26. Alternativa jsfeat para o clipping (sem OpenCV.js)
- **Contexto**: Fase 1 do clipping implementada com OpenCV.js (`@techstark/opencv-js`, `/scanner/opencv.js` ~13 MB WASM embutido) em `app/lib/cardClip.ts` — Canny multi-passada + contorno + warpPerspective
- **Ideia (usuário)**: implementar tudo na mão com **jsfeat** (~150 KB, JS puro) para reduzir o download (~53 MB → ~40 MB) e eliminar a dependência do WASM
- **O que falta no jsfeat**: não tem `approxPolyDP`/`warpPerspective` nativos — precisaria implementar (Douglas-Peucker ~40 linhas; transform de perspectiva via math manual ou rasterização) — e validar razão de aspecto igual
- **Plano**: só se o download virar problema real (GitHub Pages/dados móveis); manter OpenCV.js como implementação canônica da Fase 1
- Tags: scanner, clipping, frontend, P3

---

## ✅ Recentes (resolvidos — referência)

| Item | Commit |
|---|---|
| P1.7+P1.8+P2.15+P2.16: gênero treinadores, BRL snapshot, mapping, JP | `8167f16` |
| Página /features (debug: predições + todas as features) | `b56162a` |
| P0.2-P0.5: inflacionadas visíveis + build TS + cache mtime + paths | `44a2f3e` |
| Auditoria completa 05/08: 8 bugs novos (P0.2-P0.5, P1.6-P1.8) + 6 itens P2/P3 registrados | `—` (ver BACKLOG) |
| P2.5+P2.7: nome do set no /snapshot + histórico no /card | `6ca38e0` |
| P2.8: refresh incremental do cache ptcg no cron semanal | `5b8d210` |
| P1: fallback offline scanner + sync mapping no cron + badge carta JP | `4f53558` |
| BACKLOG.md centralizado | `0d99794` |
| Changelog page (commits + ablações) | `f214b7f` |
| Bug link Liga no `/card` (Mew ex MEW vs Celebrations) + mapping completo | `07b5679` |
| Contagem negativa snapshot + duplicação fallback JP + limpeza crawler | `0d9ff28` |
| `.hermes.md` atualizado | `aac8391` |
| ensure_embeddings incremental nos crons | `0e8a81b` |
| Embeddings vencedores integrados (base/cls+mean/PCA32) | `b2c9e1b` |
| Ablações de embeddings | `6b943bf` |

---

## Como manter

- Adicionar itens novos com prioridade + tags + estimativa quando souber
- Mover para "Recentes" ao resolver, com o hash do commit
- Fontes: `.hermes.md`, `OPORTUNIDADES_MODELO.md`, `experiments/ablation_results.csv`
