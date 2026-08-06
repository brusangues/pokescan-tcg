"""Verifica hrefs do NavBar (e links) no DOM após hidratação no site real."""
import asyncio
from playwright.async_api import async_playwright

BASE = 'https://brusangues.github.io/pokescan-tcg'

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(f'{BASE}/hits/', wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(3000)
        nav = await page.evaluate('''() => {
            const links = [...document.querySelectorAll('nav a')].map(a => a.getAttribute('href'));
            const logo = document.querySelector('header a, a[class*="shrink-0"]');
            return { navLinks: links, logo: logo?.getAttribute('href') };
        }''')
        print('NavBar links (após hidratação):', nav)
        await browser.close()

asyncio.run(main())
