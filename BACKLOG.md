# PokeScan TCG — Backlog

Centraliza melhorias, bugs e ideias **pendentes**. Prioridade: P0 (crítico) → P1 (alto) → P2 (médio) → P3 (baixo/ideia).

> ✅ **Resolvidos não ficam aqui** — migram para [`FEATURES.md`](FEATURES.md) (lista de features desenvolvidas). Regra do projeto desde 07/08/2026.

---

## 🚀 P1 — Próxima feature

### [P1] 34. Busca multicritério no scanner (qualquer campo, multi-termo)
- **Problema**: busca atual cobre nome/número/coleção/raridade/id, mas um termo por vez — "Gengar stormfront" não casa porque "stormfront" é o nome do set e a busca não cruza carta×set.
- **Ideia**: consulta por tokens — cada token pode casar com QUALQUER campo (nome, set/coleção, raridade, número, id) e todos os tokens precisam de match. Ex.: "Gengar stormfront" → Gengar do set Stormfront; "charizard 201" → Charizard número 201; "reverse holo" → variante no nome.
- **Cuidado**: debounce/perf (índice 20k+); ranking quando múltiplos campos casam; manutenção da busca por palavras existente como fallback.
- Tags: scanner, frontend, busca

### [P1] 31. Subsets japoneses
- **Feito (19/08)**: 14 sets 1:1 re-mapeados p/ o set EN correto (ver FEATURES.md) — o P1.31 principal está resolvido.
- **Resta**: os subsets japoneses da era SWSH têm correspondência EN APENAS PARCIAL (cov 30-70%) e numeração ≠ EN — mapeá-los a 1 set daria nome/número errado; hoje resolvem por fallback de NOME (mais correto). Reavaliar caso a projeto decida suportar os sets JP nativos.
- Tags: dados, mapeamento, set, JP

### [P1] 30. Alerta de tendência + integração da previsão ao scanner
- **Feito (19/08)**: ranking de tendência da próxima semana implementado (página /tendencias — ver FEATURES.md); P1.30 principal resolvido.
- **Resta (extensão)**: disparar alerta quando carta entra no top de subida prevista (relacionado ao P2.10); integrar a previsão ao scanner/similaridade (mostrar tendência no resultado de scan evitando cartas em queda).
- Tags: dados, TCGCSV, modelagem, produto

---

## 💡 P2 — Melhorias de produto

### [P2] 32. Scanner matching: sinal independente p/ fechar gap até teto top-5
- **Estado (26/08)**: verificador ORB prototipado offline (`experiments/orb_prototipo.py`, base rotulada, métrica agregada por carta) — **caminho ORB DESCARTADO por evidência**. DINOv2 top-1 = 74/115 (64.3%); +ORB verificando ambiguidades = 75/115 (65.2%) top-3, 74/115 top-5 → ganho ~0. O ORB discrimina bem por crop (46 ambíguos → 35 a certa nos top-k → acertou 32), mas essas cartas já tinham sido achadas em outro crop da mesma foto. Conclusão: o gap ao teto está em **cartas fora do top-5 ou não detectadas pela segmentação**, não em reordenar os top-k.
- **Evidência** (base rotulada manual, `docs/AVALIACAO_LABELS.md`): acerto@1 = 74%, teto top-5 = 83% (~9pp recuperáveis). Re-rank com sinais leves + CatBoost LOFO foi NEGATIVO (−0,8pp, `0901db4`) — só um sinal INDEPENDENTE do DINOv2 pode fechar o gap.
- **Próximo passo sugerido**: atacar o recall do top-k (aumentar índice p/ cartas que hoje não chegam ao top-5, melhorar segmentação p/ recuperar cartas não detectadas) em vez de refinamento rank.
- Tags: scanner, matching, cv

### [P2] 33. Base rotulada manual — continuar crescendo (retreinar re-rank no futuro)
- **Estado**: `C:/Projects/pokescan-tcg-labels` — 29 fotos/137 cartas rotuladas 100% manual (99% corretas). Harness completo pronto: `experiments/rerank_sinais.py` (gera dataset de pares) + `treinar_rerank.py` (CatBoost LOFO com folhas agrupadas).
- **Gatilho**: com ~3x a base atual, retreinar o re-rank — hoje não generaliza (dataset pequeno). Cada nova foto rotulada também melhora a avaliação de segmentação/matching.
- Tags: scanner, dados, rotulagem

---

## 🔬 P3 — Experimentos / ideias

### [P3] 34. Segmentação: binder com fundo preto perde a fileira inferior
- **Evidência**: foto `20260822_115216` (binder 9-pocket fundo preto) — Canny+Otsu acham 4-6 quads de 8; as cartas perdidas ficam nas bordas (topo/fundo) contra o fundo escuro. Overlays em `experiments/debug_crops/`.
- **Ideia**: máscara por células do binder (grade 3x3 detectável pelas costuras) ou CLAHE local antes do Canny. Medir na base antes (réplica Python fiel: `debug_segmentacao.py`).
- Tags: scanner, segmentação, cv


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
- Front é responsivo e acessível via rede local; **Ideia**: transformar em PWA (manifest + service worker) para instalar no celular
- Tags: frontend, produto

### [P3] 26. Alternativa jsfeat para o clipping (sem OpenCV.js)
- **Contexto**: Fase 1 do clipping implementada com OpenCV.js (`@techstark/opencv-js`, `/scanner/opencv.js` ~13 MB WASM embutido) em `app/lib/cardClip.ts` — Canny multi-passada + contorno + warpPerspective
- **Ideia (usuário)**: implementar tudo na mão com **jsfeat** (~150 KB, JS puro) para reduzir o download (~53 MB → ~40 MB) e eliminar a dependência do WASM
- **O que falta no jsfeat**: não tem `approxPolyDP`/`warpPerspective` nativos — precisaria implementar (Douglas-Peucker ~40 linhas; transform de perspectiva via math manual ou rasterização) — e validar razão de aspecto igual
- **Plano**: só se o download virar problema real (GitHub Pages/dados móveis); manter OpenCV.js como implementação canônica da Fase 1
- Tags: scanner, clipping, frontend, P3
