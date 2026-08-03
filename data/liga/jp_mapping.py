"""Mapeamento de edicoes japonesas → nome EN (pokemontcg.io set id).
Base: dados da Liga (sSigla) mapeados para o conjunto EN equivalente."""
# sigla da liga → set id no pokemontcg.io (revisado, sem IDs japoneses)
JP_TO_EN_SET: dict[str, str] = {
    # Scarlet & Violet era
    'SV1S': 'sv1', 'SV1W': 'sv1',  # Scarlet/Violet ex → base SV
    'SV2D': 'sv2', 'SV2P': 'sv2',  # Clay Burst/Snow Hazard → Paldea Evolved
    'SV3':  'sv3',  # Ruler of the Black Flame → Obsidian Flames
    'SV3A': 'sv3pt5',  # Raging Surf → 151
    'SV4M': 'sv4', 'SV4K': 'sv4',  # Future / Ancient Roar → Paradox Rift
    'SV5M': 'sv5', 'SV5K': 'sv5',  # Cyber Judge / Wild Force → Temporal Forces
    'SV6R': 'sv6', 'SV6Q': 'sv6',  # Transformation Mask / Night Wanderer → Twilight Masquerade
    'SV6A': 'sv6pt5',  # Night Wanderer → Shrouded Fable
    'SV7R': 'sv7', 'SV7Q': 'sv7',  # Stellar Crown → Stellar Crown
    'SV8P': 'sv8', 'SV8Q': 'sv8',  # Paradise Dragona → Surging Sparks
    'SV8A': 'sv8pt5',  # Super Electric Breaker → Prismatic Evolution
    'SV9P': 'sv9', 'SV9Q': 'sv9',  # Time Gazer × Space Juggler → Journey Together
    'SV9A': 'sv9pt5',  # Heat Wave Arena → Destined Rivals
    'SV10P': 'sv10',
    # Sword & Shield — álbuns principais
    's1H': 'swsh1', 's1W': 'swsh1',
    's2R': 'swsh2', 's2W': 'swsh2',
    's3R': 'swsh3', 's3W': 'swsh3',
    's3A': 'swsh3pt5',  # Legendary Heartbeat → Champion's Path
    's4R': 'swsh4', 's4W': 'swsh4',
    's4A': 'swsh4pt5',  # Shining Fates
    's5R': 'swsh5', 's5I': 'swsh5',
    's6R': 'swsh6', 's6I': 'swsh6',
    's6A': 'swsh6pt5',  # Eevee Heroes → Evolving Skies
    's7R': 'swsh7', 's7I': 'swsh7',
    's8R': 'swsh8', 's8I': 'swsh8',
    's9R': 'swsh9', 's9I': 'swsh9',
    's10T': 'swsh10', 's10K': 'swsh10',
    's11R': 'swsh11', 's11K': 'swsh11',
    's12R': 'swsh12', 's12K': 'swsh12',
    's12A': 'swsh12pt5',  # VSTAR Universe → Crown Zenith
    # Sun & Moon
    'SM1': 'sm1', 'SM2': 'sm2', 'SM3': 'sm3', 'SM4': 'sm4',
    'SM5': 'sm5', 'SM6': 'sm6', 'SM7': 'sm7', 'SM8': 'sm8',
    'SM9': 'sm9', 'SM10': 'sm10', 'SM11': 'sm11', 'SM12': 'sm12',
    # XY
    'XY8': 'xy8', 'XY9': 'xy9', 'XY10': 'xy10', 'XY11': 'xy11',
    'XY12': 'xy12',
}