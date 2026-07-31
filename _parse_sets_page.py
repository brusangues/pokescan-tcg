import re
from pathlib import Path

# Arquivo da página de edições
content = Path(r'C:\Models\hermes\cache\web\www.ligapokemon.com.br-8804474451.md').read_text()

# Extrair todos: ed=SIGLA seguido pelo nome
# Padrão: ed=SIGLA) seguido por [Nome do Set](...
matches = re.findall(r'ed=(\w+)\)\s*\n(?:.*?\n)*?\[([^\]]+)\]\(https://www\.ligapokemon\.com\.br/\?view=cards/search', content)

liga_sets = {}
for sigla, nome in matches:
    if sigla not in liga_sets:
        liga_sets[sigla] = nome.strip()

print(f'Sets na Liga: {len(liga_sets)}')
print()

# Mapeamento manual TCGdex → Liga
# Baseado no conhecimento dos sets e seus nomes
manual = {
    # Sets que ja temos no mapping atual
    # … (preservar existentes)
    
    # NOVOS: sets que nao estavam mapeados
    'dp1': 'DP1',      # Space-Time Creation
    'dp2': 'DP2',      # Secret of the Lakes
    'dp3': 'DP3',      # Shining Darkness / DP3
}

# Ver quais siglas existem na Liga
sets_procurados = ['DP1', 'DP2', 'DP3', 'DP4', 'DP5', 'DPt-P', 'DP-P', 'GHDPt', 'PHDPt', 'DHDPt']
for s in sets_procurados:
    if s in liga_sets:
        print(f'  {s}: {liga_sets[s]}')
    else:
        print(f'  {s}: NÃO ENCONTRADO')