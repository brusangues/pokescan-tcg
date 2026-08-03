
import Scanner from '@/app/components/Scanner';
import { Sparkles, Camera, Zap, LayoutDashboard } from 'lucide-react';

export default function Home() {
  return (
    <main className="min-h-screen bg-slate-50 pb-20">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center text-white shadow-sm">
              <Sparkles className="w-5 h-5" />
            </div>
            <h1 className="text-xl font-bold text-gray-900 tracking-tight">PokéScan TCG</h1>
          </div>
          <nav className="hidden md:flex gap-6 items-center">
            <a href="/dashboard" className="flex items-center gap-2 text-sm font-medium text-gray-600 hover:text-gray-900 px-3 py-1.5 rounded-full hover:bg-gray-100 transition-colors">
              <LayoutDashboard className="w-4 h-4" />
              Dashboard
            </a>
            <a href="/hits" className="flex items-center gap-2 text-sm font-medium text-gray-600 hover:text-gray-900 px-3 py-1.5 rounded-full hover:bg-gray-100 transition-colors">
              <Zap className="w-4 h-4" />
              Hits
            </a>
            <a href="#" className="flex items-center gap-2 text-sm font-medium text-indigo-600 bg-indigo-50 px-3 py-1.5 rounded-full">
              <Camera className="w-4 h-4" />
              Scanner
            </a>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <div className="bg-indigo-900 text-white py-16 px-4 mb-12 relative overflow-hidden">
        <div className="absolute inset-0 opacity-10 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-white via-transparent to-transparent"></div>
        <div className="max-w-4xl mx-auto text-center space-y-6 relative z-10">
          <h2 className="text-4xl font-bold tracking-tight sm:text-5xl md:text-6xl">
            Identify Cards Instantly
          </h2>
          <p className="text-indigo-200 text-lg sm:text-xl max-w-2xl mx-auto leading-relaxed">
            Powered by AI Vision. Upload a photo of any Pokémon card to identify it, check prices, and add it to your digital collection.
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
