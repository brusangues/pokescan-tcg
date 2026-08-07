#!/usr/bin/env python
"""
build_static_data.py — gera os JSONs estáticos do frontend (public/data/)
para o export 100% estático (GitHub Pages).

Lê os mesmos dados que as API routes (data/scored/*.csv, cache ptcg,
set mapping, git log) e produz public/data/*.json com EXATAMENTE os
mesmos shapes, para os componentes só trocarem a URL do fetch.

Uso: python script/build_static_data.py [--out DIR]
"""
import csv
import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCORED = REPO / 'data' / 'scored'
PTCG_CACHE = REPO / 'data' / 'ptcg_cards_cache.json'
SET_MAPPING = REPO / 'data' / 'liga' / 'liga_set_sigla_ptcg.json'
SET_MAPPING_FALLBACK = REPO / 'data' / 'liga' / 'liga_set_sigla.json'
EDICOES = REPO / 'data' / 'liga' / 'edicoes_liga.json'


def _card_id(r: dict) -> str:
    """Chave canônica da carta: '{idE}-{lang}-{sN}' (lang: en|jp).

    Usa a coluna card_id quando presente (CSV novo); senão deriva de idE/sN/is_jp
    (CSVs antigos) — assim o histórico acumulado casa entre dias.
    """
    cid = (r.get('card_id') or '').strip()
    if cid:
        return cid
    eid = str(r.get('idE') or '').strip()
    sN = str(r.get('sN') or r.get('num') or '').strip().lstrip('0') or '0'
    if not eid:
        return ''
    lang = 'jp' if str(r.get('is_jp', '')).lower() in ('true', '1') else 'en'
    return f'{eid}-{lang}-{sN}'
ABLATIONS = REPO / 'experiments' / 'ablation_results.csv'
OUT = Path(sys.argv[sys.argv.index('--out') + 1]) if '--out' in sys.argv else REPO / 'frontend' / 'public' / 'data'


def parse_scored_csv(path: Path) -> list:
    """Réplica EXATA de parseScoredCSV (app/lib/scored.ts)."""
    out = []
    with open(path, encoding='utf-8', newline='') as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            if not (r.get('oportunidade') and r.get('real_ref') and r.get('pred_ref')):
                continue
            def f(v, default=float('nan')):
                try:
                    return float(str(v).replace(',', '.'))
                except (TypeError, ValueError):
                    return default
            real, pred, upside = f(r.get('real_ref')), f(r.get('pred_ref')), f(r.get('upside_pct'))
            if not all(math.isfinite(x) for x in (real, pred, upside)):
                continue
            out.append({
                'nome': r.get('nPT') or r.get('name') or r.get('nome') or r.get('nEN') or 'Unknown',
                'sigla': r.get('sSigla') or r.get('set_id') or '',
                'setNome': r.get('ed_sNome') or r.get('ed_sNomePortugues') or r.get('set_name') or '',
                'real': real,
                'pred': pred,
                'upside': upside,
                'oportunidade': r.get('oportunidade'),
                'iCO': int(float(r.get('iCO') or r.get('iCO_real') or '0')),
                'moeda': r.get('moeda') or 'R$',
                'liga_id': r.get('liga_id') or '',
                'card_id': _card_id(r),
                'nEN': r.get('nEN') or '',
                'sNumber': r.get('sNumber') or '',
                'num': r.get('num') or '',
                'fonte': r.get('fonte') or '',
                'is_jp': r.get('is_jp', '').lower() in ('true', '1'),
            })
    return out


def scored_files(prefix: str) -> list:
    return sorted([p for p in SCORED.glob(f'{prefix}_*.csv')], reverse=True)


def hits_payload() -> dict:
    files = scored_files('scored_hits')
    if not files:
        raise SystemExit('Nenhum scored_hits_*.csv encontrado')
    latest = files[0]
    mtime = datetime.fromtimestamp(latest.stat().st_mtime).astimezone().isoformat()

    dias = []
    dia_map = {}
    for f in files:
        m = f.name.rsplit('_', 2)
        if len(m) != 3:
            continue
        data = m[1]
        dia_map.setdefault(data, []).append(f.name)
    for data in sorted(dia_map, reverse=True):
        anos, mes, dia = data[:4], data[4:6], data[6:8]
        dias.append({'data': data, 'label': f'{dia}/{mes}/{anos}',
                     'arquivos': sorted(dia_map[data], reverse=True)})

    cards = sorted(parse_scored_csv(latest), key=lambda c: -c['upside'])
    sub = [c for c in cards if c['oportunidade'] == '🔥 Subvalorizada' and c['real'] >= 5]
    infla = sorted([c for c in cards if c['oportunidade'] == '💀 Inflacionada'], key=lambda c: c['upside'])
    return {
        'arquivo': latest.name,
        'ultimaAtualizacao': mtime,
        'total': len(cards),
        'dias': dias,
        'subvalorizadas': sub,
        'inflacionadas': infla[:20],
        'todas': cards,
    }


def snapshots_payload() -> dict:
    files = scored_files('scored_snapshot')
    if not files:
        raise SystemExit('Nenhum scored_snapshot_*.csv encontrado')
    latest = files[0]
    mtime = datetime.fromtimestamp(latest.stat().st_mtime).astimezone().isoformat()

    disponiveis = []
    for f in files:
        m = f.name.rsplit('_', 2)
        if len(m) != 3:
            continue
        data = m[1]
        time = f'{m[2][:2]}:{m[2][2:4]}'
        try:
            with open(f, encoding='utf-8', newline='') as fh:
                line_count = sum(1 for _ in fh) - 1
        except Exception:
            line_count = 0
        disponiveis.append({
            'arquivo': f.name,
            'label': f'{data[6:8]}/{data[4:6]}/{data[:4]} {time}',
            'data': data,
            'cartas': line_count,
        })

    semanas = []
    for a in disponiveis:
        d = datetime(int(a['data'][:4]), int(a['data'][4:6]), int(a['data'][6:8]))
        week_label = f'Semana de {d.strftime("%d de %b")}'
        if semanas and semanas[-1]['label'] == week_label:
            semanas[-1]['arquivos'].append(a)
        else:
            semanas.append({'label': week_label, 'arquivos': [a]})

    cards = parse_scored_csv(latest)
    sub = sorted([c for c in cards if c['oportunidade'] == '🔥 Subvalorizada' and c['real'] >= 5],
                 key=lambda c: -c['upside'])
    infla = sorted([c for c in cards if c['oportunidade'] == '💀 Inflacionada'], key=lambda c: c['upside'])
    justo = len([c for c in cards if c['oportunidade'] == '⚖️ Preço Justo'])

    set_counts = {}
    for c in cards:
        if c['sigla']:
            set_counts[c['sigla']] = set_counts.get(c['sigla'], 0) + 1
    sets = sorted([{'sigla': s, 'count': n} for s, n in set_counts.items()],
                  key=lambda x: -x['count'])[:10]

    return {
        'arquivo': latest.name,
        'ultimaAtualizacao': mtime,
        'total': len(cards),
        'disponiveis': disponiveis,
        'semanas': semanas,
        'subvalorizadas': sub,
        'inflacionadas': infla[:20],
        'justo': justo,
        'todas': cards,
        'sets': sets,
    }


def dashboard_payload() -> dict:
    hits_files = scored_files('scored_hits')
    snap_files = scored_files('scored_snapshot')
    hits_data = parse_scored_csv(hits_files[0]) if hits_files else []
    snap_data = parse_scored_csv(snap_files[0]) if snap_files else []

    def meta(files, data):
        if not files:
            return None
        mtime = datetime.fromtimestamp(files[0].stat().st_mtime).astimezone().isoformat()
        return {'arquivo': files[0].name, 'data': mtime}

    all_cards = hits_data + snap_data
    buckets = {}
    for c in all_cards:
        u = max(-500, min(500, c['upside']))
        b = math.floor(u / 10) * 10
        key = f'{b} a {b + 10}%'
        buckets[key] = buckets.get(key, 0) + 1
    distribuicao = sorted([{'range': k, 'count': v} for k, v in buckets.items()],
                          key=lambda x: int(x['range'].split(' ')[0]))

    sub_hits = sorted([c for c in hits_data if c['oportunidade'] == '🔥 Subvalorizada' and c['real'] >= 5],
                      key=lambda c: -c['upside'])[:10]
    sub_snap = sorted([c for c in snap_data if c['oportunidade'] == '🔥 Subvalorizada' and c['real'] >= 5],
                      key=lambda c: -c['upside'])[:10]
    infla_hits = sorted([c for c in hits_data if c['oportunidade'] == '💀 Inflacionada'],
                        key=lambda c: c['upside'])[:10]
    infla_snap = sorted([c for c in snap_data if c['oportunidade'] == '💀 Inflacionada'],
                        key=lambda c: c['upside'])[:10]

    set_counts = {}
    for c in hits_data:
        if c['sigla']:
            set_counts[c['sigla']] = set_counts.get(c['sigla'], 0) + 1
    sets = sorted([{'sigla': s, 'count': n} for s, n in set_counts.items()],
                  key=lambda x: -x['count'])[:10]

    return {
        'hits': {
            'meta': meta(hits_files, hits_data),
            'total': len(hits_data),
            'subvalorizadas': len([c for c in hits_data if c['oportunidade'] == '🔥 Subvalorizada' and c['real'] >= 5]),
            'inflacionadas': len([c for c in hits_data if c['oportunidade'] == '💀 Inflacionada']),
            'justo': len([c for c in hits_data if c['oportunidade'] == '⚖️ Preço Justo']),
            'topOportunidades': sub_hits,
            'topInflacionadas': infla_hits,
        },
        'snapshot': {
            'meta': meta(snap_files, snap_data),
            'total': len(snap_data),
            'subvalorizadas': len([c for c in snap_data if c['oportunidade'] == '🔥 Subvalorizada']),
            'inflacionadas': len([c for c in snap_data if c['oportunidade'] == '💀 Inflacionada']),
            'topOportunidades': sub_snap,
            'topInflacionadas': infla_snap,
        },
        'distribuicao': distribuicao,
        'sets': sets,
    }


DETALHE_FIELDS = ['id', 'name', 'supertype', 'subtypes', 'hp', 'types', 'evolvesFrom',
                  'evolvesTo', 'rarity', 'artist', 'number', 'set', 'images', 'flavorText',
                  'attacks', 'abilities', 'weaknesses', 'resistances', 'retreatCost']


def _enxuga_card(c: dict) -> dict:
    """Campos que o /card renderiza, sem os dados que ele não mostra."""
    card = {k: c.get(k) for k in DETALHE_FIELDS}
    if card.get('attacks'):
        card['attacks'] = card['attacks'][:8]
    tcg = c.get('tcgplayer')
    if tcg:
        prices = {}
        for variant, p in (tcg.get('prices') or {}).items():
            if not p:
                continue
            prices[variant] = {k: p.get(k) for k in ('market', 'low', 'high') if p.get(k) is not None}
        card['tcgplayer'] = {'updatedAt': tcg.get('updatedAt'),
                             'prices': prices} if prices else None
    cm = c.get('cardmarket')
    if cm:
        p = cm.get('prices') or {}
        card['cardmarket'] = {
            'updatedAt': cm.get('updatedAt'),
            'prices': {k: p.get(k) for k in ('averageSellPrice', 'lowPrice', 'trendPrice', 'avg30')
                       if p.get(k) is not None},
        }
    return card


def cards_basico() -> list:
    """Catálogo enxuto p/ lookup (mesmo shape do cards.json do scanner)."""
    raw = json.loads(PTCG_CACHE.read_text(encoding='utf-8'))
    return [{
        'id': c['id'],
        'n': c.get('name') or '',
        's': c.get('set', {}).get('id') or '',
        'sn': c.get('set', {}).get('name') or '',
        'num': c.get('number') or '',
        'r': c.get('rarity') or '',
        'p': (c.get('tcgplayer', {}).get('prices', {}) or {}).get('holofoil', {}).get('market')
             or (c.get('tcgplayer', {}).get('prices', {}) or {}).get('normal', {}).get('market'),
        'img': c.get('images', {}).get('small') or c.get('images', {}).get('large'),
    } for c in raw]


def cards_detalhe_chunks() -> dict:
    """Detalhe completo dividido em chunks por primeira letra do nome.
    index.json: {id: letra}; {letra}.json: lista de cartas detalhadas."""
    raw = json.loads(PTCG_CACHE.read_text(encoding='utf-8'))
    chunks: dict[str, list] = {}
    index: dict[str, str] = {}
    for c in raw:
        letra = (c.get('name') or '?')[0].lower()
        if not ('a' <= letra <= 'z'):
            letra = '0'
        chunks.setdefault(letra, []).append(_enxuga_card(c))
        index[c['id']] = letra
    return {'index': index, 'chunks': chunks}


def scored_latest_payload() -> list:
    files = [f for f in SCORED.glob('scored_*.csv') if f.name.startswith(('scored_hits_', 'scored_snapshot_'))]
    files = sorted(files, reverse=True)
    all_cards = []
    for f in files:
        if f.name.startswith('scored_hits_'):
            all_cards.extend(parse_scored_csv(f))
            break
    for f in files:
        if f.name.startswith('scored_snapshot_'):
            all_cards.extend(parse_scored_csv(f))
            break
    return all_cards


def historico_payload() -> dict:
    """Séries por card_id (chave canônica idE-lang-sN) e por nome+sigla — mesmo filtro do /api/historico."""
    files = sorted([f for f in SCORED.glob('scored_*.csv')
                    if f.name.startswith(('scored_hits_', 'scored_snapshot_'))])
    por_liga = {}
    por_nome = {}
    for f in files:
        m = f.name.split('_')
        if len(m) < 3:
            continue
        tipo = m[1]
        data = m[2]
        data_iso = f'{data[:4]}-{data[4:6]}-{data[6:8]}'
        try:
            cards = parse_scored_csv(f)
        except Exception:
            continue
        for c in cards:
            if not c['real'] or c['real'] <= 0:
                continue
            ponto = {
                'data': data_iso,
                'real': round(c['real'] * 100) / 100,
                'pred': round(c['pred'] * 100) / 100 if c['pred'] else None,
                'moeda': c['moeda'] or 'R$',
                'tipo': tipo,
            }
            if c['card_id']:
                serie = por_liga.setdefault(c['card_id'], {})
                serie[f'{data}_{tipo}'] = ponto
            nome_key = (c['nEN'] or c['nome'] or '').lower()
            if nome_key:
                sigla = c['sigla'] or ''
                serie = por_nome.setdefault(nome_key, {}).setdefault(sigla, {})
                serie[f'{data}_{tipo}'] = ponto

    def ordena(d):
        return sorted(d.values(), key=lambda p: p['data'])
    return {
        'porLiga': {k: ordena(v) for k, v in por_liga.items()},
        'porNome': {n: {s: ordena(v) for s, v in siglas.items()} for n, siglas in por_nome.items()},
    }


def set_map_inv() -> dict:
    """sigla→set ptcg E edid→set ptcg (o front resolve /card por ambos).

    Usa o edicoes_liga.json (índice canônico) quando disponível — cobre PAR/OBF/MEG/…
    que o mapping antigo não tinha — e complementa com o mapping ptcg→sigla.
    """
    inv = {}
    if EDICOES.exists():
        ed = json.loads(EDICOES.read_text(encoding='utf-8'))
        for eid, info in ed.items():
            if info.get('set'):
                inv[str(eid)] = info['set']            # '439' → 'sv4'
                inv[info['sigla'].lower()] = info['set']  # 'par' → 'sv4'
    try:
        raw = json.loads(SET_MAPPING.read_text(encoding='utf-8'))
    except Exception:
        raw = json.loads(SET_MAPPING_FALLBACK.read_text(encoding='utf-8'))
    for ptcg, liga in raw.items():
        inv.setdefault(str(liga).lower(), ptcg)
    return inv


def changelog_payload() -> dict:
    def get_commits():
        try:
            res = subprocess.run(
                ['git', 'log', '--date=iso', '--pretty=format:%h|%aI|%an|%s', '-n', '60'],
                cwd=REPO, capture_output=True, text=True, timeout=30)
            if res.returncode != 0:
                return []
            commits = []
            for line in res.stdout.strip().split('\n'):
                if not line:
                    continue
                parts = line.split('|', 3)
                if len(parts) < 4:
                    continue
                hash_, date, author, subject = parts
                m = subject.split(':', 1)
                type_ = m[0].split('(')[0] if m else 'other'
                scope = None
                if m and '(' in m[0]:
                    scope = m[0].split('(', 1)[1].rstrip(')')
                commits.append({'hash': hash_, 'date': date, 'author': author,
                                'subject': subject, 'type': type_, 'scope': scope})
            return commits
        except Exception:
            return []

    def get_ablations():
        if not ABLATIONS.exists():
            return []
        rows = []
        try:
            with open(ABLATIONS, encoding='utf-8', newline='') as fh:
                for r in csv.DictReader(fh):
                    label = r.get('label', '')
                    parts = label.split('/')
                    modelo = parts[0] if len(parts) > 0 else ''
                    agg = parts[1] if len(parts) > 1 else ''
                    pca_raw = parts[2] if len(parts) > 2 else ''
                    try:
                        pca = int(pca_raw.replace('pca', '')) if pca_raw else None
                    except ValueError:
                        pca = None
                    try:
                        rows.append({
                            'label': label,
                            'modelo': modelo,
                            'agregacao': agg,
                            'pca': pca,
                            'mae': float(r.get('mae')),
                            'r2': float(r.get('r2')),
                            'n_train': int(r.get('n_train')),
                            'n_test': int(r.get('n_test')),
                        })
                    except (TypeError, ValueError):
                        continue
        except Exception:
            return []
        return rows

    commits = get_commits()
    ablations = get_ablations()
    melhor = max(ablations, key=lambda a: a['r2']) if ablations else None
    return {
        'commits': commits,
        'ablations': ablations,
        'melhor': melhor,
        'total_commits': len(commits),
        'atualizado_em': datetime.now().astimezone().isoformat(),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    payloads = {
        'hits.json': hits_payload,
        'snapshots.json': snapshots_payload,
        'dashboard.json': dashboard_payload,
        'cards.json': cards_basico,
        'scored_latest.json': scored_latest_payload,
        'historico.json': historico_payload,
        'set_map.json': set_map_inv,
        'changelog.json': changelog_payload,
    }
    total = 0
    for name, fn in payloads.items():
        data = fn()
        path = OUT / name
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        size = path.stat().st_size
        total += size
        print(f'{name:24s} {size/1e6:7.2f} MB  ({len(data):,} itens)')

    # Detalhe em chunks por letra do nome
    detalhe_dir = OUT / 'carddetail'
    detalhe_dir.mkdir(exist_ok=True)
    chunks_data = cards_detalhe_chunks()
    index_path = detalhe_dir / 'index.json'
    index_path.write_text(json.dumps(chunks_data['index'], ensure_ascii=False), encoding='utf-8')
    total += index_path.stat().st_size
    print(f'carddetail/index.json     {index_path.stat().st_size/1e6:7.2f} MB')
    for letra, cards in sorted(chunks_data['chunks'].items()):
        path = detalhe_dir / f'{letra}.json'
        path.write_text(json.dumps(cards, ensure_ascii=False), encoding='utf-8')
        size = path.stat().st_size
        total += size
        print(f'carddetail/{letra}.json    {size/1e6:7.2f} MB ({len(cards):,})')
    print(f'TOTAL: {total/1e6:.2f} MB → {OUT}')


if __name__ == '__main__':
    main()
