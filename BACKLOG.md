# PokeScan TCG — Backlog

Centraliza melhorias, bugs e ideias **pendentes**. Prioridade: P0 (crítico) → P1 (alto) → P2 (médio) → P3 (baixo/ideia).

> ✅ **Resolvidos não ficam aqui** — migram para [`FEATURES.md`](FEATURES.md) (lista de features desenvolvidas). Regra do projeto desde 07/08/2026.

---

## 🚀 P1 — Próxima feature

### [P1] 30. Evolução do modelo temporal para prever o preço da próxima semana
- **Feito (19/08)**: P1.29 solucionado — previsão da próxima semana no card detail (ver FEATURES.md)
- **Ideia**: estender para RANKING de tendência (cartas que devem subir mais) e alerta; integrar a previsão ao scanner/similaridade
- Tags: dados, TCGCSV, modelagem, experimento

---

## 💡 P2 — Melhorias de produto

### [P2] 10. Alertas de oportunidade (Telegram)
- Crons já escoram e formatam top 10; **Ideia**: alerta dedicado quando uma carta cruza thresholds (ex. upside > +50% e iCO >= 3) — hoje é só na listagem
- Tags: crons, notificações

### [P2] 29. Calibrar threshold do scanner multi-carta (55%)
- **Contexto**: Fase 1 do multi-carta usa `THRESH = 0.55` (carta marcada "não identificada" abaixo disso) — valor inicial do levantamento, cartas grandes dão ~97% e pequenas ~40-53%
- **A fazer**: usuário envia fotos com descrições da carta real → medir o score do top-1 correto vs o limiar → ajustar `THRESH` (e talvez `LARGURA_MINIMA` de 300px) com base nos dados
- Tags: scanner, calibração, multi-carta

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
- Front é responsivo e acessível via rede local; **Ideia**: transformar em PWA (manifest + service worker) para instalar no celular
- Tags: frontend, produto

### [P3] 26. Alternativa jsfeat para o clipping (sem OpenCV.js)
- **Contexto**: Fase 1 do clipping implementada com OpenCV.js (`@techstark/opencv-js`, `/scanner/opencv.js` ~13 MB WASM embutido) em `app/lib/cardClip.ts` — Canny multi-passada + contorno + warpPerspective
- **Ideia (usuário)**: implementar tudo na mão com **jsfeat** (~150 KB, JS puro) para reduzir o download (~53 MB → ~40 MB) e eliminar a dependência do WASM
- **O que falta no jsfeat**: não tem `approxPolyDP`/`warpPerspective` nativos — precisaria implementar (Douglas-Peucker ~40 linhas; transform de perspectiva via math manual ou rasterização) — e validar razão de aspecto igual
- **Plano**: só se o download virar problema real (GitHub Pages/dados móveis); manter OpenCV.js como implementação canônica da Fase 1
- Tags: scanner, clipping, frontend, P3

### [P3] 30. Scanner multi-carta — Fase 2 (robustez + confirmação manual)
- **Contexto**: Fase 1 entregue (`15821f6`, `94b52a4`) — detecta até 10 quadriláteros, dedup por centro, match individual; limitações conhecidas: fundo não-uniforme, cartas sobrepostas, falsos positivos de detecção
- **A fazer**: (a) passada de segmentação por fundo (threshold de cor/brilho) antes do Canny — robusto para fundo escuro uniforme; (b) confirmação/correção manual das sugestões (crops desenháveis); YOLO descartado (overkill) — ver `docs/SCANNER_MULTICARTA.md`
- Tags: scanner, multi-carta, opencv, frontend
