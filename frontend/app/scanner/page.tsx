
import Scanner from '@/app/components/Scanner';
import NavBar from '@/app/components/NavBar';
import { Search, Camera } from 'lucide-react';

export default function ScannerPage() {
  return (
    <main className="min-h-screen bg-[#fbf4e6] pb-20">
      <NavBar />

      {/* Hero — mesma linguagem da landing: papel escuro + tinta, sem gradiente */}
      <div className="bg-[#f3e9d2] border-b-2 border-[#2b2517] text-[#292318] py-12 px-4 mb-10">
        <div className="max-w-4xl mx-auto space-y-4">
          <span className="badge-poke">Scanner &amp; busca</span>
          <h2 className="font-display text-4xl font-bold tracking-tight sm:text-5xl leading-tight">
            Escaneie a carta{' '}
            <span className="relative inline-block">
              <span className="relative z-10">ou busque pelo nome</span>
              <span className="absolute inset-x-0 bottom-1 h-3 bg-[#f2c11e]/70 -rotate-1" aria-hidden />
            </span>
          </h2>
          <p className="text-[#6b6252] text-lg max-w-2xl leading-relaxed">
            Tire uma foto e a identificação acontece direto no seu navegador — nada é enviado
            para servidores. Prefere digitar? A busca por nome, número ou coleção funciona
            na hora.
          </p>
          <div className="flex flex-wrap gap-x-6 gap-y-2 pt-1 text-sm font-semibold text-[#6b6252]">
            <span className="inline-flex items-center gap-2">
              <Camera className="w-4 h-4 text-[#d40b2e]" /> Foto da carta (uma ou várias)
            </span>
            <span className="inline-flex items-center gap-2">
              <Search className="w-4 h-4 text-[#d40b2e]" /> Busca por texto instantânea
            </span>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        <Scanner />
      </div>
    </main>
  );
}
