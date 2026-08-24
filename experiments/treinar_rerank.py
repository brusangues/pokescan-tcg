"""treinar_rerank.py — CatBoost re-ranker sobre pares (query, candidato).

Dataset: experiments/rerank_pares.json (detecção × top-5; target=correto).
Features do PAR: cos_full, cos_centro, hsv, rank, margem_full, margem_centro.

Validação LEAVE-ONE-FOTO-OUT com GRUPOS DE FOLHA física (fotos repetidas da
mesma folha ficam juntas — sem vazamento entre treino/teste):
  g_sylveon    = {20260822_115216, 20260822_115424, 20260822_115601}
  g_prim       = {20260822_115504, 20260822_115615}

Métrica: acerto@1 após re-rank por fold + agregado; compara ao baseline 74%.
"""
import json
import numpy as np
from pathlib import Path
from catboost import CatBoostClassifier, Pool

BASE = Path(__file__).resolve().parent.parent
PARES = BASE / 'experiments' / 'rerank_pares.json'

FOLHAS = {}
for f in ['20260822_115216', '20260822_115424', '20260822_115601']:
    FOLHAS[f] = 'folha_sylveon'
for f in ['20260822_115504', '20260822_115615']:
    FOLHAS[f] = 'folha_primarina'

FEATS = ['cos_full', 'cos_centro', 'hsv_f', 'rank', 'margem_full', 'margem_centro']


def linha(cand, det):
    return [
        cand['cos_full'],
        cand['cos_centro'],
        cand['hsv'] if cand['hsv'] is not None else np.nan,
        float(cand['rank']),
        det['margem_full'],
        det['margem_centro'],
    ]


def main():
    pares = json.loads(PARES.read_text(encoding='utf-8'))
    # monta X/y/grupos por detecção
    X, y, g, det_ids = [], [], [], []
    for det in pares:
        folha = FOLHAS.get(det['foto'].replace('.jpg', ''), det['foto'])
        for c in det['top5']:
            X.append(linha(c, det)); y.append(1 if c['correto'] else 0)
            g.append(folha); det_ids.append((det['foto'], det['quad']))
    X = np.array(X, dtype=np.float32); y = np.array(y)
    print(f'{len(X)} pares | positivos {y.sum()} ({100*y.mean():.0f}%)')

    def acc_baseline(mask):
        """acerto@1 pelo cos_full nas detecções do mask."""
        hits = tot = 0
        seen = set()
        for i in np.where(mask)[0]:
            k = det_ids[i]
            if k in seen: continue
            rows = [j for j in np.where(mask)[0] if det_ids[j] == k]
            best = max(rows, key=lambda j: X[j][0])  # cos_full
            seen.add(k); tot += 1
            hits += int(y[best])
        return hits, tot

    def acc_modelo(model, mask):
        hits = tot = 0
        proba = model.predict_proba(X[mask])[:, 1]
        idxs = np.where(mask)[0]
        seen = set()
        for local, j in enumerate(idxs):
            k = det_ids[j]
            if k in seen: continue
            rows_local = [l for l, jj in enumerate(idxs) if det_ids[jj] == k]
            best = max(rows_local, key=lambda l: proba[l])
            seen.add(k); tot += 1
            hits += int(y[idxs[best]])
        return hits, tot

    grupos = sorted(set(g))
    print(f'grupos de folha ({len(grupos)}): {grupos}')
    res_b, res_m = [], []
    detalhe = []
    for gt in grupos:
        te = np.array([x == gt for x in g])
        tr = ~te
        if y[tr].sum() < 10 or te.sum() == 0:
            continue
        tr_pool = Pool(X[tr], y[tr], feature_names=FEATS)
        model = CatBoostClassifier(iterations=300, depth=4, learning_rate=0.05,
                                   loss_function='Logloss', verbose=False,
                                   auto_class_weights='Balanced')
        model.fit(tr_pool)
        hb, tb = acc_baseline(te)
        hm, tm = acc_modelo(model, te)
        res_b.append((hb, tb)); res_m.append((hm, tm))
        imp = sorted(zip(FEATS, model.get_feature_importance()), key=lambda t: -t[1])[:3]
        detalhe.append((gt, f'base {hb}/{tb}', f'modelo {hm}/{tm}', imp))
        print(f'  TESTE {gt:22s}: baseline {hb}/{tb} ({100*hb/max(tb,1):.0f}%) | modelo {hm}/{tm} ({100*hm/max(tm,1):.0f}%) | top feats {imp}')
    B = sum(h for h,_ in res_b); BT = sum(t for _,t in res_b)
    M = sum(h for h,_ in res_m); MT = sum(t for _,t in res_m)
    print(f'\n=== AGREGADO LOFO ===')
    print(f'baseline : {B}/{BT} ({100*B/BT:.1f}%)')
    print(f'catboost : {M}/{MT} ({100*M/MT:.1f}%)')
    delta = 100*M/MT - 100*B/BT
    print(f'delta    : {delta:+.1f}pp')
    # modelo final com tudo (para inspeção de importância global)
    mfull = CatBoostClassifier(iterations=300, depth=4, learning_rate=0.05,
                               loss_function='Logloss', verbose=False,
                               auto_class_weights='Balanced')
    mfull.fit(Pool(X, y, feature_names=FEATS))
    print('\nimportância global:', sorted(zip(FEATS, mfull.get_feature_importance()), key=lambda t:-t[1]))
    mfull.save_model(str(BASE/'experiments'/'rerank_catboost.cbm'))
    json.dump({'baseline': [B, BT], 'catboost': [M, MT],
               'por_grupo': [{'grupo': d[0], 'baseline': d[1], 'modelo': d[2]} for d in detalhe]},
              open(BASE/'experiments'/'rerank_lofo_resultado.json','w'), indent=1)

if __name__ == '__main__':
    main()