"""Meldet geänderte Seiten per IndexNow an Bing & Co. (Google nutzt IndexNow nicht).

Aufruf im Workflow nach dem Speichern: python3 tools/indexnow.py
Gemeldet werden alle URLs aus sitemap.xml, deren lastmod heute ist.
Der Schlüssel liegt öffentlich als /<schlüssel>.txt im Wurzelverzeichnis, so verlangt es IndexNow.
"""
import datetime, json, os, re, urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
HOST = 'gespann-lader.de'
KEY = '2389b38155090bf1915a5d372e932f13'


def main():
    sm = open(os.path.join(ROOT, 'sitemap.xml'), encoding='utf-8').read()
    today = datetime.date.today().isoformat()
    urls = [u for u, lm in re.findall(r'<loc>(\S+?)</loc><lastmod>([\d-]+)</lastmod>', sm) if lm == today]
    if not urls:
        print('Keine geänderten Seiten.')
        return
    body = json.dumps({'host': HOST, 'key': KEY, 'keyLocation': f'https://{HOST}/{KEY}.txt', 'urlList': urls[:10000]}).encode()
    req = urllib.request.Request('https://api.indexnow.org/indexnow', data=body,
                                 headers={'Content-Type': 'application/json; charset=utf-8'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f'IndexNow: {len(urls)} URLs gemeldet, Antwort {r.status}')
    except Exception as e:  # nur ein Hinweis, kein Grund für einen roten Workflow
        print('IndexNow fehlgeschlagen:', e)


if __name__ == '__main__':
    main()
