# PokéScan TCG

Reconhecimento de cartas Pokémon TCG usando visão computacional e embeddings.

Tire uma foto ou faça upload de uma carta — o app identifica qual carta é via similaridade de embeddings, exibe preço de mercado e permite gerenciar sua coleção.

## Stack

| Camada | Tecnologia |
|---|---|
| Frontend | Next.js 15, React 19, Tailwind CSS 4, Motion (Framer Motion) |
| Backend | Next.js API Routes (BFF proxy) |
| IA (browser) | Xenova Transformers (ONNX) — `vit-base-patch16-224` p/ embeddings |
| API externa | [Pokémon TCG API](https://pokemontcg.io/) v2 |
| Ícones | Lucide React |

## Funcionalidades

- **Upload de imagem** da carta (drag & drop via react-dropzone)
- **Geração de embedding** no browser (~50MB model ONNX via WebAssembly)
- **Busca por similaridade** (cosseno) contra um índice local de cartas Base Set
- **Exibição de match** com nome, set, número, artista, raridade e preço de mercado (TCGPlayer)
- **Fallback offline** — resultados cacheados em `fetch_result.json` se API falhar
- **Scan via câmera** (UI preparada, botão Camera)

## Arquitetura

```
Usuário → Scanner.tsx → Pipeline (embeddings no browser)
                 ↓
          cosineSimilarity() vs índice de embeddings
                 ↓
         CardDisplay → card identificado + preço

API Routes (BFF):
  /api/cards?q=... → proxy para api.pokemontcg.io/v2/cards
                    → retry com backoff exponencial, timeout 15s
```

O modelo de embeddings (`Xenova/vit-base-patch16-224`) roda **no browser** via ONNX + WebAssembly. Nenhuma imagem sai do cliente.

## Setup

```bash
# 1. Instalar dependências
npm install

# 2. Configurar variáveis de ambiente (copie .env.example → .env.local)
#    GEMINI_API_KEY  — (opcional) legado do template AI Studio
#    APP_URL         — URL de deploy
#    POKEMON_TCG_API_KEY — (opcional) aumenta rate limits da pokemontcg.io

# 3. Rodar em dev
npm run dev

# 4. Build de produção
npm run build && npm start
```

## Estrutura

```
app/
├── api/cards/route.ts    — Proxy BFF p/ Pokémon TCG API
├── components/
│   ├── Scanner.tsx        — Upload + pipeline + matching
│   └── CardDisplay.tsx    — Card visual + preço
├── lib/
│   ├── pipeline.ts        — Singleton do modelo ONNX
│   └── pokemon.ts         — Interface + fetch com fallback
├── layout.tsx
├── page.tsx               — Landing + hero
└── globals.css

crawler/                    — Crawlers p/ coleta de dados (Python)
├── crawl_0.py
├── crawl_tcgdex.py
├── parallel.py
├── scrapers.py
├── cards_data.csv
└── df_full.csv

public/fetch_result.json    — Fallback offline da API
```

## Crawler (Python)

Scripts em Python que alimentam datasets de cartas. Usam requests + BeautifulSoup ou APIs diretas para baixar metadados de cartas Pokémon em CSV.

## Variáveis de ambiente

| Variável | Obrigatória | Descrição |
|---|---|---|
| `GEMINI_API_KEY` | Não | Legado do template original (Google AI Studio) |
| `APP_URL` | Não | URL de deploy |
| `POKEMON_TCG_API_KEY` | Não | Chave da [pokemontcg.io](https://pokemontcg.io/) p/ aumentar rate limits |

## Observações

- O modelo ONNX (~50MB) é baixado no primeiro carregamento e cacheados no browser (IndexedDB via `useBrowserCache`).
- O índice de cartas atual é limitado ao **Base Set (base1)** com 5 cartas para demonstração.
- O matching usa threshold de similaridade 0.15 — ajustável em `Scanner.tsx`.
