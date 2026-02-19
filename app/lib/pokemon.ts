
export interface PokemonCard {
  id: string;
  name: string;
  supertype: string;
  subtypes: string[];
  hp?: string;
  types?: string[];
  evolvesFrom?: string;
  images: {
    small: string;
    large: string;
  };
  set: {
    id: string;
    name: string;
    series: string;
    printedTotal: number;
    total: number;
    legalities: {
      unlimited: string;
    };
    ptcgoCode?: string;
    releaseDate: string;
    updatedAt: string;
    images: {
      symbol: string;
      logo: string;
    };
  };
  number: string;
  artist?: string;
  rarity?: string;
  flavorText?: string;
  nationalPokedexNumbers?: number[];
  legalities: {
    unlimited: string;
  };
  regulationMark?: string;
  tcgplayer?: {
    url: string;
    updatedAt: string;
    prices?: {
      normal?: {
        low: number;
        mid: number;
        high: number;
        market: number;
        directLow?: number;
      };
      holofoil?: {
        low: number;
        mid: number;
        high: number;
        market: number;
        directLow?: number;
      };
      reverseHolofoil?: {
        low: number;
        mid: number;
        high: number;
        market: number;
        directLow?: number;
      };
      [key: string]: any;
    };
  };
}

export async function fetchCards(query: string = 'page=1&pageSize=20'): Promise<PokemonCard[]> {
  try {
    const response = await fetch(`/api/cards?${query}`);
    if (!response.ok) {
      throw new Error('Failed to fetch cards');
    }
    const data = await response.json();
    return data.data;
  } catch (error) {
    console.error('Error fetching cards:', error);
    return [];
  }
}
