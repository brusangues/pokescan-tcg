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

### [P1] 2. Sync automático do mapping Liga↔ptcg
- `data/liga/liga_set_sigla_ptcg.json` (233 sets) foi completado manualmente via `script/rebuild_set_mapping.py`
- **Ideia**: rodar o rebuild no cron (antes da escoragem) para pegar sets novos automaticamente; só adiciona, não remove
- Tags: backend, mapping, crons

### [P1] 3. Cartas JP na página de detalhe
- Fallback JP mapeia sigla JP → set EN por nome; a página `/card` mostra a carta EN equivalente (preço, imagem) em vez da carta JP real
- **Ideia**: quando o match é por fallback JP, exibir badge "Carta japonesa — preço estimado do equivalente EN" e o nome/número real da Liga
- Tags: frontend, fallback JP

### [P1] 4. `fetch_result.json` vazio (fallback offline do scanner)
- `frontend/public/fetch_result.json` é o bucket quando a API pokemontcg cai; está vazio/reduzido
- **Ideia**: popular com amostra real de cartas (ex. 20 do cache local) para o scanner não quebrar offline
- Tags: frontend, resiliência

---

## 💡 P2 — Melhorias de produto

### [P2] 5. Nome do set completo no `/snapshot`
- Tabela de hits mostra "sigla + nome do set" (`ed_sNome`); snapshot não tem `ed_sNome` no CSV → mostra só sigla
- **Ideia**: incluir `ed_sNome` no CSV do snapshot (crawler já tem o dado?) ou resolver via mapping no front
- Tags: frontend, snapshot

### [P2] 6. Alertas de oportunidade (Telegram)
- Crons já escoram e formatam top 10; **Ideia**: alerta dedicado quando uma carta cruza thresholds (ex. upside > +50% e iCO >= 3) — hoje é só na listagem
- Tags: crons, notificações

### [P2] 7. Histórico de preços por carta (time series)
- Temos snapshots semanais + hits diários acumulando; **Ideia**: gráfico de evolução de preço real vs predito por carta no `/card`
- Tags: frontend, dados

### [P2] 8. Cache de cartas ptcg desatualizado
- `data/ptcg_cards_cache.json` tem 20.479 cartas; sets novos (ex. sv8pt5 Prismatic Evolutions) foram adicionados manualmente no mapping mas o cache precisa refresh periódico
- **Ideia**: script de refresh incremental do cache (pokemontcg.io paginado) + rodar no cron mensal
- Tags: backend, dados

### [P2] 9. Dashboard com mais métricas
- `/dashboard` tem métricas agregadas; **Ideia**: adicionar evolução temporal de oportunidades (subvalorizadas por dia), top sets por upside médio, distribuição de iCO
- Tags: frontend, dashboard

---

## 🔬 P3 — Experimentos / ideias

### [P3] 10. Modelo dedicado para cartas JP
- Hoje JP usa o modelo global EN via fallback (mapeamento de 62 siglas); usuário pediu modelo JP dedicado, mas sem features exclusivas decidiu-se pelo fallback
- **Ideia futura**: coletar mais dados JP (histórico de preços da Liga) e treinar modelo separado
- Tags: modelagem, JP

### [P3] 11. Embeddings: testar dinov2-large em produção
- Ablações: `large/cls+mean/pca32` teve R² 0.2948 vs `base` 0.2870 (+0.008); base foi integrado por custo/velocidade
- **Ideia**: rodar large quando GPU estiver ociosa e comparar em produção (A/B)
- Tags: modelagem, embeddings

### [P3] 12. Ensembling USD+BRL
- BRL usa USD como feature; **Ideia**: testar blend (média ponderada) ou stacked model
- Tags: modelagem

### [P3] 13. Alertas de cartas da coleção do usuário
- **Ideia**: usuário marca cartas que possui; o sistema avisa quando elas sobem/descem
- Tags: produto

### [P3] 14. App mobile / PWA
- Front é responsivo e acessível via `192.168.0.8:3000` na rede local; **Ideia**: transformar em PWA (manifest + service worker) para instalar no celular
- Tags: frontend, produto

---

## ✅ Recentes (resolvidos — referência)

| Item | Commit |
|---|---|
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
