
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

export async function fetchCards(query: string = 'page=1&pageSize=5', retries = 2, delay = 10): Promise<PokemonCard[]> {
  for (let i = 0; i < retries; i++) {
    try {
      // Use local API route to avoid CORS/Network issues
      const response = await fetch(`/api/cards?${query}`);
      
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        if (!response.ok) {
           const errorData = await response.json().catch(() => ({}));
           console.warn(`Attempt ${i + 1} /api/cards?${query} failed: ${response.status} ${JSON.stringify(errorData)}`);
           if (i === retries - 1) throw new Error(`Failed to fetch cards: ${response.status}`);
        } else {
           const data = await response.json();
           return data.data || [];
        }
      } else {
        // Received HTML or non-JSON (likely "Starting Server..." page)
        const text = await response.text();
        console.warn(`Attempt ${i + 1} received non-JSON response (likely server starting): ${text.substring(0, 50)}...`);
        if (i === retries - 1) throw new Error(`Expected JSON but got ${contentType}`);
      }
    } catch (error) {fetchCards
      console.error(`Attempt ${i + 1} /api/cards?${query} error:`, error);
      if (i === retries - 1) return [];
    }
    
    // Wait before retrying
    await new Promise(resolve => setTimeout(resolve, delay * (i + 1)));
  }
  throw new Error('Failed to fetch cards after multiple attempts');
}
