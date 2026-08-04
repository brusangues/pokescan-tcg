
import Scanner from '@/app/components/Scanner';
import NavBar from '@/app/components/NavBar';

export default function ScannerPage() {
  return (
    <main className="min-h-screen bg-slate-50 pb-20">
      <NavBar />

      {/* Hero */}
      <div className="bg-indigo-900 text-white py-14 px-4 mb-10 relative overflow-hidden">
        <div className="absolute inset-0 opacity-10 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-white via-transparent to-transparent"></div>
        <div className="max-w-4xl mx-auto text-center space-y-4 relative z-10">
          <h2 className="text-4xl font-bold tracking-tight sm:text-5xl">
            Identifique cartas na hora
          </h2>
          <p className="text-indigo-200 text-lg max-w-2xl mx-auto leading-relaxed">
            Tire uma foto de qualquer carta Pokémon para identificá-la. O modelo de visão roda
            direto no seu navegador — nada é enviado para servidores.
          </p>
        </div>
      </div>

      {/* Main Content */}
      <div className="px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        <Scanner />
      </div>
    </main>
  );
}