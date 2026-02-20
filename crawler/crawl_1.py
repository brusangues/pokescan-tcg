from seleniumbase import SB
from bs4 import BeautifulSoup
import csv

def crawl_with_seleniumbase():
    url = "https://www.ligapokemon.com.br/?view=cards/variacao&show=alta"
    
    print("Iniciando navegador fantasma para burlar o Cloudflare...")
    
    # Inicia o SeleniumBase no modo Undetected Chromedriver (UC)
    # headless=False é crucial, pois o Cloudflare bloqueia bots invisíveis mais facilmente
    with SB(uc=True, headless=False) as sb:
        
        # uc_open_with_reconnect é uma função especial do SeleniumBase 
        # para contornar a tela de verificação inicial do Cloudflare
        sb.uc_open_with_reconnect(url, reconnect_time=6)
        
        # Damos um pequeno tempo extra para garantir que a lista de cartas carregou
        sb.sleep(4)
        
        print("Proteção contornada! Extraindo os dados da página...")
        html_source = sb.get_page_source()
        
    # A partir daqui, o navegador fecha e voltamos a usar o BeautifulSoup
    soup = BeautifulSoup(html_source, 'html.parser')
    cards_data = []
    
    # Seletores flexíveis para encontrar a lista
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

    # Salvando em CSV
    csv_filename = 'pokemon_cards_highest_valuation.csv'
    with open(csv_filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Card Name', 'Edition/Number', 'Variation Value', 'Current Price'])
        for data in cards_data:
            writer.writerow(data)
            
    print(f"Sucesso absoluto! {len(cards_data)} cartas foram salvas no arquivo {csv_filename}.")

if __name__ == "__main__":
    crawl_with_seleniumbase()