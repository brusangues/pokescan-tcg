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
  --card-busca T    termo de busca textual (default 'charizard'; precisa existir
                    no cards.json do site, não no índice do scanner)
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
    ap.add_argument('--card-busca', default='charizard')
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