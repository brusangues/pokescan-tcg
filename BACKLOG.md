# PokeScan TCG — Backlog

Centraliza melhorias, bugs e ideias **pendentes**. Prioridade: P0 (crítico) → P1 (alto) → P2 (médio) → P3 (baixo/ideia).

> ✅ **Resolvidos não ficam aqui** — migram para [`FEATURES.md`](FEATURES.md) (lista de features desenvolvidas). Regra do projeto desde 07/08/2026.

---

## 🚀 P1 — Próxima feature

### [P1] 33. Nome pt-BR da Liga nas cartas do site
- **Exemplo**: [/card?set=sv8pt5&num=135&nome=Brassius](https://brusangues.github.io/pokescan-tcg/card/?set=sv8pt5&num=135&nome=Brassius) mostra "Brassius" — a Liga tem `nPT: Brás` (linha 649-135 do catálogo). O `cards.json` só leva nome EN; o catálogo Liga já resolve.
- **Ideia**: `build_static_data` anexar `nPT` (decodificar entidades HTML: `Br&aacute;s`) às cartas com join EN no cards.json/carddetail; front mostra pt-BR como nome principal (EN como secundário/tooltip). Avaliar impacto na busca por texto (indexar ambos) e nos links compartilhados (`?nome=` continua aceitando EN).
- **Cobertura esperada**: ~13.7k cartas com join EN (44% do catálogo); liga_only já usa nPT naturalmente.
- Tags: frontend, dados, liga-first, pt-BR

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

### [P2] 34. Identidade visual — sair da "cara de site gerado por IA"
- **Tells** (pesquisa 25/08 — saasui.design, joshuasnoddy.com): gradiente roxo→índigo (o tell nº 1), tudo centralizado (hero + subhead + 1 botão + 3 cards), fonte Inter, glassmorphism com sombras suaves, espaçamento uniforme sem hierarquia, componentes default de UI kit sem customização (shadcn/Tailwind cru), cards idênticos em grade, emojis decorativos. Nosso site tem vários: `rounded-2xl shadow-sm border-gray-200` em todo card, indigo como cor única, hero centrado.
- **Direção sugerida** (escolher 1 tema):
  - **A. "Guia de colecionador"** — estética de cardápio/álbum oficial Pokémon: fundo papel/creme, tipografia display arredondada (tipo Baloo/Nunito), cores por TIPO de carta (fogo=vermelho, água=azul…) como acento contextual, badges estilo TCG. Combina com o domínio; distintivo.
  - **B. "Terminal de preços"** — denso e funcional tipo Bloomberg/pro-finance: tabelas compactas, mono p/ números (tabular-nums), verde/vermelho de mercado, dark mode nativo. Prioriza a informação sobre o enfeite.
  - **C. "Editorial esportivo"** — alto contraste, headlines fortes serifadas, fotos grandes das cartas, ritmo assimétrico (quebrar a grade). Mais trabalho, mais memorável.
  - Em qualquer um: definir primitives próprias (1 botão, 1 input, 1 elevação), reduzir radius padrão, trocar Inter, matar o gradiente roxo.
- Tags: frontend, design

### [P2] 35. Scanner mobile — busca por texto presa abaixo do banner de upload
- **Problema**: resultados da busca por texto só aparecem DEPOIS do banner de subir carta; no mobile o usuário rola muito (ou nem descobre que a busca responde). Fluxo texto ≠ fluxo câmera competem pelo mesmo espaço vertical.
- **Ideias**: (a) seção de resultados colapsável/aba ("Câmera" | "Buscar") no topo; (b) resultados da busca em bottom-sheet deslizante (padrão mobile); (c) busca fixa no topo com resultados inline e upload acessível por FAB. Validar em 375px.
- Tags: scanner, frontend, mobile

### [P2] 36. Botão "Carregar índice" — linguagem de usuário, não de engenharia
- **Hoje**: revela detalhes internos (quantos MB baixando, modelo/índice/WASM) — usuário não quer saber como funciona.
- **Ideia**: copy orientada ao objetivo: "Ativar motor de busca" / "Preparar scanner" com estado único de progresso ("Preparando… pode levar alguns segundos") e pronto ("Motor pronto ✓"). MBs/detalhes técnicos ficam num `<details>` discreto "ver detalhes" para curiosos/debug. Avisar que é one-time (cache do navegador).
- Tags: scanner, frontend, ux

### [P2] 38. Copy institucional: desacoplar a marca "Liga" da interface
- **Diretriz (usuário, 25/08)**: o site não deve evidenciar que raspa a Liga Pokémon. O **link** "Ver na Liga" na página da carta pode continuar (referência útil), mas o preço em reais deve ser sempre apresentado como **"preço em reais" / "Preço real (R$)"** — nunca "preço Liga"/"Preço real (Liga)". Vale para todo o site (landing, cards, tabelas, labels).
- **Onde mexer**: `CardDetailContent.tsx` ("Preço real (Liga)"→"Preço real (R$)", "Set (Liga)"→"Coleção"), landing (`page.tsx` — "monitoramos a Liga Pokémon"→"monitoramos o mercado brasileiro"), `ScoredTable/ScoredCardRow`, textos de features/como-funciona, `gera_pred_liga.py` fonte exibida ("Modelo Liga-first (Fase 3)"→nome neutro tipo "Modelo PokéScan").
- **Regra permanente**: menções à Liga só em (a) o link externo da carta e (b) docs internos/código — nunca em labels visíveis de preço/dado.
- Tags: frontend, ux, copy

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
