"""Prices without subscription (ad hoc and the operator's own app without base fee),
for DC / HPC charging in Germany, EUR per kWh incl. VAT. Researched 2026-11-05.

LC = Ladechef operator table (operators' AFIR ad-hoc feeds via Mobilithek), Stand 2.-5.11.2026
"""
import re

LC = 'Ladechef (AFIR-Meldung der Betreiber), Stand Anfang Nov. 2026'

# key, label, regex on operator/display name, adhoc [min,max] or None, app [min,max] or None, app name, note, source
PRICES = [
    ('enbw', 'EnBW', r'^EnBW mobility', [0.79, 0.79], [0.56, 0.56], 'EnBW mobility+ Tarif S', '', LC + '; App-Preis: EnBW/Nextpit'),
    ('ewego', 'EWE Go', r'EWE Go', [0.84, 0.85], [0.52, 0.52], 'EWE Go App/Ladekarte', '', LC + '; App-Preis: EWE Go'),
    ('shell', 'Shell Recharge', r'^Shell', [0.79, 0.79], [0.52, 0.62], 'Shell Recharge Basic', 'Blockiergebühr nach 60 Min.', LC + '; App-Preis: motor.com.de, Sept. 2026'),
    ('aral', 'Aral pulse', r'Aral', [0.79, 0.81], [0.69, 0.69], 'Aral pulse Klassik', 'Ladechef meldet vereinzelt auch günstigere Standorte.', LC + '; App/ADAC: Auto Bild, InsideEVs'),
    ('allego', 'Allego', r'Allego', [0.66, 0.76], [0.59, 0.59], 'Allego Smart', 'Bis 31.12.2026 an 200 Standorten 20 ct Cashback in der App.', LC + '; App-Preis: electrive, Juni/Okt. 2026'),
    ('pfalzwerke', 'Pfalzwerke', r'Pfalzwerke', [0.79, 0.79], None, '', 'Keine eigene App.', LC + '; electrive'),
    ('tesla', 'Tesla', r'Tesla', [0.31, 0.73], None, '', 'Preis je Standort und Uhrzeit.', LC),
    ('vattenfall', 'Vattenfall', r'Vattenfall', [0.44, 0.70], None, '', '„Fair Laden“ meist 0,44–0,49 €.', LC),
    ('aldisued', 'ALDI SÜD', r'ALDI S[ÜU]D', [0.44, 0.47], None, '', 'Laden nur während der Öffnungszeiten.', LC),
    ('aldinord', 'ALDI Nord', r'ALDI Nord', [0.44, 0.47], None, '', '', LC),
    ('lidl', 'Lidl', r'Lidl', [0.48, 0.69], None, '', '', LC),
    ('kaufland', 'Kaufland', r'Kaufland', [0.48, 0.69], None, '', '', LC),
    ('ionity', 'IONITY', r'IONITY', [0.72, 0.76], [0.68, 0.72], 'IONITY Go', '', LC + '; App-Preis: motor.com.de, Sept. 2026'),
    ('eon', 'E.ON Drive', r'E\.ON', [0.73, 0.73], [0.61, 0.61], 'E.ON Drive ohne Grundgebühr', '', LC + '; App-Preis: InsideEVs/test.de'),
    ('comfort', 'Comfort Charge', r'Comfort ?Charge', [0.47, 0.74], None, '', '', LC),
    ('teag', 'TEAG', r'^TEAG', [0.49, 0.49], None, '', '', LC),
    ('mer', 'Mer', r'^MER\b|Mer Germany', [0.49, 0.66], [0.69, 0.69], 'Mer-App', 'App-Preis laut deiner Beobachtung.', LC),
    ('jolt', 'JOLT', r'Jolt|JOLT', [0.66, 0.70], [0.55, 0.59], 'JOLT-App', 'App-Preis Stand 2025, nicht neu geprüft.', LC + '; App-Preis: ecomento 2025'),
    ('total', 'TotalEnergies', r'TotalEnergies', [0.33, 1.01], None, '', 'Große Spanne je Standort.', LC),
    ('eviny', 'Eviny', r'Eviny', [0.67, 0.67], None, '', 'Laut Nutzerbericht, nicht amtlich bestätigt.', 'Leserkommentar ecomento, März 2026'),
    ('henw', 'Hamburger Energiewerke', r'HEnW|Hamburger Energiewerke', [0.50, 0.72], None, '', '', LC),
    ('fastned', 'Fastned', r'Fastned', [0.69, 0.69], [0.62, 0.62], 'Fastned-App mit hinterlegter Karte (−10 %)', '', LC + '; App-Rabatt: ecomento, März 2026'),
    ('tanke', 'TankE', r'TankE', [0.48, 0.75], None, '', '', LC),
    ('esb', 'Energie Südbayern', r'Energie Südbayern', [0.58, 0.58], None, '', '', LC),
    ('amperio', 'amperio', r'amperio', [0.69, 0.69], None, '', '', LC),
    ('citywatt', 'Citywatt', r'Citywatt', [0.70, 0.79], None, '', '', LC),
    ('cubos', 'CUBOS', r'CUBOS', [0.30, 0.70], None, '', '', LC),
    ('eam', 'EAM', r'^EAM', [0.59, 0.59], None, '', '', LC),
    ('gpjoule', 'GP JOULE', r'GP JOULE', [0.65, 0.73], None, '', '', LC),
    ('jet', 'JET', r'^JET', [0.49, 0.49], None, '', '', LC),
    ('westfalen', 'Westfalen', r'^Westfalen AG', [0.64, 0.64], None, '', '', LC),
    ('electra', 'Electra', r'Electra', [0.69, 0.69], [0.54, 0.54], 'Electra-App', '', LC + '; App-Preis: einfacheauto/Auto Bild 2026'),
    ('sachsen', 'SachsenEnergie', r'SachsenEnergie', [0.50, 0.50], None, '', 'Quelle ohne genaues Datum.', 'inside-digital Tarifübersicht'),
    ('orlen', 'ORLEN', r'ORLEN', [0.58, 0.58], None, '', '', LC),
    ('mainova', 'Mainova', r'Mainova', [0.76, 0.76], None, '', '', LC),
    ('praeg', 'Präg', r'Präg', [0.57, 0.57], None, '', '', LC),
    ('mvv', 'MVV', r'^MVV', [0.66, 0.66], None, '', '', LC),
    ('eliso', 'eliso', r'eliso', [0.49, 0.64], None, '', '', LC),
    ('enercity', 'enercity', r'enercity', [0.78, 0.78], None, '', '', LC),
    ('baywa', 'BayWa', r'BayWa', [0.66, 1.01], None, '', '', LC),
    ('swb', 'SWB Bonn/Rhein-Sieg', r'Bonn/Rhein-Sieg', [0.49, 0.56], None, '', '', LC),
    ('avia', 'AVIA Volt', r'AVIA', [0.51, 1.01], None, '', '', LC),
    ('mbhpc', 'Mercedes-Benz HPC', r'(Mercedes|Merdedes)-Benz High Power', [0.69, 0.69], None, '', 'Nutzerangabe 2025, teils höher berichtet.', 'Leserkommentare electrive, Juni 2025'),
    ('circlek', 'Circle K', r'Circle K', None, [0.69, 0.69], 'Circle K Go', 'App-Preis laut deiner Beobachtung; Ad-hoc-Preis unbekannt.', 'eigene Beobachtung'),
]
ADAC = {'aral': 0.57}  # ADAC e-Charge (Mitglieder, keine Grundgebühr)

_compiled = [(p, re.compile(p[2])) for p in PRICES]

def price_index(op_name):
    for i, (p, rx) in enumerate(_compiled):
        if rx.search(op_name):
            return i
    return -1

PRICE_STAND = '5.11.2026'  # Datum der Preisrecherche


def export():
    return [{'k': p[0], 'label': p[1], 'adhoc': p[3], 'app': p[4], 'appName': p[5], 'note': p[6], 'src': p[7]} for p in PRICES]
