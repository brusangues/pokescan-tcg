"""Testa cenários reais de /card no GitHub Pages."""
import asyncio
from playwright.async_api import async_playwright

BASE = 'https://brusangues.github.io/pokescan-tcg'

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(f'pageerror: {str(e)[:200]}'))
        page.on('console', lambda m: errors.append(f'console.{m.type}: {m.text[:200]}') if m.type == 'error' else None)
        page.on('response', lambda r: errors.append(f'HTTP {r.status}: {r.url[:100]}') if r.status >= 400 else None)

        # 1. Carta COM modelo (Mew ex 151 — está no hits de hoje)
        await page.goto(f'{BASE}/card/?nome=Mew%20ex&sigla=MEW&num=151', wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(3500)
        has_modelo = await page.evaluate('document.body.textContent.includes("Previsão do Modelo")')
        has_hist = await page.evaluate('document.body.textContent.includes("Evolução de Preço")')
        h1 = await page.evaluate('document.querySelector("h1")?.textContent?.trim()')
        print(f'1. /card/ com barra (Mew ex): h1={h1!r} modelo={has_modelo} historico={has_hist}')

        # 2. Link do scanner — SEM barra (como o Scanner.tsx linka)
        await page.goto(f'{BASE}/card?set=sm7&num=132&nome=Hau', wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(3500)
        h1 = await page.evaluate('document.querySelector("h1")?.textContent?.trim()')
        final_url = page.url
        print(f'2. /card sem barra (Hau): h1={h1!r} url_final={final_url[:90]}')

        if errors:
            print(f'\nERROS ({len(errors)}):')
            for e in errors[:10]:
                print(' ', e)
        else:
            print('\nSEM erros ✓')
        await browser.close()

asyncio.run(main())
