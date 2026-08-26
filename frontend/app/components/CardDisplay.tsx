
import { PokemonCard } from '@/app/lib/pokemon';
import Image from 'next/image';

interface CardDisplayProps {
  card: PokemonCard;
  similarity?: number;
}

export default function CardDisplay({ card, similarity }: CardDisplayProps) {
  return (
    <div className="bg-[#fffdf7] rounded-xl shadow-lg overflow-hidden border border-[#2b2517]/15 hover:shadow-xl transition-shadow duration-300">
      <div className="relative aspect-[2.5/3.5] w-full bg-[#f3e9d2]">
        <Image
          src={card.images.large}
          alt={card.name}
          fill
          className="object-contain p-4"
          sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
        />
        {similarity !== undefined && (
          <div className="absolute top-2 right-2 bg-black/70 text-white text-xs font-mono px-2 py-1 rounded-full backdrop-blur-sm">
            {(similarity * 100).toFixed(1)}% Match
          </div>
        )}
      </div>
      <div className="p-4 space-y-2">
        <div className="flex justify-between items-start">
          <div>
            <h3 className="text-lg font-bold text-[#292318]">{card.name}</h3>
            <p className="text-sm text-[#6b6252]">{card.supertype} - {card.subtypes.join(', ')}</p>
          </div>
          <span className="text-xs font-mono bg-[#f3e9d2] px-2 py-1 rounded text-[#6b6252]">
            {card.number}/{card.set.printedTotal}
          </span>
        </div>
        
        <div className="flex items-center gap-2 text-sm text-[#6b6252]">
          <span className="font-medium">Set:</span>
          <div className="flex items-center gap-1">
            {card.set.images.symbol && (
              <div className="relative w-4 h-4">
                <Image src={card.set.images.symbol} alt="Set Symbol" fill className="object-contain" unoptimized />
              </div>
            )}
            <span>{card.set.name}</span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs text-[#6b6252] mt-2 pt-2 border-t border-[#2b2517]/15">
          <div>
            <span className="block font-medium text-[#292318]">Artist</span>
            {card.artist || 'Unknown'}
          </div>
          <div>
            <span className="block font-medium text-[#292318]">Rarity</span>
            {card.rarity || 'Common'}
          </div>
        </div>
        
        {card.tcgplayer?.prices?.holofoil?.market && (
           <div className="mt-2 text-sm font-medium text-emerald-600">
             ${card.tcgplayer?.prices?.holofoil?.market?.toFixed(2)} (Market)
           </div>
        )}
        {card.tcgplayer?.prices?.normal?.market && !card.tcgplayer?.prices?.holofoil?.market && (
           <div className="mt-2 text-sm font-medium text-emerald-600">
             ${card.tcgplayer?.prices?.normal?.market?.toFixed(2)} (Market)
           </div>
        )}
      </div>
    </div>
  );
}
