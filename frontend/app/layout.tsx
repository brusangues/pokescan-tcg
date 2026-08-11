import type {Metadata} from 'next';
import './globals.css'; // Global styles

export const metadata: Metadata = {
  title: 'PokéScan TCG',
  description: 'Identify Pokémon cards using AI vision and build your collection.',
};

export default function RootLayout({children}: {children: React.ReactNode}) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
