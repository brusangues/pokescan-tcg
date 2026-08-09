# PokeScan TCG — Backlog

Centraliza melhorias, bugs e ideias **pendentes**. Prioridade: P0 (crítico) → P1 (alto) → P2 (médio) → P3 (baixo/ideia).

> ✅ **Resolvidos não ficam aqui** — migram para [`FEATURES.md`](FEATURES.md) (lista de features desenvolvidas). Regra do projeto desde 07/08/2026.

---

## 🟡 P1 — Alto

### [P1] 6. Nenhum cron re-treina os modelos
- Refresh do cache ptcg roda semanalmente (adiciona sets novos como me5), mas os modelos USD/BRL só são re-treinados manualmente (`script/retrain_models.py`)
- **Ideia**: adicionar `retrain_models.py` ao cron semanal (depois do refresh, antes do snapshot) — ou rodar mensalmente
- Tags: backend, modelagem, crons

---

## 💡 P2 — Melhorias de produto

### [P2] 10. Alertas de oportunidade (Telegram)
- Crons já escoram e formatam top 10; **Ideia**: alerta dedicado quando uma carta cruza thresholds (ex. upside > +50% e iCO >= 3) — hoje é só na listagem
- Tags: crons, notificações

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

### [P3] 22. Deps não usadas no frontend (auditoria 05/08)
- `@google/genai`, `motion`, `class-variance-authority`, `@hookform/resolvers` estão no package.json mas **não são importados** em lugar nenhum do app
- **Fix**: `npm uninstall` (reduz bundle/instalação)
- Tags: frontend, limpeza

### [P3] 23. `crawler/crawl_tcgdex.py` quebrado (auditoria 05/08)
- `await` fora de função na linha 6 → SyntaxError — script nunca roda
- Já substituído pelo fluxo crawler_liga (legado morto); **Fix**: remover ou corrigir
- Tags: backend, limpeza

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

### [P3] 27. Explicabilidade do modelo via SHAP values (pedido do usuário 07/08)
- **Ideia**: explicar as predições de preço (USD/BRL) mostrando a contribuição de cada feature por carta (SHAP) — identificar por que o modelo considera uma carta subvalorizada/inflacionada (ex: raridade, set, iCO, embeddings puxando para cima/baixo)
- **Como**: `shap.TreeExplainer` no CatBoost (`.get_feature_importance(type='ShapValues')` é nativo) → salvar top-N features por carta no `/features` ou bloco "Previsão do Modelo" do `/card`
- **Ganho**: confiança do usuário nas recomendações; diagnóstica viés (ex: se o modelo só olha raridade)
- **Custo**: SHAP por carta é barato no CatBoost; o volume é o dump (features × cartas) — pode ser só top-5 por carta
- Tags: modelagem, explicabilidade, frontend
