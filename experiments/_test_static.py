"""Testa o export estático servido localmente (python http.server)."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE = 'http://localhost:8080'

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1280, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(f'pageerror: {str(e)[:200]}'))
        page.on('console', lambda m: errors.append(f'console.{m.type}: {m.text[:200]}') if m.type == 'error' else None)

        # 1. Landing
        await page.goto(f'{BASE}/', wait_until='networkidle')
        await page.wait_for_timeout(500)
        title = await page.title()
        print(f'1. /          → title={title!r}')

        # 2. Hits
        await page.goto(f'{BASE}/hits', wait_until='networkidle')
        await page.wait_for_timeout(1200)
        h1 = await page.evaluate('document.querySelector("h1")?.textContent?.trim()')
        rows = await page.evaluate('document.querySelectorAll("tbody tr").length')
        print(f'2. /hits      → h1={h1!r} linhas={rows}')

        # 3. Snapshot
        await page.goto(f'{BASE}/snapshot', wait_until='networkidle')
        await page.wait_for_timeout(1200)
        h1 = await page.evaluate('document.querySelector("h1")?.textContent?.trim()')
        rows = await page.evaluate('document.querySelectorAll("tbody tr").length')
        print(f'3. /snapshot  → h1={h1!r} linhas={rows}')

        # 4. Dashboard
        await page.goto(f'{BASE}/dashboard', wait_until='networkidle')
        await page.wait_for_timeout(1200)
        h1 = await page.evaluate('document.querySelector("h1")?.textContent?.trim()')
        print(f'4. /dashboard → h1={h1!r}')

        # 5. Card (set+num+nome — link do scanner)
        await page.goto(f'{BASE}/card?set=sm7&num=132&nome=Hau', wait_until='networkidle')
        await page.wait_for_timeout(2500)
        h1 = await page.evaluate('document.querySelector("h1")?.textContent?.trim()')
        hist = await page.evaluate('document.body.textContent.includes("Evolução de Preço")')
        print(f'5. /card      → h1={h1!r} historico={hist}')

        # 6. Changelog
        await page.goto(f'{BASE}/changelog', wait_until='networkidle')
        await page.wait_for_timeout(1000)
        commits = await page.evaluate('document.querySelectorAll("code, .font-mono").length')
        print(f'6. /changelog → commits~{commits}')

        # 7. Scanner — testado à parte (carrega ~53MB)
        print('7. scanner: verificado à parte')

        if errors:
            print(f'\nERROS ({len(errors)}):')
            for e in errors[:10]:
                print(' ', e)
        else:
            print('\nSEM erros de console ✓')
        await browser.close()

asyncio.run(main())
