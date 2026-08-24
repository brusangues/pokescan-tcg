# PokeScan TCG — Backlog

Centraliza melhorias, bugs e ideias **pendentes**. Prioridade: P0 (crítico) → P1 (alto) → P2 (médio) → P3 (baixo/ideia).

> ✅ **Resolvidos não ficam aqui** — migram para [`FEATURES.md`](FEATURES.md) (lista de features desenvolvidas). Regra do projeto desde 07/08/2026.

---

## 🚀 P1 — Próxima feature

### [P1] 32. Migração Liga-first — Fase 3: modelos consumindo o catálogo consolidado
- **Contexto**: Fases 2.2/2.3 concluídas (`fb8d694`, `7842750`) — `data/catalogo_liga.json` (31.281 cartas da Liga, chave `{idE}-{num}`, LEFT JOIN EN 44%) existe e o site já lista MEP/MEPR. Falta o MODELO: hoje treina com target USD (TCGCSV/cache) + merge BRL por lookup — inverter para o BRL da Liga ser primário de verdade (plano `.hermes/plans/2026-08-21_liga-como-fonte-primaria.md` Fase 3).
- **Cuidado**: A/B antes (mesma disciplina do TCGCSV) — validar que não degrada MAPE/R²; BRL da Liga tem cobertura menor mas é a fonte real do mercado BR.
- Tags: dados, modelagem, liga-first

### [P1] 31. Subsets japoneses (s5a/s6a/s6K/s6H/s7R/s7D/s10P/s10D/s12a/s8b) — resolvidos por fallback
- **Feito (19/08)**: 14 sets 1:1 re-mapeados p/ o set EN correto (ver FEATURES.md) — o P1.31 principal está resolvido.
- **Resta**: os subsets japoneses da era SWSH têm correspondência EN APENAS PARCIAL (cov 30-70%) e numeração ≠ EN — mapeá-los a 1 set daria nome/número errado; hoje resolvem por fallback de NOME (mais correto). Reavaliar caso a projeto decida suportar os sets JP nativos.
- Tags: dados, mapeamento, set, JP

### [P1] 30. Alerta de tendência + integração da previsão ao scanner
- **Feito (19/08)**: ranking de tendência da próxima semana implementado (página /tendencias — ver FEATURES.md); P1.30 principal resolvido.
- **Resta (extensão)**: disparar alerta quando carta entra no top de subida prevista (relacionado ao P2.10); integrar a previsão ao scanner/similaridade (mostrar tendência no resultado de scan evitando cartas em queda).
- Tags: dados, TCGCSV, modelagem, produto

---

## 💡 P2 — Melhorias de produto

### [P2] 32. Scanner matching: verificador ORB/template-match nos top-3
- **Evidência** (base rotulada manual, `docs/AVALIACAO_LABELS.md`): acerto@1 = 74%, teto top-5 = 83% (~9pp recuperáveis). Re-rank com sinais leves + CatBoost LOFO foi NEGATIVO (−0,8pp, `0901db4`) — só um sinal INDEPENDENTE do DINOv2 pode fechar o gap.
- **Ideia**: OpenCV.js (já carregado no scanner) faz match de features ORB entre o crop query e a imagem oficial dos top-3 candidatos; arte de carta é única — geometria confirmando = boost do candidato. Prototimar OFFLINE primeiro (réplica Python + base rotulada, mesma metodologia dos estudos anteriores) antes de portar pro browser.
- Tags: scanner, matching, cv

### [P2] 33. Base rotulada manual — continuar crescendo (retreinar re-rank no futuro)
- **Estado**: `C:/Projects/pokescan-tcg-labels` — 29 fotos/137 cartas rotuladas 100% manual (99% corretas). Harness completo pronto: `experiments/rerank_sinais.py` (gera dataset de pares) + `treinar_rerank.py` (CatBoost LOFO com folhas agrupadas).
- **Gatilho**: com ~3x a base atual, retreinar o re-rank — hoje não generaliza (dataset pequeno). Cada nova foto rotulada também melhora a avaliação de segmentação/matching.
- Tags: scanner, dados, rotulagem

### [P2] 10. Alertas de oportunidade (Telegram)
- Crons já escoram e formatam top 10; **Ideia**: alerta dedicado quando uma carta cruza thresholds (ex. upside > +50% e iCO >= 3) — hoje é só na listagem
- Tags: crons, notificações

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
