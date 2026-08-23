"""avaliacao_labels.py — roda o scanner REAL (dev /scanner via Playwright) sobre as
imagens rotuladas manualmente e compara os matches com o ground truth (labels.txt).

Extração: ✓ NOME xx.x% | ⚠ Não identificada (melhor match xx.x)%
Comparação por NOME PRINCIPAL normalizado (1ª palavra, sem acento). O scanner devolve
nEN; as labels são pt/en. Normaliza: lowercase, remove acento, mantém só [a-z0-9].

Saída: experiments/avaliacao_labels.json — por imagem:
  {detecoes: [...], labels: [...], acertadas: [...], nao_na_label: [...], faltas: [...]}
"""
import asyncio, glob, json, os, re, unicodedata, sys
from playwright.async_api import async_playwright

BASE = 'https://brusangues.github.io/pokescan-tcg'
REPO_LABELS = r'C:\Projects\pokescan-tcg-labels'
BASE_JSON = r'C:\Projects\pokescan-tcg\experiments\base_labels.json'
SALIDA = r'C:\Projects\pokescan-tcg\experiments\avaliacao_labels.json'
PROFILE = r'C:\Models\pokescan-tcg\qa\.pw_profile'

REG_IDENT = re.compile(r'✓\s*([A-Za-zÀ-ÿ0-9 .\'\-()]+?)\s*(\d{1,3}\.\d)%')
REG_NAOID = re.compile(r'⚠ Não identificada \(melhor match (\d{1,3}\.\d)%')


def norm(s: str | None) -> str:
    if not s: return ''
    s = unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]', ' ', s)


def palavra_chave(nome: str) -> str:
    """Token principal p/ comparação: primeira palavra alfanumérica."""
    t = norm(nome).split()
    return t[0] if t else ''


def extrai(body: str) -> list:
    dets = []
    ires = body.find('Resultado')
    trecho = body[ires:ires + 30000] if ires >= 0 else body
    for m in REG_IDENT.finditer(trecho):
        dets.append({'tipo': 'match', 'nome': m.group(1).strip(), 'pct': round(float(m.group(2)), 1)})
    for m in REG_NAOID.finditer(trecho):
        dets.append({'tipo': 'nao_identificada', 'pct': round(float(m.group(1)), 1)})
    return dets


async def espera_resultado(page, timeout=300):
    t0 = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - t0 < 60:
        if 'Analisando' in await page.evaluate('document.body.textContent'):
            break
        await page.wait_for_timeout(2000)
    else:
        return 'sem_scan'
    while asyncio.get_event_loop().time() - t0 < timeout:
        body = await page.evaluate('document.body.textContent')
        if 'Analisando' not in body:
            await page.wait_for_timeout(3000)
            return 'resultado'
        await page.wait_for_timeout(5000)
    return 'timeout'


def localiza_imagem(nome_arq: str) -> str | None:
    for raiz in (os.path.join(REPO_LABELS, 'done'), REPO_LABELS, os.path.join(REPO_LABELS, 'zips')):
        p = os.path.join(raiz, nome_arq)
        if os.path.exists(p):
            return p
    return None


def principal(nomes) -> set:
    return {palavra_chave(n) for n in nomes}


async def main():
    base = json.load(open(BASE_JSON, encoding='utf-8'))
    alvos = [f for f, v in base.items() if v['cartas']]
    print(f'{len(alvos)} imagens com labels')

    # agrupa labels por palavra-chave (contando duplicadas p/ checagem simples)
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(PROFILE, viewport={'width': 1400, 'height': 1100})
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        pageerrs = []
        page.on('pageerror', lambda e: pageerrs.append(str(e)))
        await page.goto(BASE + '/scanner/', wait_until='networkidle', timeout=120000)
        btn = page.locator('button:has-text("Carregar")')
        try:
            await btn.wait_for(state='visible', timeout=25000)
            await btn.click()
        except Exception:
            print('  (botão Carregar não visível — modelo já em cache, aguardando Pronto)')
        await page.wait_for_function('document.body.textContent.toUpperCase().includes("PRONTO")', timeout=600000)
        print('✓ modelo PRONTO')

        resultados = {}
        for foto in alvos:
            path = localiza_imagem(foto)
            if not path:
                print(f'  !! sem arquivo: {foto}')
                continue
            print(f'== {foto} ==')
            await page.eval_on_selector('input[type=file]', 'el => { el.value = ""; }')
            await page.wait_for_timeout(400)
            try:
                await page.set_input_files('input[type=file]', path)
            except Exception as e:
                print(f'   set_input_files ERRO: {e}')
                continue
            st = await espera_resultado(page)
            body = await page.evaluate('document.body.textContent')
            dets = extrai(body)
            labels = base[foto]['cartas']
            # comparação por palavra-chave
            kw_matches = [palavra_chave(d['nome']) for d in dets if d['tipo'] == 'match']
            kw_labels = [palavra_chave(c['nome']) for c in labels]
            acertadas = set(kw_labels) & set(kw_matches)
            faltas = [l for l in set(kw_labels) if l not in kw_matches]
            nao_label = [m for m in set(kw_matches) if m not in kw_labels]
            resultados[foto] = {
                'status': st, 'detecoes': dets, 'labels': labels,
                'kw_matches': kw_matches, 'kw_labels': kw_labels,
                'acertadas': sorted(acertadas), 'faltas': sorted(faltas),
                'nao_na_label': sorted(nao_label),
            }
            print(f'   {st} | detecoes={len(dets)} | acertou {len(acertadas)}/{len(set(kw_labels))} | faltas={sorted(faltas)} | extra={sorted(nao_label)}')
        await ctx.close()

    json.dump(resultados, open(SALIDA, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    # resumo agregado
    tot_acc = sum(len(r['acertadas']) for r in resultados.values())
    tot_lab = sum(len(set(r['kw_labels'])) for r in resultados.values())
    tot_falt = sum(len(r['faltas']) for r in resultados.values())
    tot_extra = sum(len(r['nao_na_label'])) if resultados else 0
    print(f'\n=== RESUMO ===')
    print(f'imagens: {len(resultados)} | acertos {tot_acc}/{tot_lab} ({100*tot_acc/max(tot_lab,1):.0f}%) | faltas {tot_falt} | extra/erro {tot_extra}')
    print(f'pageerrors: {len(pageerrs)}')


if __name__ == '__main__':
    asyncio.run(main())