# Gespann-Lader

Karte der Pkw-Schnelllader, an denen man mit Anhänger **durchfahren** kann – bewertet von der Community.
Statische Website (HTML/JS), Bewertungen in einer Supabase-Datenbank, Hosting auf GitHub Pages. Alles im kostenlosen Rahmen.

```
index.html, style.css, app.js   die App
config.js                       deine Einstellungen (Supabase-Adresse und öffentlicher Schlüssel)
data/                           Ladestationen je Land (data/DE/sites.json) + Autobahnlinien
vendor/                         MapLibre (Karte) und supabase-js, lokal mitgeliefert
supabase/schema.sql             Datenbank-Tabellen und Zugriffsregeln
supabase/import-bewertungen.sql deine 33 Bewertungen aus dem Prototyp
tools/                          Skripte zum Neubauen der Stationsdaten (nicht für die Website nötig)
impressum.html, datenschutz.html Vorlagen – vor dem Veröffentlichen ausfüllen
.github/workflows/keep-alive.yml hält die kostenlose Datenbank wach (optional)
```

Ohne Datenbank läuft die Seite im **Demo-Modus**: alles funktioniert, Bewertungen landen aber nur im eigenen Browser.

---

## Schritt 1 – Datenbank bei Supabase anlegen (ca. 10 Minuten)

1. Auf **supabase.com** ein Konto anlegen (Anmeldung mit GitHub ist am einfachsten).
2. **New project**: Name z. B. `gespann-lader`, ein sicheres Datenbank-Passwort vergeben (wird später nicht gebraucht, aber gut aufheben), **Region: Central EU (Frankfurt)**, Plan: Free.
3. Warten, bis das Projekt bereit ist (1–2 Minuten).
4. Links **SQL Editor** → *New query* → den kompletten Inhalt von `supabase/schema.sql` einfügen → **Run**. Es sollte „Success“ erscheinen.
5. Links **Authentication** → **Sign In / Providers**: *Email* muss aktiviert sein (ist Standard).
6. **Authentication** → **URL Configuration**:
   - *Site URL*: die spätere Adresse der Website, z. B. `https://DEIN-GITHUB-NAME.github.io/gespann-lader/`
   - *Redirect URLs*: dieselbe Adresse noch einmal hinzufügen.
7. Oben im Projekt auf **Connect** klicken und zwei Werte kopieren:
   - **Project URL** (sieht aus wie `https://abcdefgh.supabase.co`)
   - **Publishable key** (beginnt mit `sb_publishable_…`; bei älteren Projekten heißt er *anon public*)
8. Beide Werte in `config.js` eintragen:
   ```js
   supabaseUrl: 'https://abcdefgh.supabase.co',
   supabaseAnonKey: 'sb_publishable_…',
   ```
   Dieser Schlüssel darf öffentlich sein – die Zugriffsregeln in `schema.sql` sorgen dafür, dass jede Person nur ihre eigenen Bewertungen ändern kann.
   **Niemals** den *secret*- oder *service_role*-Schlüssel eintragen.

## Schritt 2 – Website auf GitHub Pages veröffentlichen (ca. 10 Minuten)

1. Auf **github.com** ein Konto anlegen bzw. anmelden.
2. Oben rechts **+** → **New repository**: Name `gespann-lader`, Sichtbarkeit **Public** (GitHub Pages ist für öffentliche Repositorys kostenlos), *Create repository*.
3. Auf der leeren Repository-Seite **uploading an existing file** anklicken.
4. Den **Inhalt** des entpackten Ordners (nicht den Ordner selbst) ins Browserfenster ziehen – also `index.html`, `app.js`, `config.js`, die Ordner `data`, `vendor` usw. Unten *Commit changes*.
   - Der Ordner `.github` ist auf dem Mac/PC oft unsichtbar. Er ist optional, siehe Schritt 5.
5. Im Repository **Settings** → **Pages**: *Source* = *Deploy from a branch*, *Branch* = `main`, Ordner `/ (root)` → *Save*.
6. Nach 1–2 Minuten ist die Seite unter `https://DEIN-GITHUB-NAME.github.io/gespann-lader/` erreichbar. Diese Adresse muss mit der *Site URL* aus Schritt 1.6 übereinstimmen.

Spätere Änderungen: Datei im Repository anklicken → Stift-Symbol → bearbeiten → *Commit changes*. Nach ca. einer Minute ist die Änderung online.

## Schritt 3 – Anmelden und deine alten Bewertungen übernehmen

1. Die Website öffnen → oben rechts das **Personen-Symbol** → E-Mail-Adresse eingeben → *Link senden*.
2. Den Link in der E-Mail öffnen. Du bist jetzt angemeldet (der grüne Punkt am Personen-Symbol zeigt das an).
3. In Supabase **SQL Editor** → *New query* → Inhalt von `supabase/import-bewertungen.sql` einfügen.
4. Im eingefügten Text `DEINE-EMAIL@BEISPIEL.DE` durch die E-Mail-Adresse ersetzen, mit der du dich gerade angemeldet hast → **Run**.
   Die Datei auf GitHub bleibt dabei unverändert – die E-Mail-Adresse nur im SQL Editor eintragen, nicht in die veröffentlichte Datei.
5. Website neu laden: deine 33 Bewertungen sind da.

## Schritt 4 – Bevor du die Seite öffentlich machst

- **E-Mail-Versand einrichten.** Supabase verschickt Anmelde-Links ohne eigenen Mailserver nur an Mitglieder deines Supabase-Teams (also an dich) und höchstens 2 pro Stunde. Für alle anderen braucht es einen eigenen SMTP-Dienst, z. B. **Brevo** (kostenloses Kontingent) oder **Resend**:
  Supabase → **Authentication** → **Emails** → **SMTP Settings** → *Enable custom SMTP* → Zugangsdaten des Dienstes eintragen.
  Danach unter **Authentication** → **Rate Limits** das E-Mail-Limit passend erhöhen (Standard dann 30 pro Stunde).
  Am besten mit einer eigenen Domain als Absender (z. B. `login@gespann-lader.de`).
- **Impressum und Datenschutzerklärung ausfüllen** (`impressum.html`, `datenschutz.html`). Die Dateien sind Vorlagen und keine Rechtsberatung – im Zweifel von einem Generator (z. B. e-recht24) oder einer Fachperson prüfen lassen.
- **Auftragsverarbeitungsvertrag (DPA)** mit Supabase abschließen: Supabase → Organization Settings → Legal Documents.

## Schritt 5 – Datenbank wach halten (optional)

Kostenlose Supabase-Projekte werden nach **7 Tagen ohne Aktivität pausiert** (die Daten bleiben erhalten, die Website zeigt dann aber keine Bewertungen und man kann sich nicht anmelden; im Supabase-Dashboard mit *Resume project* wieder starten). Solange regelmäßig Leute die Seite nutzen, passiert das nicht.

Für die Anfangszeit hält `.github/workflows/keep-alive.yml` die Datenbank wach: GitHub ruft alle drei Tage die Bewertungsstatistik ab. Falls der Ordner `.github` beim Hochladen nicht dabei war:
Repository → **Add file** → **Create new file** → als Namen `.github/workflows/keep-alive.yml` eintippen → Inhalt der Datei einfügen → *Commit changes*.
Unter **Actions** lässt sich der Lauf mit *Run workflow* einmal von Hand testen.

---

## Lokal ausprobieren

Im Ordner ein Terminal öffnen und

```
python3 -m http.server 8000
```

starten, dann `http://localhost:8000` öffnen. (Direkt per Doppelklick auf `index.html` geht es nicht, weil der Browser dann die Datendateien nicht lädt.)
Für die Anmeldung lokal `http://localhost:8000/` zusätzlich unter *Redirect URLs* in Supabase eintragen.

## Daten aktualisieren

Die Stationsdaten stammen aus dem Ladesäulenregister der Bundesnetzagentur. Neu bauen: siehe `tools/README.md`. Danach die neue `data/DE/sites.json` (und ggf. `data/mw.json`) auf GitHub hochladen und dabei die alte ersetzen.

**Weitere Länder:** In `data/countries.json` einen Eintrag ergänzen, z. B. `{ "code": "AT", "name": "Österreich", "file": "data/AT/sites.json" }`, und eine `sites.json` im gleichen Format bereitstellen. Bewertungen sind bereits nach Land getrennt gespeichert (Schlüssel `DE-51.5000_11.9000`).

## Wie die Bewertungen gespeichert werden

- Tabelle `ratings`: eine Bewertung pro Person und Standort (Durchfahrt / nur wenn wenig los / abkoppeln + Notiz bis 300 Zeichen).
- Lesen dürfen alle nur die **Zusammenfassung** (Anzahl je Bewertung) und die Notizen – ohne Namen oder E-Mail-Adressen.
- Ändern und Löschen kann jede Person nur ihre eigenen Bewertungen.
- Meldungen („Falsche Angabe melden“) landen in der Tabelle `reports` und sind nur für dich im Supabase-Dashboard sichtbar (Table Editor).
- Gesperrte oder Spam-Bewertungen löschst du im Table Editor von Hand.

## Quellen und Lizenzen

- Ladestationen: Ladesäulenregister der Bundesnetzagentur, CC BY 4.0 (aufbereitet über ratopi/ladesaeule)
- Hintergrundkarte: OpenFreeMap, Kartendaten © OpenStreetMap-Mitwirkende (ODbL)
- Autobahnachsen: Natural Earth (gemeinfrei)
- MapLibre GL JS (BSD-3-Clause), supabase-js (MIT) – Lizenztexte in `vendor/`
- Preise: eigene Recherche (Ladechef/AFIR-Meldungen der Betreiber, Betreiber-Websites), ohne Gewähr
