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
        try:
            DRIVER = uc.Chrome(version_main=145)
        except:
            # Fallback if version detection fails
            DRIVER = uc.Chrome()
    return DRIVER


def selenium_get(url, retries=3):
    print(f"selenium_get: {url=}")
    
    driver = get_driver()
    
    for attempt in range(retries):
        try:
            print(f"Attempt {attempt + 1}/{retries}: Loading page...")
            driver.get(url)
            
            # Wait for page to load and Cloudflare challenge to complete
            # Wait up to 20 seconds for the page content to be present
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Additional wait for the specific cardsjson content
            time.sleep(3)
            
            page_source = driver.page_source
            
            with open('debug_response.html', 'w', encoding='utf-8') as f:
                f.write(page_source)
            
            # Check if we got the actual content (not a Cloudflare error page)
            if 'cardsjson' in page_source or 'card' in page_source.lower():
                print(f"Success! Page loaded.")
                return type('Response', (), {'text': page_source, 'status_code': 200})()
            else:
                print(f"Attempt {attempt + 1}/{retries}: Page loaded but content not found. Retrying...")
                if attempt < retries - 1:
                    time.sleep(5 + (attempt * 3))
                continue
                
        except Exception as e:
            print(f"Attempt {attempt + 1}/{retries}: Error - {e}")
            if attempt == retries - 1:
                raise
            time.sleep(3)
    
    raise Exception("Failed to load page after all retries")
