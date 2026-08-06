"""Lista todos os links do /hits no site real (debug)."""
import asyncio
from playwright.async_api import async_playwright

BASE = 'https://brusangues.github.io/pokescan-tcg'

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        errors = []
        page.on('response', lambda r: errors.append(f'HTTP {r.status}: {r.url[:100]}') if r.status >= 400 else None)
        await page.goto(f'{BASE}/hits/', wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(4000)
        links = await page.evaluate('''() => {
            const all = [...document.querySelectorAll('a')].map(a => a.getAttribute('href')).filter(Boolean);
            const uniq = [...new Set(all)];
            return uniq.slice(0, 15);
        }''')
        print('links no /hits:')
        for l in links:
            print(' ', l)
        body_has = await page.evaluate('document.body.textContent.includes("Total escorado")')
        rows = await page.evaluate('document.querySelectorAll("a[href*=\\"card\\"]").length')
        print(f'Total escorado presente: {body_has} | links com "card": {rows}')
        print('erros:', errors[:5] if errors else 'nenhum')
        await browser.close()

asyncio.run(main())
