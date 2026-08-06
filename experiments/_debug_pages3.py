"""Valida o clique num link de carta no site real (hits → /card com prefixo)."""
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

        # Hits → clica na primeira carta
        await page.goto(f'{BASE}/hits/', wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(2500)
        link = await page.evaluate('''() => {
            const a = document.querySelector('a[href*="card?"]');
            return a ? a.getAttribute('href') : null;
        }''')
        print(f'1. link da primeira carta em /hits/: {link}')

        if link:
            await page.click('a[href*="card?"]')
            await page.wait_for_timeout(4000)
            final = page.url
            h1 = await page.evaluate('document.querySelector("h1")?.textContent?.trim()')
            print(f'2. URL final: {final[:110]}')
            print(f'3. h1: {h1!r}')

        # Scanner → "Ver detalhes" (Link com query)
        await page.goto(f'{BASE}/scanner/', wait_until='domcontentloaded')
        await page.wait_for_timeout(1000)
        vd = await page.evaluate('''() => {
            const a = document.querySelector('a[href*="card?"]');
            return a ? a.getAttribute('href') : null;
        }''')
        print(f'4. link "Ver detalhes" no scanner (se houver resultados): {vd}')

        # Voltar (Link href="/") da página de carta
        if link:
            await page.goto(final, wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(2500)
            vb = await page.evaluate('''() => {
                const a = document.querySelector('a[href="/pokescan-tcg"]');
                return a ? a.getAttribute('href') : '(não achou — procurando a[href="/"]) ' + (document.querySelector('a[href="/"]')?.getAttribute('href') || 'nenhum');
            }''')
            print(f'5. link Voltar: {vb}')

        if errors:
            print(f'\nERROS ({len(errors)}):')
            for e in errors[:10]:
                print(' ', e)
        else:
            print('\nSEM erros ✓')
        await browser.close()

asyncio.run(main())
