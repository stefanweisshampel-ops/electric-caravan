#!/usr/bin/env python3
"""Erzeugt statische, suchmaschinenfreundliche Seiten aus den Stationsdaten.

  /autobahn/                 Übersicht aller Autobahnen
  /autobahn/a9/              Schnelllader entlang der A9 mit Preisen und Gespann-Bewertungen
  /sitemap.xml               alle Seiten

Die Bewertungen holt das Skript über die öffentliche Abfrage site_stats aus Supabase
(Adresse und Schlüssel aus config.js). Alternativ: --stats datei.json
Aufruf aus dem Projektordner:  python3 tools/build_pages.py
"""
import datetime
import html
import json
import math
import os
import re
import sys
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SITE = 'https://gespann-lader.de'
MIN_KW = 100
STATUS = {'ja': 'Durchfahrt möglich', 'eng': 'Nur wenn wenig los', 'nein': 'Abkoppeln nötig', 'ungeeignet': 'Ungeeignet für Gespanne'}
E = html.escape


def load_config():
    txt = open(os.path.join(ROOT, 'config.js'), encoding='utf-8').read()
    url = re.search(r"supabaseUrl:\s*'([^']*)'", txt)
    key = re.search(r"supabaseAnonKey:\s*'([^']*)'", txt)
    return (url.group(1) if url else ''), (key.group(1) if key else '')


def fetch_stats():
    url, key = load_config()
    if not url or not key:
        return []
    req = urllib.request.Request(url.rstrip('/') + '/rest/v1/rpc/site_stats', data=b'{}', method='POST',
                                 headers={'apikey': key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except Exception as e:  # ohne Bewertungen weiterbauen
        print('Hinweis: Bewertungen nicht abrufbar:', e, file=sys.stderr)
        return []


def fmt_eur(v):
    return f'{v:.2f}'.replace('.', ',') + ' €'


def fmt_km(v):
    return (f'{v:.1f}'.replace('.', ',') if v < 10 else str(round(v))) + ' km'


def load_sites():
    d = json.load(open(os.path.join(ROOT, 'data/DE/sites.json'), encoding='utf-8'))
    prices, op_price = d['prices'], d['opPrice']
    try:  # Ad-hoc-Preise direkt von den Betreibern (AFIR über die Mobilithek), falls vorhanden
        afir = json.load(open(os.path.join(ROOT, 'data/DE/afir.json'), encoding='utf-8')).get('s', {})
    except (OSError, ValueError):
        afir = {}
    try:  # laut Nutzermeldung abgebaute Standorte ausblenden
        removed = {x['key'] for x in json.load(open(os.path.join(ROOT, 'data/DE/removed.json'), encoding='utf-8')).get('sites', [])}
    except (OSError, ValueError):
        removed = set()
    try:  # Lkw-Ladeparks mit Freigabe für Pkw mit Anhänger, siehe _info in der Datei
        pkw_ok = json.load(open(os.path.join(ROOT, 'data/DE/lkw-ausnahmen.json'), encoding='utf-8')).get('sites', [])
    except (OSError, ValueError):
        pkw_ok = []

    def near(x, r):
        return math.hypot((x['lat'] - r[0]) * 110.57, (x['lon'] - r[1]) * 70.06) < 0.15

    try:  # Durchfahrt laut Betreiber, siehe _info in der Datei
        op_info = json.load(open(os.path.join(ROOT, 'data/DE/betreiber-angaben.json'), encoding='utf-8')).get('sites', [])
    except (OSError, ValueError):
        op_info = []

    sites = []
    for r in d['sites']:
        if 'DE-%.4f_%.4f' % (r[0], r[1]) in removed:
            continue
        fl = r[8]
        pi = op_price[r[2]]
        p = prices[pi] if pi >= 0 else None
        best = None
        key = 'DE-%.4f_%.4f' % (r[0], r[1])
        a = afir.get(key)
        c = []
        if a and a[0] is not None:
            c.append(a[0])
        elif p and p.get('adhoc'):
            c.append(p['adhoc'][0])
        if p and p.get('app'):
            c.append(p['app'][0])
        best = min(c) if c else None
        parts = r[4].split(', ')
        city = re.sub(r'^\d{4,5}\s*', '', parts[-1] if parts else '')
        sites.append({
            'lat': r[0], 'lon': r[1], 'op': d['ops'][r[2]], 'name': r[3], 'addr': r[4], 'kw': r[6], 'n': r[7],
            'truck': bool(fl & 32), 'rest': bool(fl & 64), 'term': bool(fl & 8), 'mw': r[11],
            'A': {a: pos for a, pos in (r[12] or [])}, 'best': best, 'city': city,
            'key': key, 'st': None,
            'optrailer': bool(a and a[5]) or any(near(x, r) and x['betreiber'] in d['ops'][r[2]].lower() for x in op_info),
            'pkwok': bool(fl & 32) and any(near(x, r) for x in pkw_ok),
        })
    return d, sites


def attach_stats(sites, stats):
    grid = {}
    for s in sites:
        grid.setdefault((round(s['lat'] / 0.01), round(s['lon'] / 0.01)), []).append(s)
    by_key = {s['key']: s for s in sites}
    kx = 111.32 * math.cos(math.radians(51))
    for r in stats:
        s = by_key.get(r.get('site_key'))
        if not s and r.get('lat') is not None:
            cy, cx = round(r['lat'] / 0.01), round(r['lon'] / 0.01)
            bd = 0.15
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    for t in grid.get((cy + dy, cx + dx), []):
                        dd = math.hypot((t['lat'] - r['lat']) * 110.57, (t['lon'] - r['lon']) * kx)
                        if dd < bd:
                            bd, s = dd, t
        if not s:
            continue
        st = s['st'] or {'ja': 0, 'eng': 0, 'nein': 0, 'ungeeignet': 0}
        for k in ('ja', 'eng', 'nein', 'ungeeignet'):
            st[k] += int(r.get('n_' + k) or 0)
        s['st'] = st


def status_of(s):
    st = s['st']
    if not st or not sum(st.values()):
        return None
    m = max(st.values())
    for k in ('ungeeignet', 'nein', 'eng', 'ja'):  # bei Gleichstand die vorsichtigere Einschätzung
        if st[k] == m:
            return k


def page(title, desc, path, body, crumbs=None, extra_ld=None):
    ld = ''
    if crumbs:
        ld = '<script type="application/ld+json">' + json.dumps({
            '@context': 'https://schema.org', '@type': 'BreadcrumbList',
            'itemListElement': [{'@type': 'ListItem', 'position': i + 1, 'name': n, 'item': SITE + u}
                                for i, (n, u) in enumerate(crumbs)]}, ensure_ascii=False) + '</script>'
    for x in extra_ld or []:
        ld += '\n<script type="application/ld+json">' + json.dumps(x, ensure_ascii=False) + '</script>'
    return f'''<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<link rel="canonical" href="{SITE}{path}">
<meta name="theme-color" content="#0f5f6e">
<link rel="icon" type="image/png" href="/apple-touch-icon.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Gespann-Lader">
<meta property="og:locale" content="de_DE">
<meta property="og:url" content="{SITE}{path}">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:image" content="{SITE}/og.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/pages.css">
{ld}
</head>
<body>
<header class="top"><a class="brand" href="/">Gespann-Lader</a><nav><a href="/">Karte</a><a href="/autobahn/">Autobahnen</a><a href="/betreiber/">Betreiber</a><a href="/ratgeber/">Ratgeber</a></nav></header>
<main>
{body}
</main>
<footer>
<p>Stationsdaten: Ladesäulenregister der Bundesnetzagentur (CC BY 4.0). Bewertungen: Nutzerinnen und Nutzer von Gespann-Lader. Preise: eigene Recherche, ohne Gewähr – verbindlich ist der Preis vor dem Ladestart.</p>
<p><a href="/impressum.html">Impressum</a> · <a href="/datenschutz.html">Datenschutz</a></p>
</footer>
</body>
</html>
'''


# Betreiberseiten: (Pfad, Anzeigename, Suchtext im Betreibernamen, Überschrift)
BETREIBER = [
    ('tesla', 'Tesla', 'tesla', 'Tesla Supercharger mit Anhänger'),
    ('ionity', 'IONITY', 'ionity', 'IONITY mit Anhänger oder Wohnwagen'),
    ('enbw', 'EnBW', 'enbw', 'EnBW-Schnelllader mit Anhänger'),
    ('ewe-go', 'EWE Go', 'ewe go', 'EWE Go mit Anhänger'),
    ('aral-pulse', 'Aral pulse', 'aral pulse', 'Aral pulse mit Anhänger'),
    ('shell', 'Shell Recharge', 'shell', 'Shell Recharge mit Anhänger'),
    ('allego', 'Allego', 'allego', 'Allego mit Anhänger'),
    ('fastned', 'Fastned', 'fastned', 'Fastned mit Anhänger'),
    ('pfalzwerke', 'Pfalzwerke', 'pfalzwerke', 'Pfalzwerke-Schnelllader mit Anhänger'),
    ('vattenfall', 'Vattenfall', 'vattenfall', 'Vattenfall-Schnelllader mit Anhänger'),
    ('aldi', 'ALDI', 'aldi', 'Bei ALDI mit Anhänger laden'),
    ('eon', 'E.ON Drive', 'e.on', 'E.ON-Schnelllader mit Anhänger'),
    ('mer', 'Mer', 'mer germany', 'Mer-Schnelllader mit Anhänger'),
    ('circle-k', 'Circle K', 'circle k', 'Circle K mit Anhänger'),
    ('electra', 'Electra', 'electra', 'Electra mit Anhänger'),
    ('jolt', 'Jolt', 'jolt', 'Jolt mit Anhänger'),
    ('totalenergies', 'TotalEnergies', 'totalenergies', 'TotalEnergies mit Anhänger'),
    ('comfort-charge', 'Comfort Charge', 'comfort charge', 'Comfort Charge mit Anhänger'),
]


def badge(s):
    st = status_of(s)
    n = sum(s['st'].values()) if s['st'] else 0
    if st:
        return f'<span class="b {st}">{STATUS[st]}</span>' + (f'<small>{n} Bewertungen</small>' if n > 1 else '')
    if s.get('optrailer'):
        return '<span class="b ja">Durchfahrt laut Betreiber</span>'
    return '<span class="b open">noch nicht bewertet</span>'


def counts_text(cnt, n_r):
    teile = [f'{cnt["ja"]} mit Durchfahrt', f'{cnt["eng"]} nur wenn wenig los ist', f'{cnt["nein"]} nur mit Abkoppeln']
    if cnt['ungeeignet']:
        teile.append(f'{cnt["ungeeignet"]} gar nicht für Gespanne')
    return f'{n_r} davon haben Gespannfahrer schon bewertet: ' + ', '.join(teile[:-1]) + ' und ' + teile[-1] + '. '


def build_betreiber(car, stand, urls):
    ORDER = {'ja': 0, 'eng': 1, 'nein': 2, 'ungeeignet': 3, None: 4}
    overview = []
    for slug, name, needle, h1 in BETREIBER:
        lst = [s for s in car if needle in s['op'].lower()]
        if len(lst) < 20:
            continue
        cnt = {k: sum(1 for s in lst if status_of(s) == k) for k in STATUS}
        n_r = sum(cnt.values())
        overview.append((slug, name, len(lst), cnt['ja'], n_r))
        rated = sorted((s for s in lst if status_of(s)), key=lambda s: (ORDER[status_of(s)], s['city']))
        near = sorted((s for s in lst if not status_of(s) and s['mw'] is not None and s['mw'] <= 1),
                      key=lambda s: (sorted(s['A'])[0] if s['A'] else 'Z', s['city']))
        prices = sorted(s['best'] for s in lst if s['best'] is not None)

        def rows(xs):
            out = []
            for s in xs:
                sub = E(s['city']) + ((' · ' + ', '.join(sorted(s['A'], key=lambda a: int(re.sub(r'\D', '', a) or 0)))) if s['A'] else '')
                out.append(f'<tr><td><a href="/#s={E(s["key"])}">{E(s["name"] or s["op"])}</a><div class="sub">{sub}</div></td>'
                           f'<td class="num">{s["kw"]} kW<div class="sub">{s["n"]} Ladepunkt{"e" if s["n"] != 1 else ""}</div></td>'
                           f'<td>{badge(s)}</td></tr>')
            return '\n'.join(out)

        intro = f'{name} betreibt in Deutschland {len(lst)} Schnellladestandorte für Pkw mit mindestens {MIN_KW} kW. '
        intro += counts_text(cnt, n_r) if n_r else 'Bewertet hat davon noch niemand einen – fang gern an. '
        intro += 'Ob man mit Wohnwagen oder Anhänger ohne Abkoppeln laden kann, hängt vom einzelnen Standort ab: Manche Ladeparks haben Durchfahrtsplätze, viele nur Parkbuchten.'
        price = ''
        if prices:
            price = f'<p>Preis ohne Abo laut unseren Daten: ab {fmt_eur(prices[0])} pro kWh. Verbindlich ist der Preis vor dem Ladestart.</p>'
        good = [s for s in lst if status_of(s) == 'ja']
        goodbox = ('<div class="box"><b>Mit Durchfahrt bewertet:</b> ' + ', '.join(
            f'<a href="/#s={E(s["key"])}">{E(s["name"] or s["op"])}</a> ({E(s["city"])})' for s in good) + '</div>') if good else ''
        table_r = (f'<h2>Bewertete Standorte ({n_r})</h2><div class="tw"><table><thead><tr><th>Standort</th><th>Leistung</th><th>Mit Gespann</th></tr></thead><tbody>\n{rows(rated)}\n</tbody></table></div>') if rated else ''
        table_n = (f'<h2>Direkt an der Autobahn, noch nicht bewertet ({len(near)})</h2><p class="hint">Höchstens einen Kilometer von der Autobahn entfernt. Wer einen davon kennt: bitte auf der Karte bewerten.</p>'
                   f'<div class="tw"><table><thead><tr><th>Standort</th><th>Leistung</th><th>Mit Gespann</th></tr></thead><tbody>\n{rows(near)}\n</tbody></table></div>') if near else ''
        body = f'''<p class="crumbs"><a href="/">Start</a> › <a href="/betreiber/">Betreiber</a> › {E(name)}</p>
<h1>{E(h1)}: Wo ist Durchfahrt möglich?</h1>
<p class="lead">{E(intro)}</p>
<p><a class="btn" href="/#op={E(needle)}">Alle {len(lst)} Standorte von {E(name)} auf der Karte</a></p>
{goodbox}
{price}
{table_r}
{table_n}
<p class="hint">Stationsdaten: Ladesäulenregister der Bundesnetzagentur, Stand {E(stand)}. Die Bewertungen werden täglich aktualisiert, ganz aktuell sind sie auf der Karte. Mehr zum Laden mit Gespann im <a href="/ratgeber/">Ratgeber</a>.</p>'''
        title = f'{h1}: Ladestationen mit Durchfahrt | Gespann-Lader'
        desc = (f'{len(lst)} Schnelllader von {name}: Wo kann man mit E-Auto und Wohnwagen oder Anhänger laden, ohne abzukoppeln? '
                f'Bewertet von Gespannfahrern.')
        path = f'/betreiber/{slug}/'
        os.makedirs(os.path.join(ROOT, 'betreiber', slug), exist_ok=True)
        with open(os.path.join(ROOT, 'betreiber', slug, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(page(title, desc, path, body, [('Start', '/'), ('Betreiber', '/betreiber/'), (name, path)]))
        urls.append((path, '0.6'))

    items = ''.join(f'<li><a href="/betreiber/{slug}/"><b>{E(name)}</b></a><span>{n} Schnelllader'
                    + (f' · {r} bewertet' if r else '') + (f' · {g} mit Durchfahrt' if g else '') + '</span></li>'
                    for slug, name, n, g, r in overview)
    body = f'''<p class="crumbs"><a href="/">Start</a> › Betreiber</p>
<h1>Ladestationen für Gespanne nach Betreiber</h1>
<p class="lead">Welche Schnelllader von Tesla, IONITY, EnBW, Aral pulse und anderen Betreibern lassen sich mit E-Auto und Anhänger oder Wohnwagen anfahren, ohne abzukoppeln? Für jeden großen Betreiber gibt es hier alle bisherigen Bewertungen von Gespannfahrern.</p>
<ul class="alist">{items}</ul>
<p class="hint">Stationsdaten: Ladesäulenregister der Bundesnetzagentur, Stand {E(stand)}. Gezählt sind Pkw-Schnelllader ab {MIN_KW} kW.</p>'''
    os.makedirs(os.path.join(ROOT, 'betreiber'), exist_ok=True)
    with open(os.path.join(ROOT, 'betreiber', 'index.html'), 'w', encoding='utf-8') as f:
        f.write(page('Ladestationen mit Durchfahrt nach Betreiber: Tesla, IONITY, EnBW … | Gespann-Lader',
                     'Schnelllader von Tesla, IONITY, EnBW, Aral pulse und anderen: Wo kann man mit Anhänger oder Wohnwagen laden, ohne abzukoppeln?',
                     '/betreiber/', body, [('Start', '/'), ('Betreiber', '/betreiber/')]))
    urls.insert(3, ('/betreiber/', '0.8'))
    return overview


def build_ratgeber(car, stand, betreiber):
    tpl = open(os.path.join(ROOT, 'tools', 'ratgeber.html'), encoding='utf-8').read()
    tpl = re.sub(r'^<!--.*?-->\s*', '', tpl, flags=re.S)
    cnt = {k: sum(1 for s in car if status_of(s) == k) for k in STATUS}
    n_r = sum(cnt.values())
    links = '<ul class="alist">' + ''.join(
        f'<li><a href="/betreiber/{slug}/"><b>{E(name)}</b></a><span>{n} Schnelllader' + (f' · {r} bewertet' if r else '') + '</span></li>'
        for slug, name, n, g, r in betreiber) + '</ul>'
    pct = round(100 * cnt['ja'] / n_r) if n_r else 0
    p_ja = f'{pct} Prozent'
    vals = {'STAND': stand, 'N_FAST': f'{len(car):,}'.replace(',', '.'), 'N_RATED': str(n_r), 'N_JA': str(cnt['ja']),
            'N_ENG': str(cnt['eng']), 'N_NEIN': str(cnt['nein']), 'N_UNG': str(cnt['ungeeignet']), 'P_JA': p_ja,
            'BETREIBER_LINKS': links}
    body = re.sub(r'\{\{(\w+)\}\}', lambda m: vals[m.group(1)], tpl)
    faq = []
    for q, a in re.findall(r'<h3>(.*?)</h3>\s*<p>(.*?)</p>', body, re.S):
        faq.append({'@type': 'Question', 'name': re.sub('<[^>]+>', '', q),
                    'acceptedAnswer': {'@type': 'Answer', 'text': re.sub('<[^>]+>', '', a)}})
    extra = [{'@context': 'https://schema.org', '@type': 'Article',
              'headline': 'E-Auto mit Anhänger oder Wohnwagen laden – ohne Abkoppeln', 'inLanguage': 'de',
              'author': {'@type': 'Organization', 'name': 'Gespann-Lader', 'url': SITE + '/'},
              'mainEntityOfPage': SITE + '/ratgeber/'}]
    if faq:
        extra.append({'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': faq})
    os.makedirs(os.path.join(ROOT, 'ratgeber'), exist_ok=True)
    with open(os.path.join(ROOT, 'ratgeber', 'index.html'), 'w', encoding='utf-8') as f:
        f.write(page('E-Auto mit Anhänger oder Wohnwagen laden: Ladestationen mit Durchfahrt | Gespann-Lader',
                     'Wie lädt man ein Elektroauto mit Anhänger oder Wohnwagen, ohne abzukoppeln? Woran man Ladestationen mit Durchfahrt erkennt, '
                     'wie viel Reichweite der Anhänger kostet und was bei Lkw-Ladeparks gilt.',
                     '/ratgeber/', body, [('Start', '/'), ('Ratgeber', '/ratgeber/')], extra))


def lastmod(url, _old={}):
    """Änderungsdatum für die Sitemap: heute, wenn sich die Seite gegenüber dem letzten Commit geändert hat,
    sonst das bisherige Datum. So bleibt lastmod ehrlich und die Sitemap ändert sich nicht jeden Tag."""
    import subprocess
    if not _old:
        try:
            old = open(os.path.join(ROOT, 'sitemap.xml'), encoding='utf-8').read()
            _old.update(re.findall(r'<loc>' + re.escape(SITE) + r'(\S+?)</loc><lastmod>([\d-]+)</lastmod>', old))
        except OSError:
            pass
        _old.setdefault('_', '')
    f = url.strip('/') + '/index.html' if url.endswith('/') and url != '/' else ('index.html' if url == '/' else url.lstrip('/'))
    try:
        tracked = subprocess.run(['git', 'ls-files', '--error-unmatch', f], cwd=ROOT, capture_output=True).returncode == 0
        changed = not tracked or subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', f], cwd=ROOT).returncode != 0
    except OSError:
        changed = False
    return datetime.date.today().isoformat() if changed or url not in _old else _old[url]


def axis_label(o):
    return ('Süd → Nord', 'Nord → Süd') if o == 'ns' else ('West → Ost', 'Ost → West')


def build():
    args = sys.argv[1:]
    if '--stats' in args:
        stats = json.load(open(args[args.index('--stats') + 1], encoding='utf-8'))
    else:
        stats = fetch_stats()
    d, sites = load_sites()
    attach_stats(sites, stats)
    stand = '.'.join(reversed(d['stand'].split('-')))
    pstand = d.get('priceStand', '')
    car = [s for s in sites if (not s['truck'] or s['pkwok']) and s['kw'] >= MIN_KW]
    by_a = {}
    for s in car:
        for a in s['A']:
            by_a.setdefault(a, []).append(s)
    axes = d.get('axes', {})
    urls = [('/', '1.0'), ('/autobahn/', '0.8'), ('/ratgeber/', '0.8')]
    overview = []

    for a in sorted(by_a, key=lambda x: int(re.sub(r'\D', '', x) or 0)):
        lst = sorted(by_a[a], key=lambda s: s['A'][a])
        p0 = lst[0]['A'][a]
        slug = a.lower()
        n_r = sum(1 for s in lst if status_of(s))
        cnt = {k: sum(1 for s in lst if status_of(s) == k) for k in STATUS}
        good = [s for s in lst if status_of(s) == 'ja']
        cheap = [s for s in lst if s['best'] is not None and s['best'] <= 0.62]
        overview.append((a, len(lst), cnt['ja'], n_r))
        rows = []
        prev = None
        for s in lst:
            km = s['A'][a] - p0
            gap = '' if prev is None else f'<span class="gap">+{round(s["A"][a] - prev)} km</span>'
            prev = s['A'][a]
            st = status_of(s)
            n = sum(s['st'].values()) if s['st'] else 0
            badge = (f'<span class="b {st}">{STATUS[st]}</span>' + (f'<small>{n} Bewertungen</small>' if n > 1 else '')) if st \
                else ('<span class="b ja">Durchfahrt laut Betreiber</span>' if s.get('optrailer')
                      else '<span class="b open">noch nicht bewertet</span>')
            name = s['name'] or s['op']
            sub = (E(s['op']) + ' · ' if s['name'] else '') + E(s['city'])
            extra = []
            if s['mw'] is not None:
                extra.append(fmt_km(s['mw']) + ' von der Autobahn')
            if s['rest']:
                extra.append('Autohof/Rastanlage')
            if s['term']:
                extra.append('Kartenterminal')
            if s['pkwok']:
                extra.append('Lkw-Ladepark, laut Betreiber auch für Pkw mit Anhänger')
            rows.append(
                f'<tr><td class="km">{round(km)}{gap}</td>'
                f'<td><a href="/#s={E(s["key"])}">{E(name)}</a><div class="sub">{sub}</div>'
                + (f'<div class="sub">{E(" · ".join(extra))}</div>' if extra else '') +
                f'</td><td class="num">{s["kw"]} kW<div class="sub">{s["n"]} Ladepunkt{"e" if s["n"] != 1 else ""}</div></td>'
                f'<td class="num">{("ab " + fmt_eur(s["best"])) if s["best"] is not None else "–"}</td>'
                f'<td>{badge}</td></tr>')
        d1, _ = axis_label(axes.get(a, 'ns'))
        intro = (f'Entlang der {a} gibt es {len(lst)} Schnellladestandorte für Pkw mit mindestens {MIN_KW} kW, '
                 f'höchstens drei Kilometer von der Autobahn entfernt. ')
        if n_r:
            teile = [f'{cnt["ja"]} mit Durchfahrt', f'{cnt["eng"]} nur wenn wenig los ist',
                     f'{cnt["nein"]} nur mit Abkoppeln']
            if cnt['ungeeignet']:
                teile.append(f'{cnt["ungeeignet"]} gar nicht für Gespanne')
            intro += (f'{n_r} davon haben Gespannfahrer schon bewertet: '
                      + ', '.join(teile[:-1]) + ' und ' + teile[-1] + '. ')
        else:
            intro += 'Noch hat niemand einen davon bewertet – fang gern an. '
        intro += (f'{len(cheap)} Standorte gehören zu Betreibern, die ohne Abo höchstens 0,62 € pro kWh verlangen. '
                  'Lkw-Ladeparks sind nur aufgeführt, wenn der Betreiber sie ausdrücklich auch für Pkw mit Anhänger freigibt.')
        goodbox = ''
        if good:
            goodbox = ('<div class="box"><b>Mit Durchfahrt bewertet:</b> '
                       + ', '.join(f'<a href="/#s={E(s["key"])}">{E(s["name"] or s["op"])}</a> ({E(s["city"])})' for s in good)
                       + '</div>')
        body = f'''<p class="crumbs"><a href="/">Start</a> › <a href="/autobahn/">Autobahnen</a> › {a}</p>
<h1>{a}: Schnelllader für E-Autos mit Wohnwagen oder Anhänger</h1>
<p class="lead">{E(intro)}</p>
<p><a class="btn" href="/#{a}">{a} auf der Karte öffnen</a></p>
{goodbox}
<p class="hint">Reihenfolge {d1}, Kilometer entlang der Autobahn gemessen. Ein Standort fehlt oder ist falsch bewertet? Tippe ihn auf der Karte an und trage ein, ob man mit Gespann durchfahren kann.</p>
<div class="tw"><table>
<thead><tr><th>km</th><th>Standort</th><th>Leistung</th><th>Preis ohne Abo</th><th>Mit Gespann</th></tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody></table></div>
<p class="hint">Stationsdaten Stand {E(stand)}, Preise recherchiert am {E(pstand)}, Ad-hoc-Preise von EnBW, Tesla, EWE Go und Stadtwerken laut AFIR-Daten der Betreiber (Mobilithek). Die Bewertungen werden täglich aktualisiert, ganz aktuell sind sie auf der Karte.</p>'''
        title = f'{a}: Schnelllader mit Durchfahrt für Wohnwagen und Anhänger | Gespann-Lader'
        desc = (f'{len(lst)} Schnelllader an der {a}: Wo kann man mit E-Auto und Wohnwagen laden, ohne abzukoppeln? '
                f'Mit Preisen ohne Abo und Bewertungen von Gespannfahrern.')
        path = f'/autobahn/{slug}/'
        os.makedirs(os.path.join(ROOT, 'autobahn', slug), exist_ok=True)
        with open(os.path.join(ROOT, 'autobahn', slug, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(page(title, desc, path, body, [('Start', '/'), ('Autobahnen', '/autobahn/'), (a, path)]))
        urls.append((path, '0.6'))

    items = ''.join(
        f'<li><a href="/autobahn/{a.lower()}/"><b>{a}</b></a><span>{n} Schnelllader'
        + (f' · {g} mit Durchfahrt' if g else '') + '</span></li>' for a, n, g, _ in overview)
    total_rated = sum(1 for s in car if status_of(s))
    body = f'''<p class="crumbs"><a href="/">Start</a> › Autobahnen</p>
<h1>Schnelllader für Gespanne an deutschen Autobahnen</h1>
<p class="lead">Mit E-Auto und Wohnwagen auf der Autobahn: Hier findest du für jede Autobahn alle Pkw-Schnelllader ab {MIN_KW} kW in höchstens drei Kilometern Entfernung – mit Preisen ohne Abo und der Einschätzung anderer Gespannfahrer, ob man ohne Abkoppeln laden kann. Bisher sind {total_rated} Standorte bewertet.</p>
<ul class="alist">{items}</ul>
<p class="hint">Stationsdaten: Ladesäulenregister der Bundesnetzagentur, Stand {E(stand)}.</p>'''
    with open(os.path.join(ROOT, 'autobahn', 'index.html'), 'w', encoding='utf-8') as f:
        f.write(page('Schnelllader für Wohnwagen-Gespanne an allen Autobahnen | Gespann-Lader',
                     'Alle Schnelllader an deutschen Autobahnen, an denen man mit E-Auto und Wohnwagen laden kann – '
                     'bewertet von Gespannfahrern, mit Preisen ohne Abo.',
                     '/autobahn/', body, [('Start', '/'), ('Autobahnen', '/autobahn/')]))

    betreiber = build_betreiber(car, stand, urls)
    build_ratgeber(car, stand, betreiber)
    urls += [('/impressum.html', '0.1'), ('/datenschutz.html', '0.1')]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += [f'  <url><loc>{SITE}{u}</loc>' + (f'<lastmod>{lm}</lastmod>' if lm else '') + f'<priority>{p}</priority></url>'
           for u, p in urls for lm in [lastmod(u)]]
    sm.append('</urlset>')
    with open(os.path.join(ROOT, 'sitemap.xml'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(sm) + '\n')
    print(f'{len(betreiber)} Betreiberseiten, {len(overview)} Autobahn-Seiten, {len(urls)} URLs in der Sitemap, {total_rated} bewertete Standorte')


if __name__ == '__main__':
    build()
