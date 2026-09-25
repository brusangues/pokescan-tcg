# Metodologia do EV por booster (pt-BR)

Objetivo: valor esperado **por pacote** das coleções, na régua do pacote pt-BR da Copag,
para a página "preço por booster" do site.

## Régua e escala

- Pacote pt-BR = **6 cartas**. As taxas de tiragem publicadas vêm do proxy inglês
  (TCGplayer/Pokebeach), medido em pacote de **10 cartas**.
- Escala: `taxa_ptBR = taxa_EN × (6/10)` = **×0,6**.
- Premissa embutida (declarar no site): o pacote pt-BR mantém a **mesma estrutura de
  slots** do inglês, apenas com menos cartas comuns.

## Regra de idade da coleção (decisão do Bruno, 24/09)

- **Coleção com mais de 6 meses de lançamento**: pode usar **taxa agregada**
  ("~X% de carta V ou melhor por pacote").
- **Coleção com menos de 6 meses**: **não** usar agregado. Só vale:
  1. taxa **medida e publicada** para aquela coleção (ex.: TCGplayer medindo N pacotes); ou
  2. **estimativa a partir de coleções comparáveis**, nomeando as comparáveis no
     resultado e explicando por que servem.
- Motivo: coleção recente tem preço/tiragem em formação, e sets comemorativos fogem do
  padrão (taxa muito maior) — o agregado de sets normais subestimaria o EV.

## Situação das três coleções pedidas

| coleção | sigla | lançamento | taxa admissível |
|---|---|---|---|
| Evoluções Prismáticas | PRE | jan/2025 | **medida** (TCGplayer, 1.200 pacotes): UR 7,46% (1/13), ACE SPEC 4,68% (1/21) — aplicar ×0,6 |
| Celebração de 30 Anos | 30C/30C-C/30THP/30C-R | 2026 (Q3/Q4) | recente ✗ agregado. Medição existe em parte (Pokebeach, 3.000 pacotes): ~50% de V ou melhor no EN; as 3 Mew RGB acima de 1/1.000 (taxa não fixada) → **faixa** |
| Megaevolução — Heróis Excelsos | ASC | 2026 | recente ✗ agregado; **sem taxa publicada** → estimar por comparáveis (declarando) ou entregar só piso |

## Saída obrigatória

- Taxa **medida** → número fechado, com a fonte e o nº de pacotes medidos.
- Taxa **estimada** → número + **comparáveis usados** e o porquê.
- Taxa **não fixada** (ex.: as Mew RGB) → **faixa**, nunca um número inventado.

Fonte dos nomes pt-BR: `data/liga/nomes_edicoes_ptbr.json`.
