import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#fbf4e6]">
      <div className="text-center space-y-4">
        <h1 className="text-6xl font-bold text-gray-300">404</h1>
        <p className="text-[#6b6252]">Página não encontrada</p>
        <Link href="/" className="text-[#d40b2e] hover:underline text-sm">Voltar ao início</Link>
      </div>
    </div>
  );
}
