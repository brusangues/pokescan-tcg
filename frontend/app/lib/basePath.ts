/**
 * Base path para o deploy estático (GitHub Pages serve em /pokescan-tcg/).
 * Em dev local fica vazio (sem prefixo). O next.config.ts também usa
 * NEXT_PUBLIC_BASE_PATH para o basePath/assetPrefix — build de deploy:
 *   NEXT_PUBLIC_BASE_PATH=/pokescan-tcg npm run build
 */
export function getBasePath(): string {
  return process.env.NEXT_PUBLIC_BASE_PATH || '';
}
