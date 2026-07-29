"""
pokemon_popularity.py
=====================
Gera score de popularidade pra cada Pokémon usando dados TCGdex.

Lógica:
  - card_count: quantas cartas diferentes esse Pokémon tem (mais cartas = mais popular)
  - set_count: quantos sets diferentes ele aparece
  - gen_boost: bônus pra Pokémon de gerações antigas (Gen 1 tem mais apelo nostálgico)
  - Score final normalizado 0-100
"""

import re, json, math
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).parent / 'data'
POP_PATH = DATA_DIR / 'pokemon_popularity.json'

# Gerações por Pokédex number
def gen_from_dex(n):
    if n is None: return 9
    if n <= 151: return 1
    if n <= 251: return 2
    if n <= 386: return 3
    if n <= 493: return 4
    if n <= 649: return 5
    if n <= 721: return 6
    if n <= 809: return 7
    if n <= 898: return 8
    return 9

GEN_MULTIPLIER = {1: 1.5, 2: 1.3, 3: 1.2, 4: 1.15, 5: 1.1, 6: 1.05, 7: 1.0, 8: 1.0, 9: 1.0}

# Pokémon conhecidos como extremamente populares (boost manual)
LEGENDARY_BOOST = {
    'Charizard', 'Pikachu', 'Mewtwo', 'Mew', 'Gengar', 'Rayquaza',
    'Eevee', 'Umbreon', 'Espeon', 'Sylveon', 'Leafeon', 'Glaceon', 'Vaporeon', 'Jolteon', 'Flareon',
    'Lucario', 'Greninja', 'Blastoise', 'Venusaur', 'Celebi', 'Jirachi',
    'Mimikyu', 'Gardevoir', 'Lugia', 'Ho-Oh', 'Gyrados',
    'Dragonite', 'Arcanine', 'Snorlax', 'Lapras', 'Aerodactyl',
    'Deoxys', 'Darkrai', 'Arceus', 'Dialga', 'Palkia', 'Giratina',
    'Zekrom', 'Reshiram', 'Kyurem', 'Kyogre', 'Groudon',
    'Necrozma', 'Zacian', 'Zamazenta', 'Eternatus',
    'Lechonk', 'Tinkaton',
}


def extract_base_name(card_name):
    """Extrai o nome base do Pokémon (remove variantes)."""
    name = str(card_name).strip()
    # Remove sufixo após espaço + variante (ex: "Charizard-GX", "Charizard V")
    # Mas mantém nomes compostos como "Mega Charizard X"
    name = re.sub(r'\s+[-–—]\s*.*$', '', name)  # "Something - form"
    name = re.sub(r'\s+(EX|ex|GX|V|VMAX|VSTAR|V-UNION|BREAK|TAG TEAM|Prism Star|Radiant|Terapagos|ex|Tera|δ|Δ|SP|Crystal|Gold Star|★|LV\.\w+|lvl\.\w+|Lv\.\w+)$', '', name)
    name = re.sub(r'\s+\(.*?\)', '', name)  # "(something)"
    name = re.sub(r'\s*\([^)]*\)', '', name)  # Caso esteja grudado
    name = name.strip()
    return name if name else card_name


def extract_pokedex_from_name(name, card_data):
    """Tenta achar o Pokédex number pra um nome, procurando nos dados."""
    # Primeiro tenta match exato
    for c in card_data:
        en = c.get('name', c.get('nEN', ''))
        pt = c.get('nPT', '')
        if en == name or pt == name:
            dex = c.get('dexId', [])
            if dex:
                return dex[0]
    # Fallback: cai no parse pelo id
    return None


def compute_popularity(card_data):
    """
    card_data: lista de dicts de cartas TCGdex (com name, dexId, setId, etc.)
    Retorna dict: {base_name: score_0_100}
    """
    # Agrupar por nome base
    cards_per_pokemon = defaultdict(list)
    sets_per_pokemon = defaultdict(set)
    dex_per_pokemon = {}
    
    for c in card_data:
        en = c.get('name', c.get('nEN', ''))
        base = extract_base_name(en)
        cards_per_pokemon[base].append(c)
        
        set_id = c.get('set', {}).get('id', c.get('set_id', ''))
        if set_id:
            sets_per_pokemon[base].add(set_id)
        
        if base not in dex_per_pokemon:
            dex = c.get('dexId', c.get('pokedex_number', None))
            if dex is not None and not (isinstance(dex, float) and math.isnan(dex)):
                if isinstance(dex, list) and dex:
                    dex_per_pokemon[base] = dex[0]
                elif isinstance(dex, (int, float)):
                    dex_per_pokemon[base] = int(dex)
    
    # Calcular scores
    raw_scores = {}
    for base in cards_per_pokemon:
        card_count = len(cards_per_pokemon[base])
        set_count = len(sets_per_pokemon.get(base, set()))
        dex = dex_per_pokemon.get(base)
        gen = gen_from_dex(dex)
        
        # Score bruto
        score = math.log1p(card_count) * 3 + math.log1p(set_count) * 2
        
        # Bônus de geração (Gen 1 mais popular)
        score *= GEN_MULTIPLIER.get(gen, 1.0)
        
        # Bônus lendário/popular
        if base in LEGENDARY_BOOST:
            score *= 1.5
        
        raw_scores[base] = score
    
    # Normalizar 0-100
    if not raw_scores:
        return {}
    
    scores = list(raw_scores.values())
    min_s, max_s = min(scores), max(scores)
    if max_s > min_s:
        normalized = {k: round((v - min_s) / (max_s - min_s) * 100, 1) for k, v in raw_scores.items()}
    else:
        normalized = {k: 50.0 for k in raw_scores}
    
    return normalized


def load_or_compute(force=False):
    """Carrega cache ou computa do zero."""
    if POP_PATH.exists() and not force:
        with open(POP_PATH) as f:
            return json.load(f)
    
    # Procurar dados das cartas TCGdex
    sets_dir = DATA_DIR / 'sets'
    card_data = []
    if sets_dir.exists():
        for f in sorted(sets_dir.glob('*.json')):
            try:
                with open(f) as fh:
                    data = json.load(fh)
                    cards = data.get('cards', [])
                    set_id = data.get('id', f.stem)
                    for c in cards:
                        c['set_id'] = set_id
                    card_data.extend(cards)
            except:
                pass
    
    # Fallback: usar snapshots
    if not card_data:
        import pandas as pd
        snapshots = sorted(Path('data/monitoring').glob('snapshot_*.csv'))
        if snapshots:
            df = pd.read_csv(snapshots[-1])
            for _, row in df.iterrows():
                card_data.append({
                    'name': row.get('name_en', row.get('name', '')),
                    'nEN': row.get('name_en', row.get('name', '')),
                    'nPT': row.get('name', ''),
                    'pokedex_number': row.get('pokedex_number'),
                    'set_id': row.get('set_id'),
                })
    
    if not card_data:
        print('⚠️  Nenhum dado TCGdex encontrado. Use --force pra computar.')
        return {}
    
    pop = compute_popularity(card_data)
    
    POP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(POP_PATH, 'w') as f:
        json.dump(pop, f, indent=2, ensure_ascii=False)
    
    print(f'✅ Popularidade computada: {len(pop)} Pokémon')
    return pop


def get_popularity(name):
    """Retorna score de popularidade pra um nome de carta."""
    pop = load_or_compute()
    base = extract_base_name(name)
    return pop.get(base, 10.0)  # default baixo pra desconhecidos


def show_top(n=30):
    """Mostra os Pokémon mais populares."""
    pop = load_or_compute()
    sorted_pop = sorted(pop.items(), key=lambda x: -x[1])
    print(f'\n🏆 Top {n} Pokémon mais populares:')
    for i, (name, score) in enumerate(sorted_pop[:n], 1):
        stars = '⭐' if score > 80 else ('★' if score > 60 else '·')
        print(f'  {i:3d}. {name:25s} {score:5.1f} {stars}')
    print(f'  ... {len(pop) - n} Pokémon restantes')


if __name__ == '__main__':
    import sys
    if '--force' in sys.argv:
        load_or_compute(force=True)
    elif '--top' in sys.argv:
        show_top()
    else:
        pop = load_or_compute()
        print(f'📊 {len(pop)} Pokémon com score de popularidade')
        show_top(15)
