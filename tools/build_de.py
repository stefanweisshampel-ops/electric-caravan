"""Baut die Ladesäulendaten für Deutschland (Gespann-Lader).

Eingabe:  lad.json.gz  – Ladesäulenregister der Bundesnetzagentur (CC BY 4.0),
                         aufbereitet von https://github.com/ratopi/ladesaeule
          ne/*.geojson – Natural Earth 10m (gemeinfrei): roads, admin_0_countries
Ausgabe:  ../data/DE/sites.json, ../data/mw.json

Aufruf:   cd tools && python3 build_de.py
Benötigt: pip install shapely
"""
import gzip, json, math, re, collections, os
from shapely.geometry import shape, Point, LineString, MultiLineString, mapping
from shapely.ops import linemerge, unary_union
from shapely.strtree import STRtree

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
os.makedirs(os.path.join(OUT, 'DE'), exist_ok=True)
raw = json.load(gzip.open('lad.json.gz', 'rt', encoding='utf-8'))
rows = raw['data']
STAND = raw['meta']['source'].rsplit('_', 1)[-1].replace('.csv', '')  # 2026-09-01

KX = 111.32 * math.cos(math.radians(51.0))  # km per degree lon (approx for DE)
KY = 110.57

def km(a_lat, a_lon, b_lat, b_lon):
    return math.hypot((a_lat - b_lat) * KY, (a_lon - b_lon) * KX)

def fnum(x):
    try:
        return float(str(x).replace(',', '.'))
    except Exception:
        return 0.0

TRUCK_RE = re.compile(r'milence|daimler truck|truck|\blkw\b|lkw[- ]|nutzfahrzeug|park your truck|e-?lkw|schwerlast', re.I)
REST_RE = re.compile(r'autohof|rasthof|raststätte|rastanlage|rastplatz|\bT&R\b|tank ?& ?rast', re.I)

def dc_points(s):
    pts = []
    for p in s['charging'].get('points', []):
        best = 0.0
        plugs = set()
        for pl, pw in zip(p.get('plugs', []), p.get('power', [])):
            if pl.startswith('DC'):
                best = max(best, fnum(pw))
                if 'Combo' in pl: plugs.add('CCS')
                elif 'CHAdeMO' in pl: plugs.add('CHA')
                elif 'MCS' in pl: plugs.add('MCS')
        if best > 0:
            pts.append((best, plugs))
    return pts

cand = []
for s in rows:
    if s.get('status') != 'operational':
        continue
    pts = dc_points(s)
    if not pts or max(p[0] for p in pts) < 50:
        continue
    text = ' | '.join(str(x or '') for x in (s.get('operator'), s.get('display_name'), s.get('location_name'), s.get('addr', {}).get('address_extra')))
    mcs = any('MCS' in p[1] for p in pts)
    truck = mcs or bool(TRUCK_RE.search(text)) or max(p[0] for p in pts) >= 600
    cand.append({'s': s, 'pts': pts, 'truck': truck, 'text': text})

print('candidate rows', len(cand), 'truck rows', sum(c['truck'] for c in cand))

# ---- cluster rows into sites (same operator + same truck flag, within 120 m)
parent = list(range(len(cand)))
def find(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb: parent[rb] = ra

grid = collections.defaultdict(list)
CELL = 0.002
for i, c in enumerate(cand):
    g = c['s']['geo']
    grid[(round(g['lat'] / CELL), round(g['lon'] / CELL))].append(i)
for (gy, gx), idxs in grid.items():
    neigh = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            neigh += grid.get((gy + dy, gx + dx), [])
    for i in idxs:
        ci = cand[i]
        for j in neigh:
            if j <= i: continue
            cj = cand[j]
            if ci['truck'] != cj['truck']: continue
            if ci['s']['operator'] != cj['s']['operator']: continue
            if km(ci['s']['geo']['lat'], ci['s']['geo']['lon'], cj['s']['geo']['lat'], cj['s']['geo']['lon']) <= 0.12:
                union(i, j)

clusters = collections.defaultdict(list)
for i in range(len(cand)):
    clusters[find(i)].append(cand[i])
print('sites', len(clusters))

def short_op(s):
    dn = (s.get('display_name') or '').strip()
    op = (s.get('operator') or '').strip()
    name = dn or op
    return re.sub(r'\s+', ' ', name)

def clean(x):
    return re.sub(r'\s+', ' ', str(x or '')).strip()

def human(x):
    x = clean(x)
    if not x: return ''
    if re.search(r'\d{4,}', x) or x.count('_') >= 2 or (('_' in x) and (' ' not in x)):
        return ''
    if len(x) > 80: return x[:80]
    return x

sites = []
for members in clusters.values():
    lat = sum(m['s']['geo']['lat'] for m in members) / len(members)
    lon = sum(m['s']['geo']['lon'] for m in members) / len(members)
    s0 = members[0]['s']
    ops = collections.Counter(short_op(m['s']) for m in members)
    op = ops.most_common(1)[0][0]
    names = collections.Counter(human(m['s'].get('location_name')) for m in members if human(m['s'].get('location_name')))
    name = names.most_common(1)[0][0] if names else ''
    extras = collections.Counter(human(m['s']['addr'].get('address_extra')) for m in members if human(m['s']['addr'].get('address_extra')))
    extra = extras.most_common(1)[0][0] if extras else ''
    a = s0['addr']
    hn = clean(a.get('house_number'))
    street = clean(a.get('street')) + ('' if hn in ('', '0') else ' ' + hn)
    city = clean(a.get('city'))
    addr = f"{street}, {clean(a.get('postcode'))} {city}".strip(', ')
    allpts = [p for m in members for p in m['pts']]
    maxkw = int(round(max(p[0] for p in allpts)))
    n = len(allpts)
    plugs = set()
    for p in allpts: plugs |= p[1]
    pay = set()
    hours = ''
    for m in members:
        acc = m['s'].get('access', {})
        for p in acc.get('payment', []) or []:
            pay.add(p)
        if acc.get('opening_hours') and not hours:
            hours = acc['opening_hours']
    terminal = any(('credit' in p or 'debit' in p) for p in pay)
    newest = max((m['s']['charging'].get('commissioning_date') or '') for m in members)
    truck = members[0]['truck']
    text = ' '.join(m['text'] for m in members)
    rest = bool(REST_RE.search(text))
    sites.append({
        'lat': round(lat, 5), 'lon': round(lon, 5), 'op': op, 'name': name, 'addr': addr,
        'extra': extra, 'kw': maxkw, 'n': n,
        'ccs': 'CCS' in plugs, 'cha': 'CHA' in plugs, 'mcs': 'MCS' in plugs,
        'term': terminal, 'hours': '' if hours == '24/7' else hours, 'h24': hours == '24/7',
        'since': newest, 'truck': truck, 'rest': rest, 'city': city,
    })

# truck site nearby (for car sites)
truck_sites = [s for s in sites if s['truck']]
tgrid = collections.defaultdict(list)
for t in truck_sites:
    tgrid[(round(t['lat'] / 0.01), round(t['lon'] / 0.01))].append(t)
for s in sites:
    s['tnear'] = False
    if s['truck']: continue
    gy, gx = round(s['lat'] / 0.01), round(s['lon'] / 0.01)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for t in tgrid.get((gy + dy, gx + dx), []):
                if km(s['lat'], s['lon'], t['lat'], t['lon']) <= 0.4:
                    s['tnear'] = True

# ---- motorways (Natural Earth), clipped to Germany (+ ~3 km)
cs = json.load(open('ne/ne_10m_admin_0_countries.geojson'))
DE = shape([f for f in cs['features'] if f['properties'].get('ADM0_A3') == 'DEU'][0]['geometry'])
DEb = DE.buffer(0.04)
roads = json.load(open('ne/ne_10m_roads.geojson'))
segs = []
for f in roads['features']:
    p = f['properties']
    if p['type'] != 'Major Highway':
        continue
    g = shape(f['geometry'])
    if not g.intersects(DEb):
        continue
    g = g.intersection(DEb)
    if g.is_empty: continue
    lab = ' '.join(str(p.get(k) or '') for k in ('routeraw', 'label', 'label2', 'name', 'namealt'))
    A = set(re.findall(r'\bA\d+\b', lab))
    E = set(re.findall(r'\bE\d+\b', lab))
    lines = [g] if g.geom_type == 'LineString' else [l for l in getattr(g, 'geoms', []) if l.geom_type == 'LineString']
    for l in lines:
        if l.length > 0:
            segs.append({'g': l, 'A': set(A), 'E': E})

# Natural Earth often only carries the European route number (E51 ...).
# Map E routes to German A numbers where that is clear, split by region where an
# E route uses several Autobahnen. x = lon, y = lat of the segment midpoint.
def e_to_a(E, x, y):
    if 'E51' in E: return {'A9'}
    if 'E45' in E:
        if y < 48.15: return {'A93'} if y < 47.86 else {'A8'}
        if y < 49.35: return {'A9'}
        if x > 9.9 and y < 49.9: return {'A3'}
        return {'A7'}
    if 'E52' in E: return {'A8'}
    if 'E49' in E:
        if 50.4 < y < 51.45 and 11.5 < x < 12.3: return {'A9'}
        if y >= 51.45: return {'A14'}
        return set()
    if 'E56' in E: return {'A3'}
    if 'E50' in E: return {'A6'}
    if 'E37' in E: return {'A1'}
    if 'E47' in E: return {'A1'}
    if 'E34' in E: return {'A2'}
    if 'E26' in E: return {'A24'}
    if 'E28' in E: return {'A11'}
    if 'E48' in E: return {'A70'}
    if 'E53' in E: return {'A92'}
    if 'E441' in E: return {'A72'}
    if 'E451' in E: return {'A5'}
    if 'E533' in E: return {'A95'}
    if 'E35' in E: return {'A3'} if y > 50.1 else {'A5'}
    if 'E30' in E:
        if x < 8.6: return {'A30'}
        if x < 13.6: return {'A2'}
        return {'A12'}
    if 'E22' in E:
        if x < 8.8: return {'A28'}
        if x < 10.95: return {'A1'}
        return {'A20'}
    if 'E55' in E:
        if y > 53.0: return {'A19'}
        if y > 52.6: return {'A24'}
        if y > 51.2: return {'A13'}
        return {'A17'}
    if 'E36' in E: return {'A13'} if y > 51.95 else {'A15'}
    if 'E43' in E: return {'A7'} if y > 47.8 else {'A96'}
    if 'E31' in E: return {'A61'} if x < 8.3 else {'A65'}
    if 'E40' in E:
        if 50.3 < y < 50.95 and 8.0 < x < 9.6: return set()
        return {'A4'}
    return set()

for s in segs:
    if not s['A'] and s['E']:
        c = s['g'].interpolate(0.5, normalized=True)
        if DE.buffer(0.01).contains(c):
            s['A'] = e_to_a(s['E'], c.x, c.y)

# propagate A labels along connected segments that share an E route
def ends(l):
    c = list(l.coords)
    return [c[0], c[-1]]
def close(p, q):
    return abs(p[0] - q[0]) < 0.02 and abs(p[1] - q[1]) < 0.02
changed = True
it = 0
while changed and it < 50:
    changed = False
    it += 1
    for s in segs:
        if s['A'] or not s['E']: continue
        for t in segs:
            if not t['A'] or not (s['E'] & t['E']): continue
            if any(close(p, q) for p in ends(s['g']) for q in ends(t['g'])):
                # inherit only the A numbers that run on the shared E route
                s['A'] = set(t['A'])
                changed = True
                break
covered = sum(s['g'].length for s in segs if s['A']) / sum(s['g'].length for s in segs)
print('motorway segments', len(segs), 'share with A label after propagation', round(covered, 3))

tree = STRtree([s['g'] for s in segs])
# along-axis ordering per motorway: principal axis of its coordinates
byA = collections.defaultdict(list)
for s in segs:
    for a in s['A']:
        byA[a].append(s['g'])
axes = {}
for a, ls in byA.items():
    pts = [(x * KX, y * KY) for l in ls for (x, y) in l.coords]
    mx = sum(p[0] for p in pts) / len(pts); my = sum(p[1] for p in pts) / len(pts)
    sxx = sum((p[0] - mx) ** 2 for p in pts); syy = sum((p[1] - my) ** 2 for p in pts); sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
    ang = 0.5 * math.atan2(2 * sxy, sxx - syy)
    ux, uy = math.cos(ang), math.sin(ang)
    # orient so that positive direction points north (or east if mostly E-W)
    if abs(uy) >= abs(ux):
        if uy < 0: ux, uy = -ux, -uy
    else:
        if ux < 0: ux, uy = -ux, -uy
    axes[a] = (mx, my, ux, uy, 'ns' if abs(uy) >= abs(ux) else 'ew')

NEAR = 3.0  # km
for s in sites:
    p = Point(s['lon'], s['lat'])
    idx = tree.query(p.buffer(0.06))
    best = 99.0
    A = {}
    for i in idx:
        seg = segs[i]
        q = seg['g'].interpolate(seg['g'].project(p))
        d = km(s['lat'], s['lon'], q.y, q.x)
        best = min(best, d)
        if d <= NEAR:
            for a in seg['A']:
                if a not in A or d < A[a]:
                    A[a] = d
    s['mw'] = round(best, 1) if best < 99 else None
    s['A'] = sorted(A, key=lambda a: int(a[1:]))
    s['pos'] = {}
    for a in s['A']:
        mx, my, ux, uy, _ = axes[a]
        s['pos'][a] = round(((s['lon'] * KX - mx) * ux + (s['lat'] * KY - my) * uy), 1)

# ---- compact encoding
ops = sorted(set(s['op'] for s in sites))
opi = {o: i for i, o in enumerate(ops)}
cities = sorted(set(s['city'] for s in sites))
FIELDS = ['lat', 'lon', 'op', 'name', 'addr', 'extra', 'kw', 'n', 'flags', 'hours', 'since', 'mw', 'A']
out_rows = []
for s in sorted(sites, key=lambda s: (s['lat'], s['lon'])):
    flags = (1 if s['ccs'] else 0) | (2 if s['cha'] else 0) | (4 if s['mcs'] else 0) | (8 if s['term'] else 0) \
        | (16 if s['h24'] else 0) | (32 if s['truck'] else 0) | (64 if s['rest'] else 0) | (128 if s['tnear'] else 0)
    out_rows.append([s['lat'], s['lon'], opi[s['op']], s['name'], s['addr'], s['extra'], s['kw'], s['n'], flags,
                     s['hours'], s['since'], s['mw'], [[a, s['pos'][a]] for a in s['A']]])

# gazetteer from the whole register (all stations, so small towns are found too)
gz = collections.defaultdict(lambda: [0.0, 0.0, 0, ''])
for s in rows:
    a = s['addr']; c = clean(a.get('city'))
    if not c: continue
    k = (c, a.get('state') or '')
    g = gz[k]; g[0] += s['geo']['lat']; g[1] += s['geo']['lon']; g[2] += 1; g[3] = a.get('state') or ''
STATE = {'Baden-Württemberg': 'BW', 'Bayern': 'BY', 'Berlin': 'BE', 'Brandenburg': 'BB', 'Bremen': 'HB', 'Hamburg': 'HH', 'Hessen': 'HE',
         'Mecklenburg-Vorpommern': 'MV', 'Niedersachsen': 'NI', 'Nordrhein-Westfalen': 'NW', 'Rheinland-Pfalz': 'RP', 'Saarland': 'SL',
         'Sachsen': 'SN', 'Sachsen-Anhalt': 'ST', 'Schleswig-Holstein': 'SH', 'Thüringen': 'TH'}
places = []
for (c, st), (la, lo, n, _) in gz.items():
    places.append([c, STATE.get(st, ''), round(la / n, 4), round(lo / n, 4), n])
places.sort(key=lambda p: -p[4])

import prices as PR
data = {'stand': STAND, 'fields': FIELDS, 'ops': ops, 'sites': out_rows, 'places': places,
        'axes': {a: axes[a][4] for a in axes},
        'prices': PR.export(), 'adac': PR.ADAC, 'motion': PR.MOTION, 'opPrice': [PR.price_index(o) for o in ops],
        'priceStand': PR.PRICE_STAND}
data['country'] = 'DE'
json.dump(data, open(os.path.join(OUT, 'DE', 'sites.json'), 'w'), ensure_ascii=False, separators=(',', ':'))

# ---- Autobahnlinien zum Hervorheben einer gewählten Autobahn
def coords_lines(g):
    if g.is_empty: return []
    if g.geom_type == 'LineString': return [[[round(x, 4), round(y, 4)] for x, y in g.coords]]
    out = []
    for gg in getattr(g, 'geoms', []): out += coords_lines(gg)
    return out
mw = []
for s in segs:
    if not s['A']: continue
    for l in coords_lines(s['g'].simplify(0.002, preserve_topology=True)):
        mw.append([sorted(s['A'], key=lambda a: int(a[1:])), l])
json.dump(mw, open(os.path.join(OUT, 'mw.json'), 'w'), separators=(',', ':'))

print('stand', STAND)
print('sites total', len(sites), 'truck sites', len(truck_sites), 'car sites', len(sites) - len(truck_sites))
print('car sites with truck park nearby', sum(1 for s in sites if s['tnear']))
print('car sites <=3km motorway', sum(1 for s in sites if not s['truck'] and s['mw'] is not None and s['mw'] <= 3))
print('ops', len(ops), 'places', len(places))
for f in (os.path.join(OUT, 'DE', 'sites.json'), os.path.join(OUT, 'mw.json')):
    print(f, os.path.getsize(f))
