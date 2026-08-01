import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import cloudscraper


def cloudscraper_get(url):
    print(f"cloudscraper_get: {url=}")
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        },
        delay=10,
        ssl_context=None,
    )
    response = scraper.get(url)
    with open('debug_response.html', 'w', encoding='utf-8') as f:
        f.write(response.text)

    if response.status_code != 200:
        print(f"Failed! Cloudflare might still be blocking it. Status: {response.status_code}")
        print(response.text)
        raise Exception("Response status code != 200")

    return response


DRIVER = None


def get_driver():
    """Initialize undetected chromedriver"""
    global DRIVER
    if DRIVER is None:
        DRIVER = uc.Chrome(
            headless=False,
            use_subprocess=True,
            version_main=150,
        )
    return DRIVER


def selenium_get(url, retries=3, quiet=True):
    if not quiet:
        print(f"selenium_get: {url=}")
    
    driver = get_driver()
    
    for attempt in range(retries):
        try:
            if not quiet:
                print(f"Attempt {attempt + 1}/{retries}: Loading page...")
            driver.get(url)
            
            # Espera até 30s para o Cloudflare resolver
            # Procura por cardsjson OU elementos de card OU "ligapokemon" no conteúdo
            for _ in range(30):
                time.sleep(1)
                page_source = driver.page_source
                if 'cardsjson' in page_source or 'card' in page_source.lower():
                    break
            
            page_source = driver.page_source
            
            with open('debug_response.html', 'w', encoding='utf-8') as f:
                f.write(page_source)
            
            # Verifica se passou do Cloudflare (não tem _cf_chl_opt)
            if '_cf_chl_opt' not in page_source and ('cardsjson' in page_source or 'p1b' in page_source or 'nPT' in page_source):
                if not quiet:
                    print(f"Success! Page loaded with card data.")
                return type('Response', (), {'text': page_source, 'status_code': 200})()
            else:
                if not quiet:
                    print(f"Attempt {attempt + 1}/{retries}: Cloudflare still blocking. Retrying...")
                if attempt < retries - 1:
                    time.sleep(5 + (attempt * 3))
                continue
                
        except Exception as e:
            if not quiet:
                print(f"Attempt {attempt + 1}/{retries}: Error - {e}")
            if attempt == retries - 1:
                raise
            time.sleep(3)
    
    raise Exception("Failed to load page after all retries")
