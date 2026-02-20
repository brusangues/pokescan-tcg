
import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.toString();
  
  try {
    const apiUrl = `https://api.pokemontcg.io/v2/cards?${query}`;
    console.log('Fetching from Pokemon API:', apiUrl);
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      'User-Agent': 'PokeScan-TCG/1.0',
    };
    
    if (process.env.POKEMON_TCG_API_KEY) {
      headers['X-Api-Key'] = process.env.POKEMON_TCG_API_KEY;
      console.log('Using API key for Pokemon TCG API');
    }

    const response = await fetch(apiUrl, { headers });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`Pokemon API Error: ${response.status} ${response.statusText}`, errorText);
      return NextResponse.json(
        { error: `Pokemon API responded with ${response.status}: ${response.statusText}` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Proxy error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch data from Pokemon API' },
      { status: 500 }
    );
  }
}
