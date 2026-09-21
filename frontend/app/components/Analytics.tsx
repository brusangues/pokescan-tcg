'use client';
/**
 * Analytics.tsx — tag do Google Analytics 4 (gtag.js).
 *
 * Dois cuidados que evitam relatório sujo:
 *  1. Só entra no build PUBLICADO (`NEXT_PUBLIC_BASE_PATH` definido, que é o que
 *     o deploy usa). Build local de validação fica sem tag nenhuma.
 *  2. Mesmo no publicado, só envia hit quando o host é o do GitHub Pages —
 *     abrir o `out/` servido localmente não conta.
 *
 * O site é uma SPA estática: o `gtag('config')` manda a primeira page_view, mas
 * navegação client-side (Next Link) NÃO gera page_view sozinha — por isso o
 * efeito abaixo manda as seguintes, pulando a primeira para não duplicar.
 */
import { useEffect, useRef } from 'react';
import { usePathname } from 'next/navigation';
import Script from 'next/script';

const ID = process.env.NEXT_PUBLIC_GA_ID || 'G-E6CYP4RSLH';
const PUBLICADO = !!process.env.NEXT_PUBLIC_BASE_PATH;

export default function Analytics() {
  const pathname = usePathname();
  const primeira = useRef(true);

  useEffect(() => {
    if (!PUBLICADO) return;
    if (primeira.current) {
      primeira.current = false;
      return;
    }
    if (!/brusangues\.github\.io$/.test(window.location.hostname)) return;
    const g = (window as unknown as { gtag?: (...a: unknown[]) => void }).gtag;
    if (!g) return;
    g('event', 'page_view', {
      page_path: window.location.pathname + window.location.search,
      page_location: window.location.href,
      page_title: document.title,
    });
  }, [pathname]);

  if (!PUBLICADO) return null;

  return (
    <>
      <Script
        src={`https://www.googletagmanager.com/gtag/js?id=${ID}`}
        strategy="afterInteractive"
      />
      <Script id="ga4-init" strategy="afterInteractive">
        {`(function () {
  if (!/brusangues\\.github\\.io$/.test(location.hostname)) return;
  window.dataLayer = window.dataLayer || [];
  function gtag() { dataLayer.push(arguments); }
  window.gtag = gtag;
  gtag('js', new Date());
  gtag('config', '${ID}', { anonymize_ip: true });
})();`}
      </Script>
    </>
  );
}
