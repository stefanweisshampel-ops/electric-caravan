-- =====================================================================
-- Deine bisherigen Bewertungen aus dem Prototyp übernehmen
-- 1. Melde dich zuerst einmal auf deiner neuen Website an (E-Mail-Link).
-- 2. Trage ganz unten bei email = '...' die E-Mail-Adresse ein,
--    mit der du dich angemeldet hast.
-- 3. Dieses Skript im SQL-Editor von Supabase ausführen.
-- Hinweis: Diese Datei nicht mit eingetragener E-Mail-Adresse veröffentlichen.
-- =====================================================================
insert into public.ratings (site_key, country, lat, lon, status, note, site_name, user_id, created_at, updated_at)
select v.site_key, 'DE', v.lat, v.lon, v.status, '', v.site_name, u.id, v.t::timestamptz, v.t::timestamptz
from (values
  ('DE-52.1324_12.7506', 52.13244, 12.75064, 'nein', 'MER Germany', '2026-11-05T21:07:58.447Z'),
  ('DE-52.2668_12.9225', 52.26677, 12.92253, 'nein', 'Tesla Germany GmbH', '2026-11-05T21:07:33.344Z'),
  ('DE-52.4011_12.7944', 52.40113, 12.79443, 'nein', 'Norma Groß Kreutz', '2026-11-05T21:07:02.795Z'),
  ('DE-52.4589_12.9724', 52.45887, 12.97238, 'nein', 'Energie und Wasser Potsdam GmbH', '2026-11-05T21:06:13.883Z'),
  ('DE-52.5338_12.9972', 52.53381, 12.99719, 'eng', 'Wustermark', '2026-11-05T21:05:43.144Z'),
  ('DE-52.5401_12.9776', 52.54009, 12.9776, 'nein', 'Aral Pulse', '2026-11-05T21:04:48.049Z'),
  ('DE-52.5658_12.9754', 52.56583, 12.97538, 'ja', 'Shell Deutschland GmbH', '2026-11-05T21:04:29.564Z'),
  ('DE-52.5823_13.0126', 52.58232, 13.01264, 'eng', 'Vattenfall Smarter Living GmbH', '2026-11-05T21:02:50.840Z'),
  ('DE-52.7098_13.1069', 52.70982, 13.10694, 'ja', 'EWE Go GmbH', '2026-11-05T21:00:06.699Z'),
  ('DE-52.7197_13.0994', 52.71972, 13.09943, 'nein', 'Vattenfall Smarter Living GmbH', '2026-11-05T20:54:53.179Z'),
  ('DE-52.8886_12.8108', 52.88856, 12.81077, 'nein', 'Allego', '2026-11-05T20:54:12.638Z'),
  ('DE-52.9180_12.7844', 52.91803, 12.78437, 'nein', 'EWE Go GmbH', '2026-11-05T20:51:47.731Z'),
  ('DE-52.9182_12.7834', 52.9182, 12.7834, 'eng', 'Shell Deutschland GmbH', '2026-11-05T20:53:00.893Z'),
  ('DE-52.9194_12.7863', 52.91945, 12.78628, 'nein', 'Allego', '2026-11-05T20:51:23.271Z'),
  ('DE-52.9208_12.7864', 52.92077, 12.78635, 'nein', 'Vattenfall Smarter Living GmbH', '2026-11-05T20:50:56.688Z'),
  ('DE-53.0672_12.5330', 53.06716, 12.53299, 'nein', 'Allego', '2026-11-05T20:40:55.791Z'),
  ('DE-53.0674_12.5332', 53.0674, 12.53323, 'nein', 'Tesla Germany GmbH', '2026-11-05T20:40:32.916Z'),
  ('DE-53.0681_12.5333', 53.06811, 12.53325, 'nein', 'Autohof Herzsprung', '2026-11-05T20:40:02.370Z'),
  ('DE-53.1563_12.4822', 53.1563, 12.48221, 'nein', 'Vattenfall Smarter Living GmbH', '2026-11-05T20:53:32.550Z'),
  ('DE-53.1574_12.4512', 53.15744, 12.45124, 'ja', 'Fastned Deutschland GmbH & Co. KG', '2026-11-05T20:38:18.797Z'),
  ('DE-53.1579_12.4551', 53.15792, 12.45514, 'nein', 'Tesla Germany GmbH', '2026-11-05T20:39:01.260Z'),
  ('DE-53.1585_12.4558', 53.15849, 12.45584, 'nein', 'EnBW mobility+ AG und Co.KG', '2026-11-05T20:37:37.967Z'),
  ('DE-53.3612_12.4968', 53.36125, 12.49683, 'nein', 'Shell Deutschland GmbH', '2026-11-05T20:36:48.748Z'),
  ('DE-53.6182_12.3727', 53.61819, 12.37265, 'nein', 'Tesla Germany GmbH', '2026-11-05T20:33:42.275Z'),
  ('DE-53.8413_12.2903', 53.8413, 12.29033, 'nein', 'MER Germany', '2026-11-05T20:33:00.140Z'),
  ('DE-53.8559_13.3337', 53.85593, 13.33371, 'nein', 'E.ON Drive Infrastructure', '2026-11-05T20:29:08.226Z'),
  ('DE-53.9233_13.3320', 53.92327, 13.33201, 'nein', 'Vattenfall Smarter Living GmbH', '2026-11-05T20:28:15.893Z'),
  ('DE-54.0118_12.2001', 54.01184, 12.20013, 'ja', 'EnBW mobility+ AG und Co.KG', '2026-11-05T20:34:35.201Z'),
  ('DE-54.0232_12.2323', 54.02316, 12.23228, 'nein', 'EnBW mobility+ AG und Co.KG', '2026-11-05T20:32:18.525Z'),
  ('DE-54.0293_12.4576', 54.02931, 12.45761, 'nein', 'MER Germany', '2026-11-05T20:36:01.382Z'),
  ('DE-54.0933_13.0878', 54.09327, 13.08778, 'nein', 'Tesla Germany GmbH', '2026-11-05T20:26:25.566Z'),
  ('DE-54.1090_13.0564', 54.10903, 13.05645, 'nein', 'TotalEnergies Charging Solutions', '2026-11-05T20:26:53.222Z'),
  ('DE-54.2704_13.1122', 54.27041, 13.1122, 'nein', 'EnBW mobility+ AG und Co.KG', '2026-11-05T20:31:20.889Z')
) as v(site_key, lat, lon, status, site_name, t)
cross join (select id from auth.users where email = 'DEINE-EMAIL@BEISPIEL.DE') u
on conflict (site_key, user_id) do update
  set status = excluded.status, updated_at = excluded.updated_at;
