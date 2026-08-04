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