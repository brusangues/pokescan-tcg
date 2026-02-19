import cloudscraper
from bs4 import BeautifulSoup
import csv

def crawl_pokemon_variations():
    url = "https://www.ligapokemon.com.br/?view=cards/variacao&show=alta"
    
    print("Bypassing Cloudflare and fetching data...")
    
    # Create a scraper instance that mimics a real browser
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    
    # Use the scraper just like you would use 'requests'
    response = scraper.get(url)
    
    if response.status_code != 200:
        print(f"Failed! Cloudflare might still be blocking it. Status: {response.status_code}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    cards_data = []
    
    # Fallback selectors based on LigaPokemon's structure
    list_items = soup.select('.col-card, .item-cards, .card-row, tr') 
        
    for item in list_items:
        try:
            name_tag = item.find('p', class_='name') or item.find('a')
            card_name = name_tag.text.strip() if name_tag else ""
            
            edition_tag = item.find('p', class_='edicao') or item.find('span', class_='edicao')
            card_edition = edition_tag.text.strip() if edition_tag else ""
            
            variation_tag = item.find('div', class_='variacao-alta') or item.find('span', class_='text-success')
            variation = variation_tag.text.strip() if variation_tag else ""
            
            price_tag = item.find('div', class_='preco') or item.find('span', string=lambda text: "R$" in text if text else False)
            price = price_tag.text.strip() if price_tag else ""
            
            if card_name and (variation or price):
                cards_data.append([card_name, card_edition, variation, price])
                
        except Exception:
            continue

    csv_filename = 'pokemon_cards_highest_valuation.csv'
    with open(csv_filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Card Name', 'Edition/Number', 'Variation Value', 'Current Price'])
        for data in cards_data:
            writer.writerow(data)
            
    print(f"Success! {len(cards_data)} cards saved to {csv_filename}.")

if __name__ == "__main__":
    crawl_pokemon_variations()