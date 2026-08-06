# PokéScan TCG

Reconhecimento de cartas Pokémon TCG por visão computacional, com **tudo rodando no browser** — nenhuma imagem sai do cliente. O app identifica a carta por similaridade de embeddings, mostra o preço de mercado (USD/TCGPlayer + BRL/Liga Pokémon) e a previsão do modelo de preços.

**Live demo**: https://brusangues.github.io/pokescan-tcg/

## O que ele faz

- 📷 **Scanner de cartas** — envie uma foto (ou use a câmera): o clipping detecta o quadrilátero da carta e corrige a perspectiva (OpenCV.js WASM), o modelo DINOv2-small gera o embedding e o índice de 20.4 mil cartas retorna o top-5 com score. Clique no resultado para abrir a página da carta com escoragem.
- 📈 **Hits da Liga Pokémon** — oportunidades diárias: subvalorizadas (comprar) vs inflacionadas (evitar), com preço real vs preço justo do modelo.
- 🗓️ **Snapshot semanal** — panorama completo do mercado com a mesma escoragem.
- 📊 **Dashboard** — distribuição de upside, top oportunidades e inflacionadas, hits × snapshot.
- 🃏 **Página da carta** — detalhes (ataques, habilidades, raridade, artista), preços TCGPlayer/Cardmarket, previsão do modelo, histórico de preços (hits diários + snapshots) e link direto para a Liga Pokémon.
- 📜 **Changelog** — commits e ablações de embeddings do modelo.

## Stack

| Camada | Tecnologia |
|---|---|
| Frontend | Next.js 15.5 (App Router, **export estático**), React 19, TypeScript, Tailwind CSS 4, lucide-react |
| IA (browser) | DINOv2-small **uint8 ONNX** (22 MB) via Transformers.js/onnxruntime-web + OpenCV.js (clipping) |
| Índice de busca | PCA128 whitened + L2-normalizado (5.2 MB fp16) — 20.426 cartas, recall@1 **97.4%** |
| Dados de preço | **Liga Pokémon** (BRL, fonte canônica) + pokemontcg.io (features USD/TCGPlayer) |
| Modelo de preços | CatBoost (USD e BRL), embeddings DINOv2-base + PCA32, split temporal |

## Arquitetura

**100% estático** — o frontend é um export do Next.js servido no GitHub Pages, sem backend. Todos os dados (hits, snapshots, catálogo de cartas, histórico) são JSONs pré-gerados no build por `script/build_static_data.py` (os mesmos dados que as antigas API routes liam).

```
Usuário → Scanner (browser)
              ↓  foto → clipping (OpenCV.js: quadrilátero + warp de perspectiva)
              ↓  DINOv2-small uint8 ONNX → embedding 768d
              ↓  PCA128 whitened → dot product no índice (20.4k cartas)
              ↓  top-5 → /card?set=...&num=... (lookup client-side no catálogo estático)
```

Pipeline de dados (roda no PC via cron):

```
Crawlers Liga Pokémon → escoragem (match liga_id/JP/nome+num) → CSVs scored
        ↓  build_static_data.py (a cada deploy)
        ↓  frontend/public/data/*.json  →  next build  →  push gh-pages
```

## Setup (dev)

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000 (Webpack — nunca --turbo)
```

> O `npm run dev` usa o Node do sistema. O **build estático** precisa de **Node 20** (o Node 22 quebra o export no Windows — `workUnitAsyncStorage`), já resolvido no `deploy_pages.sh`.

### Variáveis de ambiente

| Variável | Obrigatória | Descrição |
|---|---|---|
| `POKEMON_TCG_API_KEY` | Não* | Chave da [pokemontcg.io](https://pokemontcg.io/) — usada **só pelos scripts Python** de coleta (aumenta rate limits) |
| `NEXT_PUBLIC_BASE_PATH` | Deploy | `/pokescan-tcg` no GitHub Pages (vazio em dev) |

\* Não é usada pelo frontend — nenhuma chave é embarcada no site.

## Deploy

```bash
bash script/deploy_pages.sh
# 1) build_static_data.py → 2) next build (Node 20) → 3) push out/ → gh-pages
```

O site fica em `https://<user>.github.io/pokescan-tcg/` (Settings → Pages → Deploy from branch `gh-pages`).

## Repositório — visão geral

```
frontend/              # Next.js 15 (export estático)
├── app/
│   ├── page.tsx       # Landing
│   ├── scanner/       # Scanner (DINOv2 + clipping, 100% browser)
│   ├── hits/ snapshot/ dashboard/ card/ changelog/ features/
│   ├── components/    # NavBar, ScoredTable, ScoredCardRow, Scanner, PriceHistory…
│   └── lib/           # cardLookup (client-side), cardClip, scannerEngine, basePath…
├── public/scanner/    # Modelo ONNX, índice PCA128, OpenCV.js (WASM)
├── public/data/       # JSONs pré-gerados (hits, snapshots, catálogo, histórico)
└── pages/_error.tsx   # _error custom (contorna bug do export no Windows)

crawler/               # Scrapers da Liga Pokémon (undetected-chromedriver)
script/                # build_static_data.py, deploy_pages.sh, score_apos_crawl.py,
                       # retrain_models.py, refresh_ptcg_cache.py, rebuild_set_mapping.py…
data/                  # Cache pokemontcg.io, snapshots, scored CSVs, embeddings (gitignored)
experiments/           # Ablações de embeddings, benchmarks (clipping, scanner)
```

> Pipeline de predição de preços (treino CatBoost USD/BRL, escoragem de oportunidades, crawlers): veja [`PIPELINE.md`](PIPELINE.md).

## Licença

Privado — uso pessoal.
