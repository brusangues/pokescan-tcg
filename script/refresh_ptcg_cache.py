"""
script/refresh_ptcg_cache.py
============================
Refresh INCREMENTAL do cache de cartas pokemontcg.io
(data/ptcg_cards_cache.json) — rodado no cron semanal (liga-snapshot.sh).

Estratégia (eficiente, ~2-4 requests):
1. Busca os SETS atuais da API (fetch_all_sets) e identifica os que têm
   data de lançamento mais recente que o cache local.
2. Para cada set novo/atualizado, busca as cartas (fetch_set_cards).
3. Mescla com o cache existente (substitui cartas do mesmo id).
4. Salva o cache consolidado + backup do anterior.

Seguro: idempotente, incremental, preserva cartas antigas. Não precisa
de API key (pokemontcg.io é gratuita com rate limit).

Uso:
  python script/refresh_ptcg_cache.py            # refresh incremental
  python script/refresh_ptcg_cache.py --full     # re-baixa tudo (lento)
"""

import json, sys, argparse, shutil, time
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
DATA_DIR = BASE_DIR / 'data'
CACHE_PATH = DATA_DIR / 'ptcg_cards_cache.json'
BACKUP_DIR = DATA_DIR / 'cache_backups'

# Janela de atualização: sets lançados/atualizados nos últimos N dias
# também são re-buscados (pricing embutido muda com o mercado)
RECENT_DAYS = 30


def load_existing():
    if not CACHE_PATH.exists():
        print('  Cache não existe — será criado do zero.')
        return {}, {}
    cards = json.loads(CACHE_PATH.read_text(encoding='utf-8'))
    by_id = {c['id']: c for c in cards}
    # set_id -> data de lançamento mais recente conhecida no cache
    set_dates = {}
    for c in cards:
        sid = (c.get('set') or {}).get('id', '')
        rd = (c.get('set') or {}).get('releaseDate', '')
        if sid and rd and (sid not in set_dates or rd > set_dates[sid]):
            set_dates[sid] = rd
    return by_id, set_dates


def parse_data(s):
    """Normaliza datas da API ('2026/01/30') e ISO ('2026-08-05') → date."""
    if not s:
        return None
    s = str(s).strip()
    for fmt in ('%Y/%m/%d', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def refresh_incremental(args):
    import ptcg_io

    print(f'📦 Refresh incremental do cache ptcg...')
    by_id, set_dates_known = load_existing()
    print(f'  Cache atual: {len(by_id)} cartas | {len(set_dates_known)} sets')

    # 1. Sets atuais da API (com retry — rate limit gratuito)
    print('  Buscando lista de sets...')
    sets = []
    for tentativa in range(4):
        sets = ptcg_io.fetch_all_sets()
        if sets:
            break
        espera = 10 * (tentativa + 1)
        print(f'  ⚠️ Lista de sets vazia (tentativa {tentativa+1}/4). Aguardando {espera}s...')
        time.sleep(espera)
    if not sets:
        print('  ❌ API de sets indisponível após retries. Abortando (cache intacto).')
        sys.exit(1)
    print(f'  API tem {len(sets)} sets')

    # Data de corte: hoje - RECENT_DAYS (re-busca sets lançados nessa janela)
    corte = datetime.now().date() - timedelta(days=RECENT_DAYS)

    novos = []
    sets_info = {}
    for s in sets:
        sid = s.get('id', '')
        sets_info[sid] = s
        rd = parse_data(s.get('releaseDate', ''))
        conhecido = parse_data(set_dates_known.get(sid))
        # Re-busca se: set desconhecido OU data de release mais nova que o
        # conhecido OU lançado nos últimos RECENT_DAYS (pricing muda)
        if rd and rd >= corte:
            novos.append(sid)
        elif not conhecido:
            novos.append(sid)
        elif rd and conhecido and rd > conhecido:
            novos.append(sid)

    print(f'  Sets para atualizar: {len(novos)}')
    if args.dry_run:
        print('  [dry-run] Não tocando o cache.')
        return 0
    if not novos:
        print('  ✅ Cache já está atualizado. Nada a fazer.')
        return 0

    # 2. Busca cartas dos sets alvo (com retry — rate limit gratuito)
    total_novas = 0
    for i, sid in enumerate(novos):
        cards_set = []
        for tentativa in range(4):
            try:
                cards_set = ptcg_io.fetch_set_cards(sid)
            except Exception as e:
                print(f'  ⚠️ Erro no set {sid}: {e}')
                cards_set = []
            if cards_set:
                break
            espera = 10 * (tentativa + 1)
            print(f'  ⚠️ Set {sid} vazio (tentativa {tentativa+1}/4). Aguardando {espera}s...')
            time.sleep(espera)
        if not cards_set:
            print(f'  ❌ Set {sid} sem cartas após retries. Pulando.')
            continue
        s = sets_info.get(sid, {})
        for c in cards_set:
            # Anexa _set (mesmo formato do fetch_all_cards_global)
            c['_set'] = {
                'set_id': sid,
                'set_name': s.get('name', ''),
                'set_series': s.get('series', ''),
                'set_release_date': s.get('releaseDate', ''),
                'set_printed_total': s.get('printedTotal', 0) or s.get('total', 0),
            }
            by_id[c['id']] = c  # substitui/insere
        total_novas += len(cards_set)
        print(f'  [{i+1}/{len(novos)}] {sid}: {len(cards_set)} cartas')

    # 3. Salva com backup
    if total_novas > 0:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        if CACHE_PATH.exists():
            shutil.copy2(CACHE_PATH, BACKUP_DIR / f'ptcg_cards_cache_{ts}.json')
            print(f'  💾 Backup: cache_backups/ptcg_cards_cache_{ts}.json')

        lista = list(by_id.values())
        lista.sort(key=lambda c: c.get('id', ''))
        CACHE_PATH.write_text(json.dumps(lista, ensure_ascii=False), encoding='utf-8')
        print(f'  ✅ Cache salvo: {len(lista)} cartas (+{total_novas} novas/atualizadas)')
    return total_novas


def refresh_full():
    """Re-baixa tudo (fallback)."""
    import ptcg_io
    print('📦 Refresh COMPLETO do cache (lento, ~82 requests)...')
    cards = ptcg_io.fetch_all_cards_global()
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    if CACHE_PATH.exists():
        shutil.copy2(CACHE_PATH, BACKUP_DIR / f'ptcg_cards_cache_{ts}.json')
    CACHE_PATH.write_text(json.dumps(cards, ensure_ascii=False), encoding='utf-8')
    print(f'  ✅ Cache salvo: {len(cards)} cartas')
    return len(cards)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--full', action='store_true', help='Re-baixa tudo')
    parser.add_argument('--dry-run', action='store_true', help='Só mostra o que seria atualizado')
    args = parser.parse_args()

    if args.full:
        refresh_full()
    else:
        refresh_incremental(args)


if __name__ == '__main__':
    main()
