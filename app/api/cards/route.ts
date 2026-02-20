
import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

// Helper function to fetch with retries and timeout
async function fetchWithRetry(
  url: string,
  headers: HeadersInit,
  maxRetries: number = 3,
  timeoutMs: number = 15000
): Promise<Response> {
  let lastError: Error | null = null;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      console.log(`Attempt ${attempt}/${maxRetries}: Fetching ${url}`);

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

      const response = await fetch(url, {
        headers,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      // If successful or client error, return immediately
      if (response.ok || (response.status >= 400 && response.status < 500)) {
        return response;
      }

      // 5xx errors (including 504) - retry
      const responseText = await response.text();
      lastError = new Error(
        `HTTP ${response.status}: ${response.statusText} - ${responseText.substring(0, 200)}`
      );

      console.warn(`Attempt ${attempt} failed: ${lastError.message}`);

      // Wait before retrying (exponential backoff)
      if (attempt < maxRetries) {
        const waitTime = Math.min(1000 * Math.pow(2, attempt - 1), 10000);
        console.log(`Waiting ${waitTime}ms before retry...`);
        await new Promise((resolve) => setTimeout(resolve, waitTime));
      }
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));

      if (lastError.name === 'AbortError') {
        lastError = new Error('Request timeout - API took too long to respond');
      }

      console.warn(`Attempt ${attempt} error: ${lastError.message}`);

      // Don't retry on abort/timeout for the last attempt
      if (attempt < maxRetries) {
        const waitTime = Math.min(1000 * Math.pow(2, attempt - 1), 10000);
        console.log(`Waiting ${waitTime}ms before retry...`);
        await new Promise((resolve) => setTimeout(resolve, waitTime));
      }
    }
  }

  throw lastError || new Error('Failed to fetch after all retries');
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.toString();

  try {
    const apiUrl = `https://api.pokemontcg.io/v2/cards?${query}`;
    console.log(`Fetching from Pokemon API: ${apiUrl}`);

    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      'User-Agent': 'PokeScan-TCG/1.0',
    };

    if (process.env.POKEMON_TCG_API_KEY) {
      headers['X-Api-Key'] = process.env.POKEMON_TCG_API_KEY;
      console.log('Using API key for Pokemon TCG API');
    }

    const response = await fetchWithRetry(apiUrl, headers, 3, 15000);

    if (!response.ok) {
      const errorText = await response.text();
      console.error(
        `Pokemon API Error: ${response.status} ${response.statusText}`,
        errorText
      );
      return NextResponse.json(
        { error: `Pokemon API responded with ${response.status}: ${response.statusText}` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : 'Unknown error occurred';
    console.error('Proxy error:', errorMessage);

    return NextResponse.json(
      {
        error: 'Failed to fetch data from Pokemon API',
        details: errorMessage,
      },
      { status: 503 }
    );
  }
}
