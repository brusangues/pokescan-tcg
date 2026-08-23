"""avaliacao_margem.py — re-escaneia imagens MULTI-CARTA e captura margem top-1 vs top-2/3,
para testar se AMBIGUIDADE (margem pequena) discrimina acerto de erro.

Body: "Carta N ... ✓ Nome pct% [Set] #2 Nome (pct)% #3 Nome (pct)%"
Saída: experiments/margem_labels.json  {arquivo: [{nome, pct, margem2, margem3, nao_id}]}
"""
import asyncio, json, os, re, unicodedata
from playwright.async_api import async_playwright

BASE='https://brusangues.github.io/pokescan-tcg'
REPO_LABELS=r'C:\Projects\pokescan-tcg-labels'
BASE_JSON=r'C:\Projects\pokescan-tcg\experiments\base_labels.json'
SALIDA=r'C:\Projects\pokescan-tcg\experiments\margem_labels.json'
PROFILE=r'C:\Models\pokescan-tcg\qa\.pw_profile'

REG_MAIN=re.compile(r'Carta \d+.*?✓\s*([^\d]{2,40}?)\s*(\d{1,4}\.\d)%')
# similares: #N Nome (pct)%
REG_SIM=re.compile(r'#\d\s*([^()]{2,40}?)\s*\((\d{1,3}(?:\.\d)?)%\)')
# Nome até o pct (nome não tem dígitos ou %; é non-greedy)
REG_MAIN2=re.compile(r'✓\s*([^%\d]{1,45}?)\s*(\d{1,4}\.\d)%')

def norm(s): 
    if not s: return ''
    return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFD',s).encode('ascii','ignore').decode().lower())

def localiza(n):
    for r in (os.path.join(REPO_LABELS,'done'), REPO_LABELS):
        p=os.path.join(r,n)
        if os.path.exists(p): return p
    return None

async def espera(page, timeout=300):
    t0=asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time()-t0<60:
        if 'Analisando' in await page.evaluate('document.body.textContent'): break
        await page.wait_for_timeout(2000)
    else: return 'sem_scan'
    while asyncio.get_event_loop().time()-t0<timeout:
        b=await page.evaluate('document.body.textContent')
        if 'Analisando' not in b: await page.wait_for_timeout(3000); return 'resultado'
        await page.wait_for_timeout(4000)
    return 'timeout'

async def main():
    base=json.load(open(BASE_JSON,encoding='utf-8'))
    # só imagens com >=4 cartas (as de múltipla, onde o matching importa)
    alvos=[f for f,v in base.items() if len(v['cartas'])>=4]
    print(f'{len(alvos)} imagens multi-carta')
    async with async_playwright() as p:
        ctx=await p.chromium.launch_persistent_context(PROFILE, viewport={'width':1400,'height':1100})
        page=ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto(BASE+'/scanner/', wait_until='networkidle', timeout=120000)
        btn=page.locator('button:has-text("Carregar")')
        try:
            await btn.wait_for(state='visible',timeout=25000); await btn.click()
        except: pass
        try: await page.wait_for_function('document.body.textContent.toUpperCase().includes("PRONTO")',timeout=300000)
        except: pass
        print('✓ PRONTO')
        out={}
        for f in alvos:
            path=localiza(f)
            if not path: continue
            print('==',f,'==')
            await page.eval_on_selector('input[type=file]','el=>{el.value="";}')
            await page.set_input_files('input[type=file]',path)
            await espera(page)
            b=await page.evaluate('document.body.textContent')
            i=b.find('Resultado'); seg=b[i:i+30000] if i>=0 else b
            cartas=[]; pos=0
            # separa por "Carta N"
            partes=re.split(r'Carta \d+', seg)[1:]
            for part in partes:
                m=REG_MAIN2.search(part)
                sims=REG_SIM.findall(part)
                if not m: 
                    # não identificada
                    nm=re.search(r'⚠ Não identificada.*\(melhor match (\d{1,3}\.\d)%', part)
                    if nm: cartas.append({'nao_id':float(nm.group(1))})
                    continue
                nome=m.group(1).strip(); pct=float(m.group(2))
                sims=[(norm(s),float(p)) for s,p in sims]
                m2=sims[0][1] if sims else None
                cartas.append({'nome':nome,'pct':pct,'m2':m2,
                               'margem2': round(pct-m2,1) if m2 else None})
            out[f]={'cartas':cartas,'labels':base[f]['cartas']}
            print(f'  {len(cartas)} cartas | margens: {[(c["nome"],c["pct"],c.get("margem2")) for c in cartas]}')
        await ctx.close()
    json.dump(out,open(SALIDA,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
    print('salvo',SALIDA)

asyncio.run(main())