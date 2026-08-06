"""Teste Playwright do clipping com imagens realistas (carta 63:88 + fundo)."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE = Path(__file__).resolve().parent.parent
EXP = BASE / 'experiments'

TESTES = [
    ('_clip2_0.jpg', 'Hau'),
    ('_clip2_1.jpg', 'Voltorb'),
    ('_clip2_2.jpg', 'Iron Moth'),
    ('_clip2_3.jpg', 'Numel'),
]

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1280, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('console', lambda m: errors.append(m.text[:300]) if m.type == 'error' else None)

        await page.goto('http://localhost:3001/scanner', wait_until='networkidle')
        await page.click('text=Carregar scanner')
        await page.wait_for_selector('text=Scanner pronto', timeout=180000)
        print('✓ scanner pronto')

        for fname, esperado in TESTES:
            await page.set_input_files('input[type=file]', str(EXP / fname))
            await page.wait_for_selector('text=Melhor', timeout=90000)
            await page.wait_for_timeout(2500)

            info = await page.evaluate('''() => {
                const h4 = document.querySelector('.space-y-3 .min-w-0 h4');
                const span = document.querySelector('.space-y-3 .min-w-0 span.font-mono');
                const clip = document.querySelector('.mt-3');
                return {
                    nome: h4 ? h4.textContent.trim() : null,
                    score: span ? span.textContent.trim() : null,
                    clip: clip ? clip.textContent.trim().slice(0, 60) : null,
                };
            }''')
            ok = info['nome'] == esperado
            print(f'  {"✓" if ok else "✗"} {fname}: esperado="{esperado}" → {info}')
            if not ok and info['nome']:
                todos = await page.evaluate('() => [...document.querySelectorAll(".space-y-3 .min-w-0 h4")].map(e => e.textContent.trim())')
                print(f'      todos: {todos}')

        if errors:
            print('\nErros console/page:')
            for e in errors[:6]:
                print('  ', e)
        await browser.close()

asyncio.run(main())
