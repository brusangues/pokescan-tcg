"""Diagnóstico do /card no GitHub Pages real."""
import asyncio
from playwright.async_api import async_playwright

BASE = 'https://brusangues.github.io/pokescan-tcg'

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(f'pageerror: {str(e)[:250]}'))
        page.on('console', lambda m: errors.append(f'console.{m.type}: {m.text[:250]}') if m.type in ('error', 'warning') else None)
        page.on('response', lambda r: errors.append(f'HTTP {r.status}: {r.url[:120]}') if r.status >= 400 else None)

        await page.goto(f'{BASE}/card/?set=sm7&num=132&nome=Hau', wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(4000)
        body = await page.evaluate('document.body.textContent.slice(0, 500)')
        print('=== BODY:', body.replace('\n', ' ')[:400])
        print()
        print(f'=== ERROS ({len(errors)}):')
        for e in errors[:15]:
            print(' ', e)
        await browser.close()

asyncio.run(main())
