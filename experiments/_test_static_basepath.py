"""Teste do export COM basePath /pokescan-tcg (simula GitHub Pages)."""
import asyncio
from playwright.async_api import async_playwright

BASE = 'http://localhost:8080/pokescan-tcg'

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1280, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(f'pageerror: {str(e)[:200]}'))
        page.on('console', lambda m: errors.append(f'console.{m.type}: {m.text[:200]}') if m.type == 'error' else None)

        await page.goto(f'{BASE}/', wait_until='networkidle')
        await page.wait_for_timeout(500)
        print('1. / →', await page.title())

        await page.goto(f'{BASE}/hits/', wait_until='networkidle')
        await page.wait_for_timeout(1500)
        tot = await page.evaluate('document.body.textContent.includes("Total escorado")')
        print('2. /hits/ → total escorado:', tot)

        await page.goto(f'{BASE}/card/?set=sm7&num=132&nome=Hau', wait_until='networkidle')
        await page.wait_for_timeout(3000)
        h1 = await page.evaluate('document.querySelector("h1")?.textContent?.trim()')
        print('3. /card/ → h1:', h1)

        await page.goto(f'{BASE}/scanner/', wait_until='domcontentloaded')
        await page.wait_for_timeout(1500)
        await page.click('text=Carregar scanner', timeout=15000)
        await page.wait_for_selector('text=Scanner pronto', timeout=180000)
        print('4. /scanner/ → Scanner pronto ✓')

        await page.goto(f'{BASE}/dashboard/', wait_until='networkidle')
        await page.wait_for_timeout(1500)
        ok = await page.evaluate('document.body.textContent.includes("Distribuição de Upside") || document.body.textContent.includes("Hits")')
        print('5. /dashboard/ → ok:', ok)

        await page.goto(f'{BASE}/changelog/', wait_until='networkidle')
        await page.wait_for_timeout(1000)
        commits = await page.evaluate('document.body.textContent.includes("Commits")')
        print('6. /changelog/ → commits:', commits)

        if errors:
            print(f'\nERROS ({len(errors)}):')
            for e in errors[:8]:
                print(' ', e)
        else:
            print('\nSEM erros de console ✓')
        await browser.close()

asyncio.run(main())
