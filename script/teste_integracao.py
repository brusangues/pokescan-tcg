#!/usr/bin/env python
"""teste_integracao.py — valida o scanner de ponta a ponta no site.

Roda contra o site PUBLICADO (default) ou um build local, e confere os
poderes essenciais do scanner em uma rodada rápida:

  1. ÍNDICE — size/assets (index/row_cards/pca/cards.json) baixáveis e não-vazios.
  2. MOTOR — carrega (Ativar motor -> PRONTO) no browser real.
  3. BUSCA — busca por texto de uma carta liga_only (ex. Detetive Pikachu)
     retorna resultado (carta está no índice).
  4. SCAN — sobe uma foto multi-carta da base rotulada e detecta M+N cartas,
     com pelo menos 1 delas identificada (não '✓ sem nome').
  5. CARD — abre /card de um id liga_only e confere título (sem 404).

Flags:
  --base URL        (default https://brusangues.github.io/pokescan-tcg)
  --local           usa http://localhost:8080 (build estático local)
  --foto PATH       foto a escanear (default: binder 115739 da base rotulada)
  --card-set S      set da carta a validar na /card (default 246)
  --card-num N      num da carta a validar na /card (default 14)
  --card-nome NOME  nome da carta a validar na /card (default 'Charizard')
  --card-id-canonic ID  card_id canônico {idE}-{lang}-{num} a validar (default 71-en-60)
  --card-busca T    termo de busca textual (default 'charizard'; precisa existir
                    no cards.json do site, não no índice do scanner)
  --col-card-id ID  carta p/ testar a coleção (default 411-en-4 Charmander)
  --col-nome NOME   nome esperado da carta na coleção (default Charmander)
Exit: 0 = pass, 1 = falha (com quais checks falharam na saída).

Uso: python script/teste_integracao.py [--local] [--base URL]
"""
import argparse, json, re, sys, unicodedata
from pathlib import Path

import asyncio
from playwright.async_api import async_playwright

REPO = Path(__file__).resolve().parent.parent
labels_cache = None

def base_labels():
    global labels_cache
    if labels_cache is None:
        labels_cache = json.loads((REPO/'experiments'/'base_labels.json').read_text(encoding='utf-8'))
    return labels_cache

def norm(s):
    if not s: return ''
    return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFD',s).encode('ascii','ignore').decode().lower())

async def espera_fim(page, timeout=120):
    """Espera o upload disparar ('Analisando' aparecer) e o scan terminar (sair)."""
    import time as _t
    t0 = _t.time()
    viu = False
    while _t.time()-t0 < timeout:
        b = await page.evaluate('document.body.textContent')
        if 'Analisando' in b:
            viu = True
            break
        await page.wait_for_timeout(2000)
    if not viu:
        return False
    while _t.time()-t0 < timeout:
        b = await page.evaluate('document.body.textContent')
        if 'Analisando' not in b:
            return True
        await page.wait_for_timeout(3000)
    return True

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='https://brusangues.github.io/pokescan-tcg')
    ap.add_argument('--local', action='store_true')
    ap.add_argument('--foto', default=str(REPO.parent/'pokescan-tcg-labels'/'done'/'20260822_115739.jpg'))
    ap.add_argument('--card-set', default='base1')
    ap.add_argument('--card-num', default='4')
    ap.add_argument('--card-nome', default='Charizard')
    ap.add_argument('--card-id-canonic', default='71-en-60')
    ap.add_argument('--lig-card-id', default='733-1')
    ap.add_argument('--vendas-card-id', default='733-23')  # carta com vendas verificadas
    ap.add_argument('--card-busca', default='charizard')
    ap.add_argument('--col-card-id', default='411-en-4')  # carta p/ testar a coleção
    ap.add_argument('--col-nome', default='Charmander')
    a = ap.parse_args()
    base = 'http://localhost:8080' if a.local else a.base

    checks = []
    def check(nome, ok, det=''):
        checks.append((nome, bool(ok), det))
        mark = '✅' if ok else '❌'
        print(f'  {mark} {nome}' + (f' — {det}' if det else ''))

    print(f'🧪 Teste de integração — scanner @ {base}\n')

    async with async_playwright() as p:
        # contexto limpo (cache de browser persiste cards.json/index e mascara fixes)
        bro = await p.chromium.launch()
        ctx = await bro.new_context(viewport={'width':1400,'height':1100})
        page = await ctx.new_page()

        try:
            await page.goto(base + '/scanner/', wait_until='networkidle', timeout=90000)
        except Exception as e:
            check('abrir /scanner', False, str(e)[:80])
            return 1

        # 1. Índice baixável
        assets = ['index.bin', 'row_cards.bin', 'pca.bin', 'cards.json']
        tamanhos = {}
        try:
            for asset in assets:
                resp = await page.evaluate(f"""async (u)=>{{
                    const r=await fetch(u); return r.status;}}""", f'{base}/scanner/{asset}')
                # dado pode nao ser fetchável por status; pega tamanho via HEAD-like
                tamanhos[asset] = resp
        except Exception as e:
            check('fetch assets do scanner', False, str(e)[:80])
        else:
            ok_assets = all(t in tamanhos and tamanhos[t] == 200 for t in assets)
            # tamanho: usa a requisicao do motor que ja baixou (index ~28MB)
            idx = tamanhos.get('index.bin', 0)
            cards = tamanhos.get('cards.json', 0)
            check('assets do scanner (HTTP 200)', ok_assets,
                  f"index {idx} · cards {cards}")
            # o tamanho real via fetch com arrayBuffer do index
            try:
                nbytes = await page.evaluate(f"""async ()=>{{const r=await fetch('{base}/scanner/index.bin'); const b=await r.arrayBuffer(); return b.byteLength;}}""")
            except Exception:
                nbytes = 0
            check('índice tem cartas da Liga (>25MB fp16)', nbytes > 25e6, f"{nbytes/1e6:.1f}MB")
            try:
                cbytes = await page.evaluate(f"""async ()=>{{const r=await fetch('{base}/scanner/cards.json'); return (await r.text()).length;}}""")
            except Exception:
                cbytes = 0
            check('cards.json não-vazio', cbytes > 40000, f"{cbytes/1e6:.1f}MB chars")

            # catálogo do site: bloco de vendas verificadas (v3m) anexado pelo build
            try:
                v3m = await page.evaluate(f"""async ()=>{{
                    // O cards.json e republicado a cada deploy: logo apos publicar, o
                    // CDN pode devolver versao parcial/404 por alguns segundos. Retenta.
                    const busca = async () => {{
                        let erro = '';
                        for (let i = 0; i < 4; i++) {{
                            try {{
                                const r = await fetch('{base}/data/cards.json', {{cache: 'no-store'}});
                                if (r.ok) return await r.json();
                                erro = 'HTTP ' + r.status;
                            }} catch (e) {{ erro = String(e).slice(0, 50); }}
                            await new Promise(res => setTimeout(res, 2500));
                        }}
                        throw new Error(erro || 'cards.json indisponivel');
                    }};
                    const j = await busca();
                    const com = j.filter(c => c && c.v3m);
                    const campos = com.every(c => Array.isArray(c.v3m.v) || Array.isArray(c.v3m.n) || Array.isArray(c.v3m.f)
                        || (c.v3m.gr && c.v3m.gr.n > 0) || (c.v3m.pc && Object.keys(c.v3m.pc).length > 0));
                    const vendas = com.filter(c => Array.isArray(c.v3m.v)).length;
                    return {{total: j.length, com: com.length, campos: campos, vendas: vendas,
                             ts: com.length ? (com[0].v3m.ts || '') : ''}};
                }}""")
            except Exception as e:
                check('catálogo: vendas verificadas (v3m)', False, str(e)[:60])
            else:
                check('catálogo: vendas verificadas (v3m)',
                      v3m['com'] > 0 and v3m['campos'],
                      f"{v3m['com']} de {v3m['total']} cartas · {v3m['vendas']} com vendas · ts {v3m['ts']}")

        # 2. Motor PRONTO + dropzone habilitado
        mot_ok = False
        try:
            # reativa o motor (dropzone fica disabled até phase=ready)
            await page.wait_for_function('document.body.textContent.toUpperCase().includes("PRONTO")', timeout=180000)
            try:
                await page.locator('button:has-text("Ativar motor")').click(timeout=6000)
            except Exception:
                pass
            # espera o DROPZONE habilitar (phase=ready), não só o texto
            for _ in range(60):
                await page.wait_for_timeout(3000)
                hab = await page.evaluate("""() => {const dz=document.querySelector('[class*=border-dashed]'); return dz?!(dz.className.includes('opacity-50')):false;}""")
                if hab:
                    mot_ok = True
                    break
        except Exception as e:
            pass
        check('motor de busca + dropzone habilitado', mot_ok)

        # 3. Scan de foto multi-carta (PRIMEIRO, antes da busca — estado limpo)
        foto = a.foto
        if not Path(foto).exists():
            check(f'scan foto ({Path(foto).name})', False, 'foto não encontrada')
        else:
            n_detectadas = n_ident = 0
            try:
                await page.set_input_files('input[type=file]', foto)
                await espera_fim(page, timeout=150)
                corpo = await page.evaluate('document.body.textContent')
                partes = [q for q in re.split(r'Carta \d+', corpo) if q.strip()]
                n_detectadas = len(partes)
                n_ident = len(re.findall(r'✓\s*[^\d%\n]{2,40}?\d+\.\d%', corpo))
            except Exception as e:
                check('scan da foto', False, str(e)[:80])
            check('scan detecta várias cartas', n_detectadas >= 4, f'{n_detectadas} cartas')
            check('ao menos 1 carta identificada (✓ com %)', n_ident >= 1, f'{n_ident} identificadas')

        # 6e. Botão 'Tenho' no resultado do SCAN (bug a5a9814) — DeteccaoCard
        try:
            n_tenho = await page.evaluate("""() => [...document.querySelectorAll('button')].filter(b=>b.title==='Adicionar à minha coleção').length""")
            check('botão "Tenho" no resultado do scan', n_tenho >= 1, f'{n_tenho} cartas marcáveis')
        except Exception as e:
            check('botão Tenho no scan', False, str(e)[:60])

        # 4. Página /card (formato set+num+nome — como o app gera os links)
        card_ok = False
        import urllib.parse as _up
        urls = [
            f'/card/?set={_up.quote(a.card_set)}&num={_up.quote(a.card_num)}&nome={_up.quote(a.card_nome)}',
            '/card/?set=base1&num=4&nome=Charizard',
        ]
        for u in urls:
            try:
                await page.goto(base + u, wait_until='networkidle', timeout=60000)
                await page.wait_for_timeout(3000)
                corpo = await page.evaluate('document.body.textContent')
                # valida o TÍTULO (nome da carta) no topo, não o ruído de "página não encontrada"
                inicio = ' '.join(corpo.split())[:600]
                tem_titulo = bool(re.search(r'[A-Za-zÀ-ÿ]{4,}', inicio))
                # marcação clara de vazio: página de 404 real tem "Página não encontrada" como título grande
                vazio = 'Página não encontrada' in inicio and not re.search(r'#\s*\d+', inicio)
                if tem_titulo and not vazio:
                    card_ok = True
                    check('carta abre na /card (set+num+nome)', True, f'{u.split("?")[1]}')
                    break
            except Exception:
                continue
        if not card_ok:
            check('carta abre na /card (set+num+nome)', False, 'só título de 404/vazio')
        # rota canônica card_id (formato {idE}-{lang}-{num}, ex 71-en-60)
        try:
            await page.goto(base + f'/card/?card_id={a.card_id_canonic}', wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(3000)
            corpo = await page.evaluate('document.body.textContent')
            inicio = ' '.join(corpo.split())[:600]
            vazio = 'Página não encontrada' in inicio and not re.search(r'#\s*\d+', inicio)
            tem_nome = bool(re.search(r'[A-Za-zÀ-ÿ]{4,}', inicio))
            check(f'/card?card_id canônico ({a.card_id_canonic}) abre', bool(tem_nome and not vazio),
                  'abre' if (tem_nome and not vazio) else '404/vazio')
        except Exception as e:
            check(f'/card?card_id canônico ({a.card_id_canonic})', False, str(e)[:60])

        # rota liga_only (chave canônica {idE}-{num}) — valida id direto do scanner
        try:
            await page.goto(base + f'/card/?card_id={a.lig_card_id}', wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(3000)
            corpo = await page.evaluate('document.body.textContent')
            inicio = ' '.join(corpo.split())[:600]
            vazio = 'Página não encontrada' in inicio and not re.search(r'#\s*\d+', inicio)
            lig_ok = bool(re.search(r'[A-Za-zÀ-ÿ]{4,}', inicio) and not vazio)
            check(f'/card liga_only (id {a.lig_card_id}) abre', lig_ok,
                  'abre' if lig_ok else '404/vazio')
        except Exception as e:
            check(f'/card liga_only ({a.lig_card_id})', False, str(e)[:60])

        # bloco de vendas verificadas (3 meses) na /card
        try:
            await page.goto(base + f'/card/?card_id={a.vendas_card_id}', wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(3500)
            corpo = ' '.join((await page.evaluate('document.body.textContent')).split())
            tem_bloco = 'Vendas verificadas (3 meses)' in corpo
            tem_rs = bool(re.search(r'R\$\s?\d', corpo))
            tem_volume = bool(re.search(r'(Mais de [\d.]+ unidades|Menos de 5 unidades)', corpo))
            check('carta mostra vendas verificadas (3 meses)',
                  tem_bloco and tem_rs and tem_volume,
                  f"bloco={tem_bloco} R$={tem_rs} volume={tem_volume}")
        except Exception as e:
            check('carta mostra vendas verificadas (3 meses)', False, str(e)[:60])

        # P2.43 — anúncios de cartas GRADUADAS (contrato do `gr` + bloco na /card)
        gr_info = None
        try:
            gr_info = await page.evaluate(f"""async ()=>{{
                const r = await fetch('{base}/data/cards.json');
                const j = await r.json();
                const com = j.filter(c => c && c.v3m && c.v3m.gr && c.v3m.gr.n);
                const c0 = com.find(c => Array.isArray(c.v3m.gr.e) && c.v3m.gr.e.length) || com[0];
                const e = c0 && c0.v3m.gr.e ? c0.v3m.gr.e : [];
                const ok_amostra = e.length > 0 && e.every(a => Array.isArray(a) && a.length >= 3
                    && typeof a[0] === 'string' && a[0].length > 0
                    && typeof a[2] === 'number' && a[2] > 0);
                return {{n: com.length, id: c0 ? c0.id : '', nome: c0 ? c0.n : '',
                         amostras: e.length, ok_amostra: ok_amostra}};
            }}""")
            check('catálogo: anúncios graduados (gr) com empresa/escala/preço',
                  gr_info['n'] > 0 and gr_info['ok_amostra'],
                  f"{gr_info['n']} cartas com graduadas · ex. {gr_info['nome']} ({gr_info['id']}) · {gr_info['amostras']} amostras")
        except Exception as e:
            check('catálogo: anúncios graduados (gr)', False, str(e)[:60])

        try:
            # `card_id` na URL é o id da Liga ({idE}-{num}); o id do índice é
            # {ptcg}-{num} nas cartas com equivalência EN. Tentamos as cartas
            # liga_only com gr e, por fim, o Charizard BS (72-4).
            cands = await page.evaluate(f"""async ()=>{{
                const r = await fetch('{base}/data/cards.json');
                const j = await r.json();
                return j.filter(x => x && x.v3m && x.v3m.gr && x.v3m.gr.n
                                     && /^\\d+$/.test(String(x.s || '')))
                        .slice(0, 3).map(x => x.id);
            }}""")
            achou = None
            diag = ''
            pg3 = await ctx.new_page()
            try:
                for cid in list(cands or []) + ['72-4']:
                    await pg3.goto(base + f'/card/?card_id={cid}', wait_until='networkidle', timeout=60000)
                    try:
                        await pg3.wait_for_selector('text=Cartas graduadas à venda', timeout=12000)
                        achou = cid
                        break
                    except Exception:
                        corpo = ' '.join((await pg3.evaluate('document.body.textContent')).split())
                        diag = f'{cid}: {len(corpo)}ch vendas={"Vendas verificadas" in corpo}'
            finally:
                await pg3.close()
            check('carta mostra cartas graduadas à venda (P2.43)', bool(achou), f'carta={achou or diag}')
        except Exception as e:
            check('carta mostra cartas graduadas à venda (P2.43)', False, str(e)[:60])

        # 5. Busca por texto (debounce + loadCards assíncrono; digita char a char)
        try:
            await page.goto(base + '/scanner/', wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(2000)
            inp = page.locator('input[placeholder*="Buscar carta"]')
            await inp.click()
            await inp.type(a.card_busca, delay=50)
            # espera resultados renderizarem (busca é onChange com debounce)
            ok_busca = False
            for _ in range(15):
                await page.wait_for_timeout(2000)
                corpo = await page.evaluate('document.body.textContent')
                nao_achou = 'nenhuma carta encontrada' in corpo.lower()
                tem_algum = re.search(r'[A-Za-zÀ-ÿ]{4,}', corpo)
                if nao_achou:
                    break
                if tem_algum and 'Resultado' in corpo:
                    ok_busca = True
                    break
            check(f'busca "{a.card_busca}" retorna resultado', ok_busca,
                  '' if ok_busca else 'nenhuma carta encontrada')
        except Exception as e:
            check(f'busca "{a.card_busca}"', False, str(e)[:80])

        # 6. Coleção pessoal local (P2.37) — marcar 'Tenho' + página /minha-colecao
        # 6a. Página /minha-colecao vazia (localStorage limpo no contexto novo)
        try:
            await page.goto(base + '/minha-colecao/', wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(2500)
            corpo = await page.evaluate('document.body.textContent')
            vazia = 'coleção está vazia' in corpo.lower() or 'coleção está vazia' in corpo.lower()
            check('página /minha-colecao carrega (vazia)', vazia,
                  '' if vazia else 'não achou estado vazio')
        except Exception as e:
            check('/minha-colecao vazia', False, str(e)[:60])

        # 6b. Marcar carta na coleção pelo /card (via card_id canônico)
        try:
            await page.goto(base + f'/card/?card_id={a.col_card_id}', wait_until='networkidle', timeout=60000)
            await page.wait_for_function('document.body.textContent.includes("Tenho esta carta")', timeout=45000)
            await page.locator('button:has-text("Tenho esta carta")').click()
            await page.wait_for_timeout(800)
            corpo = await page.evaluate('document.body.textContent')
            marcou = 'na coleção' in corpo
            check('botão "Tenho esta carta" marca a carta', marcou)
        except Exception as e:
            check('marcar carta na coleção', False, str(e)[:60])

        # 6c. /minha-colecao mostra a carta + valor resolvido
        try:
            await page.goto(base + '/minha-colecao/', wait_until='networkidle', timeout=60000)
            ok_preco = False
            for _ in range(25):
                await page.wait_for_timeout(1500)
                corpo = await page.evaluate('document.body.textContent')
                tem_carta = a.col_nome in corpo
                tem_mercado = 'valor real' in corpo.lower()
                if tem_carta and tem_mercado and re.search(r'R\$\s*[\d.,]+', corpo):
                    ok_preco = True
                    break
            check('coleção mostra carta + valor real/estimado', ok_preco,
                  f'nome={a.col_nome} presente' if ok_preco else 'sem carta ou valor')
        except Exception as e:
            check('coleção mostra valor', False, str(e)[:60])

        # 6d. NavBar tem a rota 'Minha coleção'
        try:
            await page.goto(base + '/', wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(2000)
            corpo = await page.evaluate('document.body.textContent')
            tem_rota = 'minha coleção' in corpo.lower()
            check('NavBar tem rota "Minha coleção"', tem_rota)
        except Exception as e:
            check('NavBar rota coleção', False, str(e)[:60])

        # 6e/6f. P2.43 — coleção por unidade: graduação com valor próprio + migração
        # Contexto próprio: semeia o localStorage ANTES do primeiro load da página.
        colecao_seed = {
            'base1-4': {
                'id': 'base1-4', 'nome': 'Charizard', 's': 'base1', 'num': '4',
                'qtd': 4, 'addAt': 1,
                # 1: raw NM foil PT com custo declarado; 2: raw SP foil;
                # 3: PSA com escala publicada; 4: PSA sem a escala publicada
                'unidades': [
                    {'cond': 'NM', 'tipo': 'F', 'lang': 'PT', 'pago': 500},
                    {'cond': 'SP', 'tipo': 'F'},
                    {'grad': {'emp': 'PSA', 'esc': 'NM 7'}},
                    {'grad': {'emp': 'PSA', 'esc': 'GEM-MT 10'}},
                ],
            },
            'fake-999': {'id': 'fake-999', 'nome': 'Carta antiga', 'qtd': 2, 'addAt': 2},
        }
        ctx2 = await bro.new_context(viewport={'width': 1400, 'height': 1100})
        try:
            pg2 = await ctx2.new_page()
            await pg2.add_init_script(
                "try{localStorage.setItem('pokescan.colecao', "
                + json.dumps(json.dumps(colecao_seed)) + ")}catch(e){}")
            await pg2.goto(base + '/minha-colecao/', wait_until='networkidle', timeout=60000)
            await pg2.wait_for_timeout(2500)
            try:
                await pg2.locator('button:has-text("Unidades e condição")').first.click(timeout=8000)
                await pg2.wait_for_timeout(800)
            except Exception:
                pass
            corpo = ''
            for _ in range(20):
                await pg2.wait_for_timeout(1500)
                corpo = ' '.join((await pg2.evaluate('document.body.textContent')).split())
                if 'Valor graduado' in corpo and 'Referência' in corpo:
                    break
            m = re.search(r'Valor graduado \(referência de mercado\)\s*(R\$ [\d.,]+)', corpo)
            val = 0.0
            if m:
                val = float(m.group(1).replace('R$', '').replace('.', '').replace(',', '.').strip())
            check('coleção: unidade graduada com valor de mercado próprio (P2.43)',
                  bool(m) and val > 0 and bool(re.search(r'Referência: PSA', corpo)),
                  f'valor graduado R$ {val:.2f}' if val else 'sem valor graduado')
            check('coleção: item antigo (só qtd) migra para unidades (P2.43)',
                  'Carta antiga' in corpo and 'Unidades e condição (2)' in corpo,
                  'item sem `unidades` virou 2 unidades')

            # P2.44 — preço por CONDIÇÃO/TIPO, referência graduada pela escala,
            # tipo/idioma por unidade e custo declarado → lucro
            pc = await pg2.evaluate(f"""async ()=>{{
                const r = await fetch('{base}/data/cards.json');
                const j = await r.json();
                const com = j.filter(c => c.v3m && c.v3m.pc && Object.keys(c.v3m.pc).length);
                const c0 = com[0];
                const ok = !!c0 && Object.entries(c0.v3m.pc).every(([k, ts]) =>
                    /^(M|NM|SP|MP|HP|D)$/.test(k) && Object.values(ts).every(a =>
                        Array.isArray(a) && a.length >= 4 && typeof a[2] === 'number' && a[2] > 0));
                return {{n: com.length, ok: ok, ex: c0 ? Object.keys(c0.v3m.pc).join('/') : ''}};
            }}""")
            check('catálogo: preço por condição/tipo (pc) dos anúncios (P2.44)',
                  pc['n'] > 0 and pc['ok'],
                  f"{pc['n']} cartas com pc · ex. condições {pc['ex']}")

            check('coleção: referência pela condição+tipo da unidade (P2.44)',
                  'Referência NM · Foil' in corpo and 'mesma condição e tipo' in corpo,
                  'unidade NM/Foil casou condição e tipo')

            check('coleção: referência graduada casando a escala (P2.44)',
                  'mesma escala (NM 7)' in corpo,
                  'unidade PSA NM 7 casou a escala publicada')

            mLuc = re.search(r'Lucro sobre o que você pagou\s*\+?(R\$ [\d.,]+)', corpo)
            vLuc = 0.0
            if mLuc:
                vLuc = float(mLuc.group(1).replace('R$', '').replace('.', '').replace(',', '.').strip())
            check('coleção: custo declarado vira lucro (P2.44)',
                  bool(mLuc) and vLuc > 0 and 'pagou R$ 500,00' in corpo,
                  f'lucro R$ {vLuc:.2f} sobre pago R$ 500,00' if mLuc else 'sem bloco de lucro')
        except Exception as e:
            check('coleção: unidade graduada (P2.43)', False, str(e)[:60])
        finally:
            await ctx2.close()

        # 7. Smoke test — percorre TODAS as páginas (captura erros de render/break)
        # Cada página tem: label (navbar) + sentinel de conteúdo carregado.
        # Sentinel vazio => espera mais; se nunca chega a carregar, é bug de dados.
        paginas = [
            # (rota, label, sentinel_de_conteudo_carregado)
            ('/', 'PokéScan', 'PokéScan'),
            ('/dashboard', 'Dashboard', 'Dashboard'),
            ('/hits', 'Hits', 'Hits'),
            ('/snapshot', 'Snapshot', 'Snapshot'),
            ('/tendencias', 'Tendências', 'Tendências'),
            ('/colecoes', 'Coleções', 'Coleções'),
            ('/minha-colecao', 'Minha coleção', 'Minha coleção'),
            ('/scanner', 'Scanner', 'SCANNER'),
            ('/changelog', 'Changelog', 'Changelog'),
            ('/card/?set=base1&num=4&nome=Charizard', 'Charizard', 'Charizard'),
        ]
        for rota, label, sentinel in paginas:
            try:
                page_errors = []
                erro_fn = lambda e: page_errors.append(str(e))
                page.on('pageerror', erro_fn)
                await page.goto(base + rota, wait_until='domcontentloaded', timeout=60000)
                # espera o sentinel aparecer (skeleton/loading some) até 15s
                ok_sentinel = False
                for _ in range(10):
                    await page.wait_for_timeout(1500)
                    corpo = await page.evaluate('document.body.textContent')
                    if sentinel.lower() in corpo.lower():
                        ok_sentinel = True
                        break
                corpo = await page.evaluate('document.body.textContent')
                page.remove_listener('pageerror', erro_fn)
                # critérios: sentinel presente + sem erro de runtime + nao 404 + sem marcadores de falha de dados
                nao_404 = re.search(r'[A-Za-zÀ-ÿ]{4,}', corpo) is not None
                dados_ok = not any(k in corpo.lower() for k in
                    ['erro ao carregar', 'falha ao carregar', 'não foi possível carregar', 'application error'])
                sem_erro = not page_errors
                ok = ok_sentinel and nao_404 and sem_erro and dados_ok
                check(f'página "{label}" ({rota})', ok,
                      [] if ok else [f'sem sentinel={sentinel!r}' if not ok_sentinel else '',
                                     'pageerror' if page_errors else '',
                                     'erro dados' if not dados_ok else ''])
            except Exception as e:
                check(f'página "{label}" ({rota})', False, str(e)[:60])

        # 8. Header (NavBar) bloqueia o conteúdo por trás ao rolar
        #    Regressão: sintaxe de var do Tailwind v3 na v4 (bg-[--color-x])
        #    gera CSS inválido -> fundo transparente -> conteúdo vaza pela barra.
        try:
            for rota in ['/', '/dashboard', '/tendencias']:
                await page.goto(base + rota, wait_until='domcontentloaded', timeout=60000)
                await page.wait_for_timeout(2000)
                await page.evaluate('window.scrollTo(0, 1200)')
                await page.wait_for_timeout(500)
                info = await page.evaluate('''() => {
                    const h = document.querySelector('header');
                    if (!h) return null;
                    const cs = getComputedStyle(h);
                    const r = h.getBoundingClientRect();
                    // alfa do background computado (0 = transparente)
                    let alfa = 0;
                    const m = cs.backgroundColor.match(/rgba?\\(([^)]+)\\)/);
                    if (m) { const partes = m[1].split(',').map(s => s.trim());
                             alfa = partes.length === 4 ? parseFloat(partes[3]) : 1; }
                    const el = document.elementFromPoint(r.width/2, Math.max(2, r.height/2));
                    return {bg: cs.backgroundColor, alfa, op: cs.opacity,
                            dentro: h.contains(el)};
                }''')
                if not info:
                    check(f'header opaco em {rota}', False, 'sem <header>')
                    continue
                ok = info['alfa'] > 0 and info['op'] == '1' and info['dentro']
                check(f'header opaco (bloqueia conteúdo) em {rota}', ok,
                      '' if ok else f"bg={info['bg']} alfa={info['alfa']} dentro={info['dentro']}")
        except Exception as e:
            check('header opaco (bloqueia conteúdo)', False, str(e)[:60])
        await ctx.close(); await bro.close()

    # Resumo
    n_pass = sum(1 for _,ok,_ in checks if ok)
    n_total = len(checks)
    print(f'\n{"="*44}\nRESULTADO: {n_pass}/{n_total} checks passaram\n{"="*44}')
    faltas = [n for n,ok,_ in checks if not ok]
    if faltas:
        print('Falhas: ' + ', '.join(faltas))
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(asyncio.run(main()))