"""Valida /card com modelo (Mew ex 151) + scanner completo no export estático."""
import asyncio
from playwright.async_api import async_playwright

BASE = 'http://localhost:8080'

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1280, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(f'pageerror: {str(e)[:200]}'))
        page.on('console', lambda m: errors.append(f'console.{m.type}: {m.text[:200]}') if m.type == 'error' else None)

        # 1. /card com carta que TEM modelo (Mew ex 151 — do hits de hoje)
        await page.goto(f'{BASE}/card?nome=Mew%20ex&sigla=MEW&num=151', wait_until='networkidle')
        await page.wait_for_timeout(3000)
        h1 = await page.evaluate('document.querySelector("h1")?.textContent?.trim()')
        modelo = await page.evaluate('document.body.textContent.includes("Previsão do Modelo")')
        preco = await page.evaluate('document.body.textContent.includes("Evolução de Preço")')
        print(f'1. /card Mew ex → h1={h1!r} modelo={modelo} historico={preco}')

        # 2. Scanner completo (53MB — demora)
        await page.goto(f'{BASE}/scanner/', wait_until='domcontentloaded')
        await page.wait_for_timeout(1500)
        await page.click('text=Carregar scanner', timeout=15000)
        await page.wait_for_selector('text=Scanner pronto', timeout=180000)
        print('2. /scanner → Scanner pronto ✓')

        # 3. Scan com uma das fotos de calibração (img_01 Judge)
        import base64
        from pathlib import Path
        img = Path(r'C:/projects/pokescan-tcg/experiments/calibracao/img_01.jpg')
        await page.set_input_files('input[type=file]', str(img))
        await page.wait_for_selector('text=Melhor', timeout=120000)
        await page.wait_for_timeout(2500)
        info = await page.evaluate('''() => {
            const h4 = document.querySelector('.space-y-3 .min-w-0 h4');
            const span = document.querySelector('.space-y-3 .min-w-0 span.font-mono');
            const clip = document.querySelector('.mt-3');
            return {
                nome: h4 ? h4.textContent.trim() : null,
                score: span ? span.textContent.trim() : null,
                clip: clip ? clip.textContent.trim().slice(0, 40) : null,
            };
        }''')
        print(f'3. scan img_01 → {info["nome"]} | {info["score"]} | clip={info["clip"]}')

        if errors:
            print(f'\nERROS ({len(errors)}):')
            for e in errors[:8]:
                print(' ', e)
        else:
            print('\nSEM erros de console ✓')
        await browser.close()

asyncio.run(main())
