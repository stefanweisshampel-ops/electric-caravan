#!/usr/bin/env python3
"""Testauswertung der Mobilithek-Abrufe (nur Zusammenfassung, keine Rohdaten).

Liest probe/raw/<name>.json (vom Workflow abgerufen) und probe/raw/<name>.status
und schreibt probe/summary.json + probe/summary.txt:
  - Größe, HTTP-Status, oberste Schlüssel
  - wie oft "applicableForVehicles" vorkommt und welche vehicleType-Werte
  - ob Stellplatz-Abmessungen ("dimension") angegeben sind
  - ein gekürztes Beispiel für Fahrzeugeignung und für Preisangaben
"""
import json, os, re, sys
from collections import Counter

RAW = sys.argv[1] if len(sys.argv) > 1 else 'probe/raw'
OUT = sys.argv[2] if len(sys.argv) > 2 else 'probe'

PRICE_KEY = re.compile(r'(rate|price|tariff|amount|cost)', re.I)


def walk(o, path=''):
    if isinstance(o, dict):
        yield path, o
        for k, v in o.items():
            yield from walk(v, path + '/' + k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, path + '[]')


def short(o, n=1500):
    s = json.dumps(o, ensure_ascii=False)
    return s if len(s) <= n else s[:n] + ' …'


def analyse(name, data):
    keys = Counter()
    vtypes = Counter()
    applicable = 0
    dims = 0
    ex_vehicle = ex_dim = ex_price = None
    price_paths = Counter()
    sites = 0
    for path, d in walk(data):
        for k in d.keys():
            keys[k] += 1
        if 'applicableForVehicles' in d:
            applicable += 1
            for vc in d.get('applicableForVehicles') or []:
                vt = vc.get('vehicleType') if isinstance(vc, dict) else None
                if isinstance(vt, list):
                    for x in vt:
                        vtypes[x.get('value') if isinstance(x, dict) else str(x)] += 1
                elif isinstance(vt, dict):
                    vtypes[vt.get('value')] += 1
                elif vt:
                    vtypes[str(vt)] += 1
            if ex_vehicle is None:
                ex_vehicle = {'path': path, 'applicableForVehicles': d['applicableForVehicles']}
        if 'dimension' in d and d['dimension']:
            dims += 1
            if ex_dim is None:
                ex_dim = {'path': path, 'dimension': d['dimension']}
        for k in d.keys():
            if PRICE_KEY.search(k):
                price_paths[path + '/' + k] += 1
                if ex_price is None:
                    ex_price = {'path': path, k: d[k]}
        if re.search(r'energyInfrastructureSite\[\]$', path):
            sites += 1
    return {
        'sites': sites,
        'applicableForVehicles': applicable,
        'vehicleTypes': vtypes.most_common(20),
        'dimension': dims,
        'topKeys': keys.most_common(60),
        'pricePaths': price_paths.most_common(15),
        'exampleVehicle': short(ex_vehicle) if ex_vehicle else None,
        'exampleDimension': short(ex_dim, 600) if ex_dim else None,
        'examplePrice': short(ex_price) if ex_price else None,
    }


def main():
    res = {}
    for fn in sorted(os.listdir(RAW)):
        if not fn.endswith('.status'):
            continue
        name = fn[:-7]
        status = open(os.path.join(RAW, fn)).read().strip()
        body = os.path.join(RAW, name + '.json')
        r = {'status': status}
        if os.path.exists(body):
            r['bytes'] = os.path.getsize(body)
            try:
                data = json.load(open(body, encoding='utf-8'))
                r['topLevel'] = list(data.keys())[:10] if isinstance(data, dict) else type(data).__name__
                r.update(analyse(name, data))
            except Exception as e:  # kein JSON → Anfang zeigen (Fehlermeldungen)
                r['parseError'] = str(e)[:200]
                r['head'] = open(body, 'rb').read(400).decode('utf-8', 'replace')
        res[name] = r
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(os.path.join(OUT, 'summary.json'), 'w'), ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, 'summary.txt'), 'w') as f:
        for name, r in res.items():
            f.write(f"== {name}: HTTP {r.get('status')}, {r.get('bytes', 0)} Bytes, Standorte {r.get('sites', '?')}, "
                    f"Fahrzeugeignung {r.get('applicableForVehicles', '?')}, Abmessungen {r.get('dimension', '?')}\n")
            if r.get('vehicleTypes'):
                f.write(f"   vehicleType: {r['vehicleTypes']}\n")
            if r.get('parseError'):
                f.write(f"   Fehler: {r['parseError']} | {r.get('head', '')[:200]!r}\n")
    print(open(os.path.join(OUT, 'summary.txt')).read())


if __name__ == '__main__':
    main()
