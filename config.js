// =====================================================================
// Gespann-Lader – Einstellungen
// Nach dem Anlegen des Supabase-Projekts hier die beiden Werte eintragen
// (Supabase → im Projekt oben auf „Connect“ klicken: „Project URL“ und
// „Publishable key“ – bei älteren Projekten heißt er „anon public“).
// Ohne diese Werte läuft die Seite im Demo-Modus: Bewertungen werden dann
// nur im eigenen Browser gespeichert.
// Der Publishable/anon-Schlüssel darf öffentlich sein; geschützt wird über
// die Zugriffsregeln in supabase/schema.sql. Niemals den „secret“- oder
// „service_role“-Schlüssel hier eintragen!
// =====================================================================
window.GL_CONFIG = {
  supabaseUrl: 'https://fefmwmgbgvznlzpcidbs.supabase.co',
  supabaseAnonKey: 'sb_publishable_3z16j3nbWT8E1QLX4CmRYw__HfmREgu',
  mapStyle: 'https://tiles.openfreemap.org/styles/liberty',
  appName: 'Gespann-Lader',
};
