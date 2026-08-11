# APIs de Pokémon — Pesquisa (11/08/2026)

Resumo compreensivo das APIs disponíveis sobre Pokémon (TCG e jogos), com foco em
**preço** — incluindo a pergunta central: *existe API com histórico de preço?*
(tabela rápida no fim, seção [Histórico de preços](#-histórico-de-preços-o-gap-da-modelagem)).

Legenda: ✅ usamos no pokescan-tcg · 💰 paga · 🆓 gratuita

---

## 1. Catálogo de cartas (TCG)

### Pokémon TCG API — pokemontcg.io ✅
- **O que é**: a API de referência da comunidade para dados de cartas do TCG (criada por Andrew Backes; hoje "part of Scrydex").
- **Capacidades**:
  - Catálogo completo em JSON (~20.5k cartas): nome, número, set, raridade, artista, HP, tipos, ataques, habilidades, fraquezas, retreat, legalities (formato legal), imagens (small/large), `nationalPokedexNumbers`.
  - **Preços embutidos (atual)**: TCGPlayer (low/mid/high/market/directLow por foil: normal/holofoil/reverse/1st ed…) e **Cardmarket** (avg, trend, low, germanProLow, **avg1/avg7/avg30** — média de venda em 1/7/30 dias).
  - Filtros de busca tipo Lucene (`q=name:charizard set.id:swsh4`), paginação (250/página).
- **Limitações**:
  - **Sem série histórica de preços** — só o snapshot atual + as médias móveis 1/7/30 do Cardmarket (não dá para reconstruir o preço de ontem).
  - Catálogo essencialmente EN (as versões JP/PT não são o foco; sets de outros idiomas são tratados como sets à parte).
  - Chave gratuita com limite diário (~1000 req/dia na v2; a v1 sem key era limitada a 1000/dia por IP).
- **Uso no projeto**: `ptcg_cards_cache.json` (fetch de todas as cartas), pricing embutido no treino/escoragem, imagens.

### TCGdex — api.tcgdex.net ✅ (legado — removido)
- **O que é**: API alternativa de catálogo, multilíngue (EN/FR/DE/ES/IT/PT!).
- **Capacidades**: cartas, sets, séries; **preços embutidos** cardmarket (EUR) + tcgplayer (USD) — mesmos campos médios (avg1/7/30).
- **Limitações**: mesmo padrão — preço atual apenas, sem histórico; catálogo menos completo em alguns sets novos.
- **Uso no projeto**: o `crawler/crawl_tcgdex.py` (legado quebrado) foi **removido** — substituído pelo fluxo `crawler_liga` + pokemontcg.io.

---

## 2. Preços atuais (marketplaces)

### TCGPlayer API oficial — api.tcgplayer.com 💰
- **O que é**: API oficial do maior marketplace de TCG dos EUA (Pokémon = categoria 3).
- **Capacidades**: catálogo de produtos, grupos, **prices de mercado** (market/low/mid/high/directLow), sellers, listagens, pedidos. OAuth2 (`client_credentials`).
- **Limitações**: acesso voltado a sellers/parceiros (comissionamento/contrato); rate limits por plano; não é "grátis para qualquer app".
- **Obs**: os preços já chegam de graça via pokemontcg.io/TCGCSV.

### Cardmarket API oficial — api.cardmarket.com 💰
- **O que é**: API oficial do maior marketplace europeu (Europa; preços em EUR).
- **Capacidades**: catálogo, **preços** (trend, avg, low, high, avg1/7/30…), wants, orders, inventário — pensada para sellers.
- **Limitações**: autenticação por HMAC (app key + secret), uso comercial; sem histórico público via API (o site mostra gráfico, mas a API não expõe a série).

### TCGCSV — tcgcsv.com 🆓
- **O que é**: dump estruturado dos dados públicos do TCGPlayer (categorias → grupos → produtos → preços) em JSON/CSV.
- **Capacidades**: preços atuais (market/low/mid/high/directLow por subtype: Holofoil, Reverse…), produtos selados e singles, sem key.
- **Limitações**: snapshot atual; para histórico, ver o [Archive](#tcgcsv-archive-🆓-o-achado).
- **Uso potencial**: alternativa/backup ao pricing do pokemontcg.io.

### PokéWallet — pokewallet.io 🆓
- **O que é**: API REST gratuita de preços em tempo real (TCGPlayer + CardMarket) + base de cartas completa.
- **Limitações**: projeto indie recente (2026); planos pagos para rate limits altos; confiabilidade a avaliar.

### ThePriceDex — thepricedex.com ✅
- **O que é**: site de estudos de **pull rate** por set (probabilidade de cada raridade por booster).
- **Uso no projeto**: base dos EV do booster (/colecoes — pull rates × 6/11 para o booster PT-BR).
- **Limitações**: não é API de preço — só taxas de pull.

---

## 3. Histórico de preços — *o gap da modelagem* 🎯

**Resposta curta: SIM, existem fontes** — e uma delas é gratuita e diária:

### TCGCSV Archive 🆓 ★ (o achado principal)
- **URL**: `https://tcgcsv.com/archive/tcgplayer/prices-YYYY-MM-DD.ppmd.7z`
- **O que é**: arquivo de **preços TCGPlayer diários** (market/low/mid/high) de todas as cartas — o exemplo documentado é de **2024-02-08** em diante; os arquivos acumulam dia a dia.
- **Formato**: 7z com compressão ppmd — o download é ~pequeno por dia; o conteúdo é o dump de preços daquele dia (por categoria/grupo/produto).
- **Por que importa**: é exatamente o que falta na modelagem — **série temporal diária de preços USD** (o modelo hoje só vê avg1/7/30 e o snapshot atual).
- **Como usar**: baixar diariamente (cron) ou backfillar o período 2024-02 → hoje; join por productId TCGPlayer (que também vem no pokemontcg.io? não — o join seria via grupo/numeração ou via TCGCSV products).

#### ✅ Validação feita (11/08/2026 — `experiments/validate_tcgcsv.py`, NÃO integrado ao produtivo)
- **Formato**: arquivo diário `prices-2026-08-01.ppmd.7z` = 3.98 MB comprimido / 80 MB extraído; JSON por grupo da categoria 3 (Pokémon): 217 grupos, **31.153 productIds com preço** (low/mid/high/market/directLow por subtipo Normal/Holofoil/Reverse).
- **Join com o catálogo**: via **nome do grupo TCGPlayer** ("SWSH01: Sword & Shield Base Set" → set id) + **extendedData Number** (formato `"053/202"` → `53`): **12.776/12.812 singles casaram (99.7%)** — 96/217 grupos mapeados no catálogo (o resto são selados/sets fora do cache).
- **Sanity check**: marketPrice do archive (01/08) vs tcgplayer do cache (mesma fonte) — Δ de −R$0.11 a +R$0.03 (diferença de data dos snapshots) ✓.
- **Custo do backfill**: ~4 MB/dia comprimido → 2024-02 até hoje ≈ **3.5 GB** de download (~900 arquivos).

### PriceCharting — pricecharting.com 💰
- **O que é**: preços de colecionáveis (games/cards) com **gráfico de histórico** por produto; inclui cartas Pokémon **raw e graded** (PSA/BGS/CGC…).
- **API**: `/api/product` retorna preços por condição (loose/cib/new; para cards: gradadas). O **histórico** fica no site (plano premium mostra "historic prices"); via API oficial é pago; há scrapers prontos (Apify) que extraem o `chart_data` mensal.
- **Limitações**: histórico mensal (não diário), cobertura parcial para singles modernos baratos, pago.

### cardmarketapi.com 💰 (indie)
- API de terceiros (Reddit/PokeInvesting, 2026): preços Cardmarket **em tempo real + histórico** para todos os TCG, lookup em massa. Pago.

### pokemon-api.com / "TCG Go Pro" (RapidAPI) 💰
- API paga (RapidAPI) com planos que incluem **"History Prices"** + real-time TCGPlayer/Cardmarket/Lorcana.

### CardHedger — cardhedger.com 💰
- "Price History API" para Pokémon/sports cards (raw + graded). Pago.

### TCG Price Lookup 💰
- API única com TCGPlayer + eBay em tempo real, **valores graded e price history** de 300k+ cartas.

### pokemonpricetracker.com 💰
- Histórico para cartas raw e graded + **pop data** (contagem de gradações) — citado como o mais completo em histórico no r/PokeInvesting.

### eBay API — developer.ebay.com 💰
- Browse/Search API: busca de listagens ativas com preço. **Atenção**: a busca de *sold/completed items* foi deprecada/restrita — hoje é difícil obter vendas realizadas via API oficial (exige parceria; há scrapers de "sold listings" no Apify). Útil para preço de mercado US, não para histórico fácil.

### Histórico PRÓPRIO (o que já acumulamos) ✅
- Os `scored_hits_*.csv` + `scored_snapshot_*.csv` diários (desde ago/2026) já formam uma série temporal de **preços BR (Liga)** — a única fonte de histórico BR que existe hoje, porque a Liga não publica histórico.
- Para o **histórico USD**, o TCGCSV Archive dá o backfill completo (2024 → hoje) sem depender de acumular daqui pra frente.

---

## 4. Dados dos jogos (não TCG)

### PokéAPI — pokeapi.co 🆓
- **O que é**: a API de referência para dados dos **jogos** Pokémon.
- **Capacidades**: pokémon (stats base, tipos, habilidades, sprites, altura/peso, base experience), species (cadeia evolutiva, taxa de captura, gênero, flavor texts), moves, abilities, items, berries, locations, pokedexes, generations — tudo por idioma.
- **Limitações**: **nada de TCG** (não tem cartas nem preços); sem autenticação (rate limit generoso, ~300 req/min; dados estáticos).
- **Potencial para o modelo**: features de "popularidade/fundamento" — ex: stats base, taxa de captura, número na Pokédex (já usamos `pokedex_number` + `pokemon_popularity`; a PokéAPI pode enriquecer com stats/evolução).

---

## 5. APIs brasileiras 🇧🇷

### Liga Pokémon — ligapokemon.com.br ✅
- **O que é**: o principal marketplace brasileiro de cartas Pokémon (dominante no BR).
- **API**: **não existe API pública oficial** — o acesso é via crawler (o que o projeto já faz: `crawler_liga` — preços em R$, iCO = nº de vendedores, edições PT/EN/JP, caixas seladas).
- **Limitações**: HTML dinâmico (JS) → crawler frágil e sujeito a mudanças; **sem histórico público**; sem documentação; termos de uso não explicitam crawling (usar com moderação/rate limit).
- **Obs**: a Liga lançou app próprio com scanner de cartas (2026) — o mercado BR oficial está todo nela.

### Mercado Livre API — developers.mercadolivre.com.br 🆓
- **O que é**: API oficial do ML — o maior e-commerce BR.
- **Capacidades**: `GET https://api.mercadolibre.com/sites/MLB/search?q=pokemon+charizard` → itens com **preço, condição, vendedor, vendas, thumbnail**; também `items/{id}`, categorias, sellers. Leitura básica sem token (rate limit baixo ~10 req/min; com app token sobe).
- **Por que importa**: preço **BR real de mercado secundário** (cartas usadas/novas) — complementa a Liga (que é o preço "oficial" do marketplace TCG). **Sem histórico oficial** — mas dá para acumular snapshots (mesmo padrão do histórico próprio).
- **Limitações**: busca textual (ruído — cartas vs outros produtos), sem normalização por edição Pokémon (precisa do nosso matching).

### GeckoAPI / Unwrangle 💰 (BR)
- Scrapers como serviço do Mercado Livre (PDP/PLP/reviews em JSON) — pagos; alternativa se o rate limit do ML oficial incomodar.

### Outras BR
- Não há outras APIs públicas significativas de TCG Pokémon no Brasil (o ecossistema é: Liga Pokémon + Mercado Livre + lojas físicas/Instagram). Magicsul/LigaCard/lojas usam vitrines próprias sem API.

---

## 6. Tabela-resumo

| API | Tipo | Custo | Preço atual | **Histórico** | Idiomas | Uso no projeto |
|---|---|---|---|---|---|---|
| **Pokémon TCG API** (pokemontcg.io) | Catálogo + preços | 🆓 (key) | ✅ TCGPlayer+Cardmarket (avg1/7/30) | ❌ snapshot | EN | ✅ core |
| **TCGCSV** (tcgcsv.com) | Preços TCGPlayer | 🆓 | ✅ | **✅ Archive diário desde 02/2024** | EN | — |
| **TCGCSV Archive** | Preços diários | 🆓 | ✅ | ✅✅ **diário** | EN | ⭐ candidato |
| **TCGPlayer API** | Marketplace | 💰 | ✅ | ❌ | EN | — |
| **Cardmarket API** | Marketplace | 💰 | ✅ | ❌ | EN/EU (EUR) | — |
| **PriceCharting** | Preços colecionáveis | 💰 | ✅ (raw+graded) | ✅ mensal (site/premium) | EN | — |
| **cardmarketapi.com** | Preços | 💰 | ✅ | ✅ | EN/EU | — |
| **pokemon-api.com** (RapidAPI) | Preços | 💰 | ✅ | ✅ | EN | — |
| **CardHedger** | Preços | 💰 | ✅ | ✅ | EN | — |
| **TCG Price Lookup** | Preços | 💰 | ✅ | ✅ (300k+) | EN | — |
| **pokemonpricetracker.com** | Preços + POP | 💰 | ✅ raw+graded | ✅ | EN | — |
| **PokéWallet** | Preços | 🆓/💰 | ✅ | ❌ | EN | — |
| **TCGdex** | Catálogo + preços | 🆓 | ✅ | ❌ | **EN/FR/DE/ES/IT/PT** | removido (legado) |
| **ThePriceDex** | Pull rates | 🆓 | — | — | EN | ✅ EV booster |
| **PokéAPI** | Dados dos jogos | 🆓 | — | — | **muitos** | — (potencial features) |
| **Liga Pokémon** (BR) | Marketplace BR | crawler | ✅ R$ + iCO | ❌ (acumulamos nós) | PT/EN/JP | ✅ core |
| **Mercado Livre API** (BR) | E-commerce BR | 🆓 | ✅ R$ | ❌ (acumulável) | PT | — (potencial) |

---

## 7. Conclusão / recomendação

1. **O gap de histórico de preços tem solução gratuita**: **TCGCSV Archive** — preços TCGPlayer (USD) **diários desde fev/2024** para download; é o backfill ideal para features temporais no modelo (ex: preço 7/30/90 dias atrás, tendência de longo prazo, volatilidade).
2. **Para o BR, não há fonte pública de histórico** — a Liga não publica; a estratégia atual (acumular os scored diários) é a correta, e o **Mercado Livre API** pode complementar com snapshots de preço de mercado secundário.
3. **Cuidado com as pagas**: cardmarketapi/pokemon-api/CardHedger/PriceCharting resolvem o histórico "pronto", mas o TCGCSV Archive cobre o mesmo caso (TCGPlayer USD) de graça; PriceCharting só vale se entrar graded (PSA) no escopo.
4. **Próximo passo sugerido**: baixar 1-2 dias do TCGCSV Archive para validar o formato e o join com o catálogo (productId ↔ nossa chave canônica `{idE}-lang-{sN}`), e estimar o volume do backfill 2024→hoje.

*Pesquisa: 11/08/2026 — fontes: docs.pokemontcg.io, docs.tcgplayer.com, tcgcsv.com, pricecharting.com/api-documentation, tcgdex.dev, pokeapi.co, developers.mercadolivre.com.br, help.cardmarket.com, r/PokeInvesting, tcgapi.dev.*
