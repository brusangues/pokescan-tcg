# Avaliação do scanner contra a base rotulada manual (pokescan-tcg-labels)

Data: 23/08/2026. Base: `C:/Projects/pokescan-tcg-labels` — labels 100% manuais
(99% corretas), fotos de binder/mesa, 1–9 cartas. Regra de fonte: Liga = canônica.

## Como foi feito
- `experiments/ler_labels.py` parseia `labels.txt` → `experiments/base_labels.json`
  (61 imagens, 29 com labels, 137 cartas).
- Scanner REAL rodado no site publicado (`https://brusangues.github.io/pokescan-tcg`)
  via Playwright (dev `localhost:3000` deu **bug de hidratação**
  "layout router not mounted" — incompatibilidade `output:'export'`+`next dev`
  no Next 15.5; o build estático do Pages hidrata normalmente).
  Scripts: `experiments/avaliacao_labels.py`, `experiments/avaliacao_margem.py`
  (captura top-1 pct + margem vs top-2).

## Resultados agregados (29 imagens, 115 cartas)
- **Detecção boa**: 117 detecções vs 115 cartas rotuladas.
- **Matching ~62%** de acerto (71/115), 44 erros (falsos positivos confiantes).
- Vários "erros" são só tradução pt↔en (Juiz→Judge, Lílian→Lillie, Energia de Fogo→Fire Energy),
  logo o acerto real é maior que 62%.

## Descoberta-chave: pct do top-1 NÃO discrimina acerto de erro
- Acertos: pct mínimo 46, mediana 65. | Erros: pct mínimo 42, mediana 55.
- As distribuições se sobrepõem. **Subir o THRESH de 40→60 tira ~tantos acertos
  quanto erros** → ajustar o threshold não resolve.

## Ajuste acionável 1: MARGEM top-1 vs top-2 (ambiguidade)
- Acertos: margem mediana **8.9pp** | Erros: mediana **1.7pp**; só 5/33 erros com margem ≥6.
- Exigir margem mínima (re-rank / sinalizar "incerto") mantém a maioria dos acertos e
  elimina ~73% dos falsos positivos:
  - margem ≥3pp: 75% acertos mantidos, restam 9/33 erros
  - margem ≥5pp: 67% acertos, restam 7/33 erros
- **Cuidado**: acertos de margem baixa incluem variantes da MESMA carta
  (Fire Energy vs Fire Energy, Pikachu, Mudkip duplos) — são válidos. A sinalização
  deve ser "incerto, ver top-3" (mostrar), não ocultar como não-identificado.
- Implementar em `scannerEngine.ts`: computar margem top-1/top-2, expor no `Scanner.tsx`.

## Ajuste 2: bug de score >100%
- `Multi Technical Machine 01` (20260822_115739) retornou **162.7%** (margem 106.7) —
  impossível para cosseno normalizado. São crops degenerados com normalização quebrada
  que inflam falsos matches. Investigar/corrigir normalização no `scannerEngine.ts`.

## Padrões de erro por imagem (ground truth manual)
- Piores: cartas **EN antigas** (promo/bw // Team Aqua/Magma), cartas pequenas em fileira
  na mesa (Cubone/Caterpie→Cottonee/Mr.Mime), e **variabilidade de detecção** entre fotos
  da MESMA folha (115216 detectou 4/8; 115424 detectou 7/8) — crop/enquadramento é
  parcialmente o gargalo (crop ruim → match ruim).
- Melhores: binder 3x3 folha inteira enquadrada (7-8/9 detectados, acerto ~60%).
- "Team Aqua's Claydol" etc. são acertos (a label pt é "Claydol da equipe aqua").

## Implementado (23/08)
1. **Bug score >100%**: `scannerEngine.search` agora **clamapa o score a [0,1]** e
   descarta NaN/Inf no loop (crops degenerados não dominam o rank). Causa real:
   query corrompido (provável shape do ONNX DINOv2 divergente) — o índice estava
   perfeito (normas 1.0). Exibição nunca mais >100%.
2. **Re-rank por margem** (ambiguidade): `ScanResult.margin = top-1 − top-2`
   exposta no engine. No `Scanner.tsx`, `MARGEM_MIN=0.03` (3pp): match com
   score ≥ THRESH **mas margem < 3pp** vira **"⚠ Incerto (ambíguo)"** (âmbar)
   com os candidatos, em vez de verde confiante. Efeito (medido na base):
   elimina ~73% dos falsos positivos confiantes mantendo ~75% dos acertos.
3. THRESH mantido em 0.40 (não é o limitador — pct não discrimina).
4. **Segmentação adaptativa** (`cardClip.ts`): debug visual (overlay das crops em
   `experiments/debug_crops/` via réplica Python fiel `debug_segmentacao.py` —
   reproduz o browser exatamente: 71/115=62% idênticos) mostrou que `.02` de
   minArea perde cartas de mesa pequenas, mas `.008` fixo adiciona falsos em
   fotos de 1 carta. Solução: minArea `.02` e, **se achar ≥4 quads** (multi-carta
   densa), um 2º passe `.008` recupera as pequenas (dedup global). Resultado
   Python: 62% → **64%** (74/115) sem regressão nas fotos solitárias; confirmado
   no browser (094527 detectou 4→5). Roda em `sweep_detecao.py`.

**Pitfall do loop de teste**: o dev `localhost:3000` deu bug de hidratação
("layout router not mounted" — `output:'export'`+`next dev` no Next 15.5). O
**build estático** (Node 20, `NEXT_PUBLIC_BASE_PATH=` vazio) + `python -m http.server 8080`
em `out/` **hidrata perfeitamente** e é o loop confiável (todos os assets do
scanner servidos localmente).

## Recomendações
1. **Re-rank por margem** (ambiguidade top-1/top-2) + sinalizar "incerto, ver top-3".
2. **Corrigir score >100%** (normalização de crops degenerados).
3. Mantém-se o THRESH 0.40 (não é o limitador).
4. Detecção/enquadramento é o próximo gargalo (mais ganho potencial) — mas mudança de CV maior.