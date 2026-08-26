import type {Metadata} from 'next';
import {Baloo_2, Nunito} from 'next/font/google';
import './globals.css'; // Global styles

const baloo = Baloo_2({
  subsets: ['latin'],
  variable: '--font-baloo',
  weight: ['500', '600', '700', '800'],
});

const nunito = Nunito({
  subsets: ['latin'],
  variable: '--font-nunito',
  weight: ['400', '600', '700'],
});

export const metadata: Metadata = {
  title: 'PokéScan TCG',
  description: 'Identifique cartas de Pokémon TCG, confira o preço justo no mercado brasileiro e acompanhe oportunidades.',
};

export default function RootLayout({children}: {children: React.ReactNode}) {
  return (
    <html lang="pt-BR" className={`${baloo.variable} ${nunito.variable}`}>
      <body>{children}</body>
    </html>
  );
}
