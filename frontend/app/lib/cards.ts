/** Constrói a URL de detalhe da carta a partir dos campos do CSV escorado. */
export function cardLink(card: {
  nome_en?: string;
  nEN?: string;
  nome?: string;
  sSigla?: string;
  sigla?: string;
}): string {
  const nome = card.nome_en || card.nEN || card.nome || '';
  const sigla = card.sSigla || card.sigla || '';
  const cleanNome = (nome || '').split('(')[0].trim();
  return `/card?nome=${encodeURIComponent(cleanNome)}&sigla=${encodeURIComponent(sigla)}`;
}

/**
 * Link direto para a página da carta na Liga Pokémon.
 * Padrão observado: ?view=cards/card&card={nEN}&ed={sSigla}&num={num}
 */
export function ligaLink(card: {
  nEN?: string;
  sSigla?: string;
  sNumber?: string;
  num?: string;
}): string {
  const nEN = card.nEN || '';
  const sigla = card.sSigla || '';
  const num = card.num || card.sNumber || '';
  if (!nEN || !sigla) return '';
  const params = new URLSearchParams({
    view: 'cards/card',
    card: nEN,
    ed: sigla,
    num,
  });
  return `https://www.ligapokemon.com.br/?${params.toString()}`;
}