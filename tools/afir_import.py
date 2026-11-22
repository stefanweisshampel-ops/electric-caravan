#!/usr/bin/env python3
"""AFIR-Daten der Betreiber (Mobilithek, DATEX II V3) -> data/DE/afir.json

Aufruf:  python3 tools/afir_import.py <rohdaten-ordner> [data/DE/sites.json] [data/DE/afir.json]

Der Rohdaten-Ordner enthält je Abo <name>.json (Namen wie in tools/mobilithek.json,
z. B. enbw-stat.json, ewe-dyn.json). Ergebnis je Standort unserer Karte:

  key: [tag, nacht, startgebühr, blockier-hinweis, quelle, anhänger, stellplatzlänge]

  tag/nacht   Ad-hoc-Preis €/kWh inkl. MwSt. (tagsüber bzw. günstigster Zeitraum)
  anhänger    1, wenn der Betreiber den Standort für Fahrzeuge mit Anhänger/Wohnwagen meldet
"""
import json, math, os, re, sys, unicodedata
from collections import defaultdict
from datetime import date

RAW = sys.argv[1] if len(sys.argv) > 1 else 'probe/raw'
SITES = sys.argv[2] if len(sys.argv) > 2 else 'data/DE/sites.json'
OUT = sys.argv[3] if len(sys.argv) > 3 else 'data/DE/afir.json'
HERE = os.path.dirname(os.path.abspath(__file__))

# Quellen: Name im Abo -> Anzeige, Lizenz, Betreiber-Prüfung gegen unseren Betreibernamen
SOURCES = [
    {'k': 'enbw', 'label': 'EnBW', 'lic': 'CC BY 4.0, EnBW AG', 'op': r'enbw'},
    {'k': 'tesla', 'label': 'Tesla', 'lic': 'Open Data, Tesla Germany GmbH', 'op': r'tesla'},
    {'k': 'ewe', 'label': 'EWE Go', 'lic': 'Open Data, EWE Go GmbH', 'op': r'\bewe\b'},
    {'k': 'vw', 'label': 'Volkswagen Group Charging (Elli)', 'lic': 'Open Data, Volkswagen Group Charging', 'op': r'volkswagen|\belli\b'},
    {'k': 'eclearing', 'label': 'e-clearing.net', 'lic': 'Open Data, e-clearing.net', 'op': None},
]
SRC_IDX = {s['k']: i for i, s in enumerate(SOURCES)}

TRAILER_TYPES = {'carWithTrailer', 'carWithCaravan', 'vehicleWithTrailer', 'vehicleWithCaravan',
                 'lightCommercialVehicleWithTrailer', 'caravan', 'trailer'}
TRAILER_EU = {'o1', 'o2', 'o3', 'o4'}   # EU-Fahrzeugklasse O = Anhänger
VAT = 19.0
NOON = 14 * 60  # Referenzzeit für den Tagespreis: 14:00


# ---------- Hilfen ----------
def walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


def val(x):
    """{"value": "dc"} -> "dc"."""
    return x.get('value') if isinstance(x, dict) else x


def coords(o):
    lr = o.get('locationReference') or {}
    for k in ('locPointLocation', 'locAreaLocation'):
        c = (lr.get(k) or {}).get('coordinatesForDisplay')
        if c and c.get('latitude') is not None:
            return float(c['latitude']), float(c['longitude'])
        p = ((lr.get(k) or {}).get('pointByCoordinates') or {}).get('pointCoordinates')
        if p and p.get('latitude') is not None:
            return float(p['latitude']), float(p['longitude'])
    return None


def km(a, b, c, d):
    r = math.radians
    x = r(d - b) * math.cos(r((a + c) / 2))
    return 6371 * math.hypot(x, r(c - a))


def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', ' ', s)


STOP = {'gmbh', 'co', 'kg', 'ag', 'mbh', 'und', 'der', 'die', 'das', 'stadtwerke', 'energie', 'energy',
        'e', 'v', 'se', 'ug', 'gesellschaft', 'mobility', 'ladenetz', 'germany', 'deutschland', 'service',
        'services', 'charging', 'versorgung', 'netz', 'emobility', 'mobil', 'de'}


def tokens(s):
    return {t for t in norm(s).split() if len(t) >= 4 and t not in STOP}


def minutes(t):
    """'08:00:00+01:00' -> 480"""
    m = re.match(r'(\d{1,2}):(\d{2})', t or '')
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def org_names(site):
    out = []
    for role in ('operator', 'owner'):
        o = (site.get(role) or {}).get('afacAnOrganisation') or {}
        for k in ('name', 'legalName'):
            for v in (o.get(k) or {}).get('values', []):
                out.append(v.get('value', ''))
    return ' '.join(out)


# ---------- Preise ----------
def gross(e):
    v = float(e.get('value') or 0)
    if e.get('taxIncluded') is False:
        v *= 1 + float(e.get('taxRate') or VAT) / 100
    return v


def day_periods(e):
    """Liste von (start, ende) in Minuten, falls tageszeitabhängig."""
    out = []
    for vp in ((e.get('overallPeriod') or {}).get('validPeriod') or []):
        for tp in vp.get('recurringTimePeriodOfDay') or []:
            a, b = minutes(tp.get('startTimeOfPeriod')), minutes(tp.get('endTimeOfPeriod'))
            if a is not None and b is not None:
                out.append((a, b if b > a else 24 * 60))
    return out


def eval_prices(prices):
    """energyPrice-Liste -> dict(tag, nacht, gebuehr, block) oder None."""
    kwh = [e for e in prices or [] if val(e.get('priceType')) == 'pricePerKWh' and float(e.get('value') or 0) > 0]
    if not kwh:
        return None
    base = [gross(e) for e in kwh if not day_periods(e)]
    timed = [(day_periods(e), gross(e)) for e in kwh if day_periods(e)]
    day = None
    for per, g in timed:
        if any(a <= NOON < b for a, b in per):
            day = g if day is None else max(day, g)
    if day is None:
        day = max(base) if base else max(g for _, g in timed)
    low = min([g for _, g in timed] + base)
    night = low if low < day - 0.005 else None
    fee = None
    block = None
    for e in prices:
        t = val(e.get('priceType'))
        g = gross(e)
        if t == 'flatRate' and g > 0.005:
            fee = g if fee is None else max(fee, g)
        if t == 'pricePerMinute' and g > 0.005:
            fm = (e.get('timeBasedApplicability') or {}).get('fromMinute') or 0
            block = (int(fm), g)
    return {'tag': day, 'nacht': night, 'gebuehr': fee, 'block': block}


def rate_prices(rate):
    pol = val(rate.get('ratePolicy'))
    if pol and pol != 'adHoc':
        return None
    return rate.get('energyPrice') or []


# ---------- Statische Daten ----------
def parse_stat(data, src, dyn):
    """Ergibt je Betreiber-Standort: dict(lat, lon, names, points=[(kw, preis)], trailer, len)."""
    all_rates = {}
    for d in walk(data):
        for ee in d.get('electricEnergy') or [] if isinstance(d.get('electricEnergy'), list) else []:
            for r in ee.get('energyRate') or []:
                if r.get('idG'):
                    all_rates.setdefault(r['idG'], r)
    out = []
    for d in walk(data):
        sl = d.get('energyInfrastructureSite')
        if not isinstance(sl, list):
            continue
        for site in sl:
            c = coords(site)
            stations = site.get('energyInfrastructureStation') or []
            if not c:
                for st in stations:
                    c = coords(st)
                    if c:
                        break
            if not c:
                continue
            local = {}
            for x in walk(site):
                for ee in x.get('electricEnergy') or [] if isinstance(x.get('electricEnergy'), list) else []:
                    for r in ee.get('energyRate') or []:
                        if r.get('idG'):
                            local.setdefault(r['idG'], r)
            upd = dyn.get(site.get('idG'), {})

            def rates_of(holder):
                res = []
                for ee in holder.get('electricEnergy') or []:
                    for r in ee.get('energyRate') or []:
                        res.append(r)
                    for ref in ee.get('energyRateByReference') or []:
                        r = local.get(ref.get('idG')) or all_rates.get(ref.get('idG'))
                        if r:
                            res.append(r)
                return res

            points = []
            for st in stations:
                st_rates = rates_of(st)
                for rp in st.get('refillPoint') or []:
                    cp = rp.get('aegiElectricChargingPoint') or rp.get('aegiRefillPoint') or {}
                    if val(cp.get('currentType')) not in (None, 'dc'):
                        continue
                    pw = [float(x) for x in cp.get('availableChargingPower') or [] if x]
                    pw += [float(c2.get('maxPowerAtSocket') or 0) for c2 in cp.get('connector') or []]
                    p = max(pw) if pw else 0
                    kw = p / 1000 if p > 1000 else p
                    if val(cp.get('currentType')) is None and kw < 50:
                        continue
                    best = None
                    # Reihenfolge: dynamische Aktualisierung am Ladepunkt, dann je Tarif, dann statisch
                    cand = []
                    if cp.get('idG') in upd.get('points', {}):
                        cand.append(upd['points'][cp['idG']])
                    for r in rates_of(cp) or st_rates:
                        rid = r.get('idG')
                        if rid in upd.get('rates', {}):
                            cand.append(upd['rates'][rid])
                        else:
                            pr = rate_prices(r)
                            if pr:
                                cand.append(pr)
                    for pr in cand:
                        ev = eval_prices(pr)
                        if ev and (best is None or ev['tag'] < best['tag']):
                            best = ev
                    points.append((kw, best))
            trailer = 0
            length = None
            for x in walk(site):
                for vc in x.get('applicableForVehicles') or [] if isinstance(x.get('applicableForVehicles'), list) else []:
                    vts = vc.get('vehicleType') or []
                    vts = vts if isinstance(vts, list) else [vts]
                    if any(val(v) in TRAILER_TYPES for v in vts):
                        trailer = 1
                    ext = (vc.get('comVehicleCharacteristicsExtensionG') or {})
                    ext = ext.get('VehicleCharacteristicsExtended') or ext.get('vehicleCharacteristicsExtended') or {}
                    if any(val(v) in TRAILER_EU for v in ext.get('euVehicleCategory') or []):
                        trailer = 1
                dim = x.get('dimension')
                if isinstance(dim, dict) and dim.get('length'):
                    try:
                        length = max(length or 0, float(dim['length']))
                    except (TypeError, ValueError):
                        pass
            out.append({'lat': c[0], 'lon': c[1], 'names': org_names(site), 'points': points,
                        'trailer': trailer, 'len': length, 'src': src})
    return out


# ---------- Dynamische Daten (Preis-Aktualisierungen) ----------
def parse_dyn(data):
    """site-idG -> {'points': {punkt-idG: energyPrice}, 'rates': {tarif-idG: energyPrice}}"""
    res = defaultdict(lambda: {'points': {}, 'rates': {}})
    for d in walk(data):
        sl = d.get('energyInfrastructureSiteStatus')
        if not isinstance(sl, list):
            continue
        for ss in sl:
            sid = (ss.get('reference') or {}).get('idG')
            for x in walk(ss):
                for u in x.get('energyRateUpdate') or [] if isinstance(x.get('energyRateUpdate'), list) else []:
                    rid = (u.get('energyRateReference') or {}).get('idG')
                    if rid and u.get('energyPrice'):
                        res[sid]['rates'][rid] = u['energyPrice']
                for key in ('aegiElectricChargingPointStatus', 'aegiRefillPointStatus'):
                    cps = x.get(key)
                    if isinstance(cps, dict):
                        pid = (cps.get('reference') or {}).get('idG')
                        for u in cps.get('energyRateUpdate') or []:
                            if pid and u.get('energyPrice'):
                                res[sid]['points'][pid] = u['energyPrice']
    return res


# ---------- Zuordnung zu unseren Standorten ----------
def main():
    abos = json.load(open(os.path.join(HERE, 'mobilithek.json')))['abos']
    by_src = defaultdict(dict)
    for a in abos:
        k = a['name'].split('-')[0]
        by_src[k][a['art']] = os.path.join(RAW, a['name'] + '.json')

    ours = json.load(open(SITES))
    ops = ours['ops']
    grid = defaultdict(list)
    for i, r in enumerate(ours['sites']):
        grid[(round(r[0] / 0.01), round(r[1] / 0.01))].append(i)

    def key_of(r):
        return 'DE-%.4f_%.4f' % (r[0], r[1])

    result = {}
    stats = {}
    for s in SOURCES:
        files = by_src.get(s['k'], {})
        stat_f, dyn_f = files.get('stat'), files.get('dyn')
        if not stat_f or not os.path.exists(stat_f):
            stats[s['k']] = 'keine statischen Daten'
            continue
        dyn = {}
        if dyn_f and os.path.exists(dyn_f):
            try:
                dyn = parse_dyn(json.load(open(dyn_f, encoding='utf-8')))
            except Exception as e:  # dynamische Daten sind optional
                print('dyn', s['k'], 'unlesbar:', e)
        try:
            data = json.load(open(stat_f, encoding='utf-8'))
        except Exception as e:
            stats[s['k']] = 'unlesbar: %s' % e
            continue
        afir_sites = parse_stat(data, s['k'], dyn)
        n_match = n_price = n_trailer = 0
        rx = re.compile(s['op'], re.I) if s['op'] else None
        for a in afir_sites:
            gy, gx = round(a['lat'] / 0.01), round(a['lon'] / 0.01)
            best, bd = None, 0.15
            atok = tokens(a['names']) if not rx else None
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    for i in grid.get((gy + dy, gx + dx), []):
                        r = ours['sites'][i]
                        dd = km(a['lat'], a['lon'], r[0], r[1])
                        if dd >= bd:
                            continue
                        op = ops[r[2]] + ' ' + (r[3] or '')
                        if rx and not rx.search(op):
                            continue
                        if atok is not None and not (atok & tokens(op)):
                            continue
                        best, bd = i, dd
            if best is None:
                continue
            n_match += 1
            r = ours['sites'][best]
            pts = [p for p in a['points'] if p[1]]
            fast = [p for p in pts if p[0] >= 100] or [p for p in pts if p[0] >= 50]
            price = None
            if fast:
                top = max(p[0] for p in fast)
                group = [p[1] for p in fast if p[0] >= top - 1e-6] or [p[1] for p in fast]
                price = min(group, key=lambda e: e['tag'])
                n_price += 1
            n_trailer += a['trailer']
            k = key_of(r)
            rnd = lambda v: None if v is None else round(v + 1e-9, 2)
            entry = [
                rnd(price['tag']) if price else None,
                rnd(price['nacht']) if price else None,
                rnd(price['gebuehr']) if price else None,
                ([price['block'][0], rnd(price['block'][1])] if price and price['block'] else None),
                SRC_IDX[s['k']],
                a['trailer'],
                a['len'],
            ]
            old = result.get(k)
            if old:  # mehrere Betreiber-Standorte auf einem unserer Standorte: günstigsten Preis behalten
                if old[0] is not None and (entry[0] is None or old[0] <= entry[0]):
                    entry[:5] = old[:5]
                entry[5] = max(old[5], entry[5])
                entry[6] = max([x for x in (old[6], entry[6]) if x is not None], default=None)
            result[k] = entry
        stats[s['k']] = {'standorte': len(afir_sites), 'zugeordnet': n_match, 'mit_preis': n_price, 'anhaenger': n_trailer}

    out = {
        'stand': date.today().isoformat(),
        'fields': ['tag', 'nacht', 'gebuehr', 'block', 'quelle', 'anhaenger', 'laenge'],
        'src': [{'k': s['k'], 'label': s['label'], 'lic': s['lic']} for s in SOURCES],
        's': dict(sorted(result.items())),
    }
    os.makedirs(os.path.dirname(OUT) or '.', exist_ok=True)
    json.dump(out, open(OUT, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    print('Standorte mit AFIR-Angaben:', len(result))


if __name__ == '__main__':
    main()
