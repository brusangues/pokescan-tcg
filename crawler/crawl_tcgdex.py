from tcgdexsdk import TCGdex, Language, Query

tcgdex = TCGdex("en") # "pt-br")

# Pegando todos os sets, exceto os do tcg pocket
sets = await tcgdex.set.list(Query().notEqual("serie.id", 'tcgp').sort("releaseDate", "desc"))
len(sets)

sets = sets[:2]
sets


def sdk_obj_to_dict(obj, prefix=""):
    obj_dict = obj.__dict__
    obj_dict = {prefix+k:v for k,v in obj_dict.items() if isinstance(v, (int, float, str, bool, type(None)))}
    return obj_dict

import asyncio

# Função separada para processar uma única carta
async def process_card(card, full_set_dict, semaphore):
    # O semáforo garante que não vamos fazer, por exemplo, 500 requests de uma vez
    async with semaphore:
        image_url = card.get_image_url(quality="low", extension="png")
        
        # Chamada de I/O assíncrona
        card_full = await card.get_full_card() 
        
        variants_dict = sdk_obj_to_dict(card_full.variants, "variants_")
        card_dict = sdk_obj_to_dict(card_full)
        
        print(f"    [+] Concluído: {card.name}")
        
        # Retorna o dicionário da linha em vez de fazer append diretamente
        return {
            **full_set_dict,
            **card_dict,
            "image_url": image_url,
            **variants_dict
        }

# Função separada para processar um set completo
async def process_set(set_brief, semaphore):
    print(f"Buscando set: {set_brief.name}...")
    
    # CORREÇÃO: Usar set_brief em vez de sets[0]
    full_set = await set_brief.get_full_set()
    full_set_dict = sdk_obj_to_dict(full_set, prefix="set_")
    
    # Cria uma lista de tarefas assíncronas para as cartas deste set
    tasks = [
        process_card(card, full_set_dict, semaphore) 
        for card in full_set.cards
    ]
    
    # Executa todas as tarefas de cartas simultaneamente
    cards_data = await asyncio.gather(*tasks)
    return cards_data

# Função principal que orquestra tudo
async def main_processor(sets):
    rows = []
    
    # Limita a 10 requisições simultâneas. Ajuste esse número conforme os limites da sua API.
    semaphore = asyncio.Semaphore(10) 
    
    # Cria as tarefas para todos os sets
    set_tasks = [process_set(set_brief, semaphore) for set_brief in sets]
    
    # Executa todos os sets simultaneamente
    all_sets_results = await asyncio.gather(*set_tasks)
    
    # all_sets_results será uma lista de listas. Vamos "achatar" (flatten) isso para a lista rows:
    for set_result in all_sets_results:
        rows.extend(set_result)
        
    return rows

# Para executar (se estiver fora de uma função async existente):
rows = asyncio.run(main_processor(sets))

# Se já estiver dentro de uma função async, basta fazer:
rows = await main_processor(sets)

