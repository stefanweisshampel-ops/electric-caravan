"""Prüft und stabilisiert ein neues Ladesäulenregister vor dem Übernehmen.

Aufruf:  python3 tools/register_update.py <alt/sites.json> <neu/sites.json> <bericht.md>

1. Schlüssel halten: Der Standort-Schlüssel ergibt sich aus lat/lon. Verschiebt das
   Register einen Standort leicht (z. B. beim Ausbau um weitere Säulen), bekäme er
   einen neuen Schlüssel und verlöre seine Bewertungen. Deshalb übernimmt ein neuer
   Standort die Position eines verschwundenen alten Standorts desselben Betreibers
   im Umkreis von 150 m. Die neue Datei wird entsprechend überschrieben.
2. Plausibilität: Ändert sich die Zahl der Standorte um mehr als 10 % nach unten
   oder 25 % nach oben, wird nichts übernommen (Exit-Code 2).
3. Bewertete Standorte, die danach immer noch fehlen (wirklich aus dem Register
   gestrichen), werden im Bericht aufgeführt (Exit-Code 3, Daten werden trotzdem
   übernommen – der Workflow legt dann ein Issue an).

Exit-Codes: 0 = alles gut, 1 = nichts Neues, 2 = abgebrochen, 3 = übernommen mit Hinweisen.
"""
import json, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PIN_KM = 0.15


def key(r):
    return 'DE-%.4f_%.4f' % (r[0], r[1])


def km(a, b):
    return math.hypot((a[0] - b[0]) * 110.57, (a[1] - b[1]) * 111.32 * math.cos(math.radians(a[0])))


def rated_keys():
    try:
        if os.environ.get('STATS_FILE'):  # zum Testen ohne Netz
            stats = json.load(open(os.environ['STATS_FILE'], encoding='utf-8'))
        else:
            import build_pages
            stats = build_pages.fetch_stats()
        return {s['site_key'] for s in stats if s.get('site_key')} or None
    except Exception as e:  # ohne Bewertungen weiter, aber im Bericht vermerken
        print('Bewertungen nicht abrufbar:', e)
        return None


def main(old_p, new_p, rep_p):
    old = json.load(open(old_p, encoding='utf-8'))
    new = json.load(open(new_p, encoding='utf-8'))
    rep = []
    if new.get('stand') == old.get('stand'):
        print('Registerstand unverändert:', new.get('stand'))
        return 1
    n_old, n_new = len(old['sites']), len(new['sites'])
    rep.append(f"Registerstand {old.get('stand')} → {new.get('stand')}, Standorte {n_old} → {n_new}.")
    if n_new < 0.9 * n_old or n_new > 1.25 * n_old:
        rep.append('**Abgebrochen:** Die Zahl der Standorte ändert sich ungewöhnlich stark. '
                   'Bitte prüfen, ob die Quelle (ratopi/ladesaeule) vollständig ist.')
        open(rep_p, 'w', encoding='utf-8').write('\n\n'.join(rep) + '\n')
        return 2

    old_by_key = {key(r): r for r in old['sites']}
    new_keys = {key(r) for r in new['sites']}
    gone = [r for k, r in old_by_key.items() if k not in new_keys]
    pinned = 0
    for r in new['sites']:
        if key(r) in old_by_key:
            continue
        op = new['ops'][r[2]]
        best = None
        for g in gone:
            if old['ops'][g[2]] == op and km(r, g) < PIN_KM and (best is None or km(r, g) < km(r, best)):
                best = g
        if best is not None and key(best) not in new_keys:
            r[0], r[1] = best[0], best[1]
            new_keys.add(key(best))
            gone.remove(best)
            pinned += 1
    added = len([r for r in new['sites'] if key(r) not in old_by_key])
    rep.append(f'Neu: {added}, nicht mehr im Register: {len(gone)}, leicht verschoben (Schlüssel gehalten): {pinned}.')
    json.dump(new, open(new_p, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))

    rated = rated_keys()
    code = 0
    if rated is None:
        rep.append('Hinweis: Die Bewertungen konnten nicht abgerufen werden, verlorene Bewertungen wurden nicht geprüft.')
        code = 3
    else:
        lost = sorted(k for k in rated if k in old_by_key and k not in new_keys)
        if lost:
            code = 3
            rep.append(f'**{len(lost)} bewertete Standorte stehen nicht mehr im Register.** '
                       'Ihre Bewertungen bleiben in der Datenbank, werden aber nicht mehr angezeigt:')
            for k in lost:
                r = old_by_key[k]
                rep.append(f'- {old["ops"][r[2]]}, {r[4]} (`{k}`)')
    open(rep_p, 'w', encoding='utf-8').write('\n\n'.join(rep) + '\n')
    print('\n'.join(rep))
    return code


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:4]))
