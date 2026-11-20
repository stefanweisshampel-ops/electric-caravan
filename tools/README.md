# Stationsdaten neu bauen

Die Website braucht diese Skripte nicht – sie sind nur zum Aktualisieren von `data/DE/sites.json` und `data/mw.json`.

## Voraussetzungen

- Python 3.10 oder neuer
- `pip install shapely`
- In diesem Ordner (`tools/`):
  - `lad.json.gz` – Ladesäulenregister der Bundesnetzagentur, aufbereitet:
    https://ratopi.github.io/ladesaeule/ladesaeulen.json.gz
  - Ordner `ne/` mit zwei Natural-Earth-Dateien (10m, als GeoJSON):
    `ne_10m_roads.geojson` und `ne_10m_admin_0_countries.geojson`
    (z. B. aus https://github.com/nvkelso/natural-earth-vector, Ordner `geojson/`)

## Bauen

```
cd tools
python3 build_de.py
```

Das Skript schreibt `../data/DE/sites.json` und `../data/mw.json` und gibt eine kurze Statistik aus.

## Preise pflegen

Die Betreiberpreise stehen in `prices.py` (eine Zeile pro Betreiber: Name, Suchmuster, Ad-hoc-Preis, App-Preis ohne Grundgebühr, Quelle).
Nach einer Änderung `build_de.py` erneut ausführen. Das Datum der Recherche steht in `PRICE_STAND`.

## Weitere Länder

Für ein neues Land eine `data/XX/sites.json` im selben Format erzeugen (Felder siehe `fields` in der Datei) und in `data/countries.json` eintragen. Gute Quellen sind die nationalen AFIR-Zugangspunkte (in Deutschland die Mobilithek) bzw. OpenStreetMap.
