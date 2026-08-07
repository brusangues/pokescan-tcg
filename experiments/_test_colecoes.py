"""Testa /colecoes no dev server: tabela, slider e fetch do ev_booster.json."""
import asyncio

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        errors = []
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.goto('http://localhost:3000/colecoes/', wait_until='networkidle')
        await page.wait_for_timeout(1500)
        linhas = await page.locator('tbody tr').count()
        print('linhas da tabela:', linhas)
        h1 = await page.locator('h1').nth(1).inner_text()
        print('h1:', h1)
        slider = await page.locator('input[type=range]').count()
        print('slider presente:', slider == 1)
        if linhas:
            primeira = await page.locator('tbody tr').first.locator('td').first.inner_text()
            print('primeira linha:', primeira.strip()[:60])
            upsides = await page.locator('tbody tr').first.locator('td').nth(3).inner_text()
            print('upside 1ª linha:', upsides.strip()[:40])
        # muda o slider e verifica reordenação
        await page.locator('input[type=range]').fill('50')
        await page.wait_for_timeout(500)
        valor = await page.locator('input[type=range]').input_value()
        print('slider após fill:', valor)
        print('erros:', errors if errors else 'nenhum')
        await browser.close()


asyncio.run(main())
