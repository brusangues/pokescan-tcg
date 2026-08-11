# Scanner Multi-Carta — Levantamento (11/08/2026)

**Objetivo:** no /scanner, identificar **mais de uma carta** numa única foto.

**Exemplo do usuário:** `img_c5fe57e351e6.jpg` (591×1280 retrato, fundo escuro).
Análise com o pipeline real (Canny multi-passada + warp + DINOv2 PCA128):

| Região | Largura | Área da foto | Top-1 (confiança) |
|---|---|---|---|
| carta 1 | ~277px | 4.5% | Growlithe 52.7% |
| carta 2 | ~214px | 2.7% | Cheerleader's Cheer 38.9% |
| carta 3 | ~188px | 2.3% | Gengar 48.9% |
| carta 4 | ~175px | 1.4% | (ruído) |

→ A detecção **acha** as regiões (3-4 quadriláteros válidos), mas as cartas são
**pequenas** (175–277px de largura; o ideal p/ DINOv2 é 300–500px+) → confiança
baixa (~40–53% vs ~97% recall@1 com cartas grandes na calibração 8/8).

---

## Possibilidades (ordem de esforço crescente)

### A. Estender o pipeline atual: N quadriláteros → N matches (recomendada p/ Fase 1)
- **O que é**: o clipping já detecta quadriláteros (Canny multi-passada + approxPolyDP).
  Em vez de pegar o primeiro/maior, coletar **todos** os quads válidos, dedup por
  centro (as 8 passadas × 6 eps acham o mesmo quad várias vezes — dedup já validado),
  warpear cada um e rodar o embedding+match individual.
- **Mudanças**: `detectCardQuad` → `detectCardQuads` (lista); `onDrop` itera as
  regiões; a UI mostra N resultados (grid/list) em vez de 1; barra de progresso
  "analisando carta X de N".
- **Custo**: ~50–100ms por embedding (CPU) → 3 cartas ≈ +0.3s. Desprezível.
- **Ganho**: resolve o caso do exemplo (cartas lado a lado / enfileiradas, fundo
  uniforme) com o pipeline que já está calibrado.

### B. Segmentação por fundo (threshold de cor/brilho) antes do Canny
- **O que é**: quando o fundo é uniforme (mesa escura — como no exemplo), segmentar
  por brilho/cor acha as cartas como blobs claros, mais robusto que Canny para
  cartas pequenas. Combinável com A como passada extra.
- **Custo**: baixo (OpenCV inRange + contornos). Sem modelo novo.
- **Limitação**: fundo não-uniforme (mãos, mesa clara, textura) degrada.

### C. Detector de objetos treinado (YOLO/Detectron) para cartas
- **O que é**: detector real de "carta Pokémon" na cena — bounding boxes robustas
  mesmo com sobreposição/ângulo. O estado da arte para "N cartas na mesa".
- **Custo**: modelo extra no browser (+10–20MB WASM/ONNX), coleta/treino de dados
  (fotos de cartas em cena), integração onnxruntime-web com NMS. **Overkill** para
  uso pessoal; descartado na Fase 1 (fica como evolução futura se o uso justificar).

### D. Corte manual (selecionar regiões)
- **O que é**: o usuário desenha/arrasta N regiões na foto (ou o app sugere quads e
  o usuário confirma). 100% robusto, zero ML.
- **Custo**: UX nova (interação de crop no canvas).
- **Ganho**: cobre os casos que a detecção automática falha (sobreposição extrema,
  fundo claro). **Fase 2** em conjunto com A (confirmar/corrigir sugestões).

---

## Limitações (medidas no exemplo + conhecidas do pipeline)

1. **Resolução por carta** — o fator dominante. Carta com < ~300px de largura na
   foto degrada o embedding (visto: 40–53% com 175–277px). **Mitigação**: aviso
   "carta pequena — aproxime a câmera" quando a região for pequena; sugerir recorte
   da foto em 2 (identificar em 2 passos); upscale do warp (bicúbico) ajuda pouco
   (o DINOv2 não inventa detalhe).
2. **Sobreposição** — cartas parcialmente cobertas geram quad híbrido ou cortado →
   match errado. A detecção atual não resolve sobreposição (Fase 1 assume cartas
   visíveis). Mitigação parcial: se o match de uma região der confiança < threshold,
   marcá-la como "não identificada".
3. **Fundo não-uniforme** — Canny falha com fundo claro/texturizado ou sombras.
   A passada B (threshold) ajuda no fundo escuro; nada resolve fundo caótico sem
   detector (C).
4. **Dedup de quadriláteros** — as passadas múltiplas geram o MESMO quad repetido;
   o dedup por centro (15% da diagonal) já funciona, mas pode fundir cartas
   realmente próximas (cartas encostadas) — calibrar o raio.
5. **Custo do índice no browser** — o match é coseno sobre 20.4k × N queries;
   N pequeno (≤10) é ok; N grande (páginas de binder) fica lento — limite prático
   ~8–10 cartas por foto.
6. **Falsos positivos de detecção** — o Canny acha quads que NÃO são cartas
   (objetos quadrados, sombras) — o filtro de ratio (0.45–0.95) reduz mas não zera;
   o match com confiança baixa + "não identificada" cobre.

---

## Recomendação

**Fase 1 (implementada — `15821f6`):** abordagem **A** — `detectCardQuads()` + dedup +
match individual → lista de N resultados na UI, com aviso de "carta pequena" e
marcação de "não identificada" quando a confiança < ~55%. Cobre o exemplo do
usuário (5 detecções na foto, avisos corretos, validado no site real).

**Fase 2 (se necessário):** abordagem **B** (threshold por fundo como passada
extra) + **D** (confirmar/corrigir sugestões com crops manuais).

**Não agora:** detector YOLO (C) — custo alto, ganho marginal para uso pessoal.

---

## Decisões para o usuário

1. Aprova a Fase 1 (A)?
2. Threshold de confiança para "não identificada": 55%? (a calibração 8/8 com
   cartas grandes dava ~97% top-1; cartas pequenas ~40–53%)
3. Limite de cartas por foto: 5? 10?
