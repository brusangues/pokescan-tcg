"""Teste Playwright com as 8 imagens de calibração."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

CAL = Path(__file__).resolve().parent.parent / 'experiments' / 'calibracao'

# 1-5 Judge, 6-7 Mareep, 8 = foto do usuário (cache diz que não há "Poke Tablet";
# o match confiante sugere Poké Pad — reportar o que vier)
ALVOS = {1: 'judge', 2: 'judge', 3: 'judge', 4: 'judge', 5: 'judge',
         6: 'mareep', 7: 'mareep', 8: None}  # None = só reportar

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1280, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('console', lambda m: errors.append(m.text[:300]) if m.type == 'error' else None)

        await page.goto('http://localhost:3000/scanner', wait_until='networkidle')
        await page.click('text=Carregar scanner')
        await page.wait_for_selector('text=Scanner pronto', timeout=180000)
        print('✓ scanner pronto')

        for n in sorted(ALVOS):
            await page.set_input_files('input[type=file]', str(CAL / f'img_{n:02d}.jpg'))
            await page.wait_for_selector('text=Melhor', timeout=90000)
            await page.wait_for_timeout(2200)

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
            alvo = ALVOS[n]
            if alvo is None:
                ok = ''
            else:
                ok = '✓' if alvo in (info['nome'] or '').lower() else '✗'
            clip_ok = '✓' if info['clip'] and 'detectada' in info['clip'] else ('⚠' if info['clip'] else '?')
            print(f'  {ok} img_{n:02d}: {info["nome"]} | {info["score"]} | clip={clip_ok}')

        if errors:
            print('\nErros console:', errors[:5])
        await browser.close()

asyncio.run(main())
