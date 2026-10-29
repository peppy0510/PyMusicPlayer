# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import addons
import contextlib
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from utilities import get_user_docapp_path


USER_AGENT = 'PyMusicPlayer/1.3.1000 +https://github.com/peppy0510/PyMusicPlayer'
CACHE_SECONDS = 60 * 60 * 24 * 30
TIMEOUT = 15

# seconds between two requests to one service, under each one's published limit
# (Discogs 60/min with a token, AcoustID 3/s, Last.fm 5/s)
INTERVALS = {'discogs': 1.1, 'acoustid': 0.4, 'lastfm': 0.25, 'image': 0.5}
IMAGE_MAX_BYTES = 5 * 1024 * 1024

PREFERENCE_KEYS = ('discogs_token', 'discogs_key', 'discogs_secret',
                   'lastfm_api_key', 'acoustid_client_key')


class WebInfoError(Exception):
    pass


class RateLimiter():

    def __init__(self):
        self.lock = threading.Lock()
        self.last = dict()

    def wait(self, service):
        with self.lock:
            elapsed = time.time() - self.last.get(service, 0)
            if elapsed < INTERVALS[service]:
                time.sleep(INTERVALS[service] - elapsed)
            self.last[service] = time.time()


limiter = RateLimiter()


class Cache():

    def __init__(self, path=None):
        if path is None:
            path = os.path.join(get_user_docapp_path(), 'webinfo.db')
        self.path = path
        self.lock = threading.Lock()
        self.execute('CREATE TABLE IF NOT EXISTS cache '
                     '(key TEXT PRIMARY KEY, body TEXT, date REAL)')

    def execute(self, sql, params=()):
        # sqlite3's own context manager commits but does not close
        with self.lock, contextlib.closing(sqlite3.connect(self.path, timeout=10)) as conn:
            with conn:
                return conn.execute(sql, params).fetchone()

    def get(self, key):
        row = self.execute('SELECT body, date FROM cache WHERE key = ?', (key,))
        if row is None or time.time() - row[1] > CACHE_SECONDS:
            return None
        return json.loads(row[0])

    def set(self, key, body):
        self.execute('INSERT OR REPLACE INTO cache (key, body, date) VALUES (?, ?, ?)',
                     (key, json.dumps(body), time.time()))


def cache_key(service, params):
    query = urllib.parse.urlencode(sorted(params.items()))
    return '%s:%s' % (service, hashlib.sha1(query.encode('utf-8')).hexdigest())


def request_json(service, url, params, headers=None, post=False, cache=None):
    key = cache_key(service, params)
    if cache is not None:
        body = cache.get(key)
        if body is not None:
            return body
    query = urllib.parse.urlencode(params)
    data = None
    if post:
        data = query.encode('utf-8')
    else:
        url = '%s?%s' % (url, query)
    request = urllib.request.Request(url, data=data)
    request.add_header('User-Agent', USER_AGENT)
    request.add_header('Accept', 'application/json')
    for name, value in (headers or dict()).items():
        request.add_header(name, value)
    limiter.wait(service)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as resp:
            body = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as error:
        raise WebInfoError('%s: HTTP %d %s' % (service, error.code, error.reason))
    except Exception as error:
        raise WebInfoError('%s: %s' % (service, error))
    if cache is not None:
        cache.set(key, body)
    return body


def candidate(source, artist='', title='', album='', genre='', year='', score=None, url='',
              duration=None, release='', image=''):
    return dict(source=source, artist=artist or '', title=title or '', album=album or '',
                genre=genre or '', year=str(year or ''), score=score, url=url or '',
                duration=duration or None, release=release or '', image=image or '')


def format_duration(seconds):
    if not seconds:
        return ''
    seconds = int(round(seconds))
    return '%d:%02d' % (seconds // 60, seconds % 60)


def split_artist_title(filename):
    name = os.path.splitext(os.path.basename(filename))[0]
    if ' - ' in name:
        artist, title = name.split(' - ', 1)
        return artist.strip(), title.strip()
    return '', name.strip()


def find_fpcalc():
    # fetched into the user's folder (addons.py), else in assets or on PATH
    path = addons.find_addon('fpcalc.exe')
    if path is not None:
        return path
    if hasattr(sys, '_MEIPASS'):
        assets = os.path.join(sys._MEIPASS, 'assets')
    else:
        assets = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets')
    path = os.path.join(assets, 'dlls', 'fpcalc.exe')
    if os.path.isfile(path):
        return path
    return shutil.which('fpcalc')


def get_fingerprint(path, fpcalc=None):
    fpcalc = fpcalc or find_fpcalc()
    if fpcalc is None:
        raise WebInfoError('acoustid: fpcalc.exe is not in assets/dlls')
    # no console window flashing up from pythonw
    flags = 0x08000000 if sys.platform.startswith('win') else 0
    try:
        resp = subprocess.run([fpcalc, '-json', '-length', '120', path], capture_output=True,
                              timeout=60, creationflags=flags)
        body = json.loads(resp.stdout.decode('utf-8'))
    except Exception as error:
        raise WebInfoError('acoustid: fpcalc failed, %s' % (error))
    return int(body['duration']), body['fingerprint']


def lookup_acoustid(path, client_key, cache=None, fpcalc=None):
    duration, fingerprint = get_fingerprint(path, fpcalc)
    params = dict(client=client_key, duration=duration, fingerprint=fingerprint,
                  meta='recordings releasegroups')
    body = request_json('acoustid', 'https://api.acoustid.org/v2/lookup',
                        params, post=True, cache=cache)
    if body.get('status') != 'ok':
        message = body.get('error', dict()).get('message', 'unknown error')
        raise WebInfoError('acoustid: %s' % (message))
    candidates = list()
    for result in body.get('results', list()):
        for recording in result.get('recordings', list()):
            if 'title' not in recording:
                continue
            artist = ', '.join([v['name'] for v in recording.get('artists', list())])
            groups = recording.get('releasegroups', list())
            album = groups[0].get('title', '') if groups else ''
            url = 'https://musicbrainz.org/recording/%s' % (recording['id'])
            candidates.append(candidate('AcoustID', artist, recording['title'], album,
                                        score=result.get('score'), url=url,
                                        duration=recording.get('duration')))
    return candidates


def get_discogs_auth(keys):
    # a personal access token, or an app's consumer key and secret (enough for the search)
    if keys.get('discogs_token'):
        return 'Discogs token=%s' % (keys['discogs_token'])
    if keys.get('discogs_key') and keys.get('discogs_secret'):
        return 'Discogs key=%s, secret=%s' % (keys['discogs_key'], keys['discogs_secret'])
    return None


def lookup_discogs(artist, title, auth, cache=None):
    # the search has no track lengths; the strict fields first, then one free-text search
    headers = {'Authorization': auth}
    for params in (dict(type='release', artist=artist, track=title, per_page=10),
                   dict(type='release', q=' '.join([v for v in (artist, title) if v]),
                        per_page=10)):
        body = request_json('discogs', 'https://api.discogs.com/database/search',
                            params, headers=headers, cache=cache)
        if body.get('results'):
            break
    candidates = list()
    for result in body.get('results', list()):
        release_artist, _, album = result.get('title', '').partition(' - ')
        if not album:
            release_artist, album = '', release_artist
        genre = (result.get('style') or result.get('genre') or [''])[0]
        url = 'https://www.discogs.com%s' % (result.get('uri', ''))
        catno = result.get('catno', '')
        release = [', '.join((result.get('format') or list())[:2]),
                   (result.get('label') or [''])[0], result.get('country', ''),
                   '' if catno.lower() == 'none' else catno]
        candidates.append(candidate('Discogs', release_artist.strip() or artist, title,
                                    album.strip(), genre, result.get('year'), url=url,
                                    release=' / '.join([v for v in release if v]),
                                    image=result.get('cover_image') or result.get('thumb')))
    return candidates


def lookup_lastfm(artist, title, api_key, cache=None):
    params = dict(method='track.getInfo', artist=artist, track=title,
                  autocorrect=1, api_key=api_key, format='json')
    body = request_json('lastfm', 'https://ws.audioscrobbler.com/2.0/', params, cache=cache)
    if 'error' in body:
        if body['error'] == 6:
            return list()
        raise WebInfoError('lastfm: %s' % (body.get('message', body['error'])))
    track = body.get('track', dict())
    tags = track.get('toptags', dict()).get('tag', list())
    genre = tags[0]['name'] if tags else ''
    # milliseconds, 0 when Last.fm does not know it
    try:
        duration = int(track.get('duration') or 0) / 1000.0
    except Exception:
        duration = None
    album = track.get('album', dict())
    images = [v.get('#text') for v in album.get('image', list()) if v.get('#text')]
    return [candidate('Last.fm', track.get('artist', dict()).get('name', artist),
                      track.get('name', title), album.get('title', ''),
                      genre, url=track.get('url', ''), duration=duration,
                      image=images[-1] if images else '')]


def fetch_image(url, folder=None):
    # the image bytes, from the disk when fetched before
    if folder is None:
        folder = os.path.join(get_user_docapp_path(), 'webinfo_images')
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, hashlib.sha1(url.encode('utf-8')).hexdigest())
    if os.path.isfile(path):
        with open(path, 'rb') as file:
            return file.read()
    request = urllib.request.Request(url)
    request.add_header('User-Agent', USER_AGENT)
    limiter.wait('image')
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as resp:
            data = resp.read(IMAGE_MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        raise WebInfoError('image: HTTP %d %s' % (error.code, error.reason))
    except Exception as error:
        raise WebInfoError('image: %s' % (error))
    if len(data) > IMAGE_MAX_BYTES:
        raise WebInfoError('image: too large')
    with open(path, 'wb') as file:
        file.write(data)
    return data


def lookup(path, artist, title, keys, cache=None):
    # (candidates, errors) from every service with a key; one failing does not stop the rest
    if not artist and not title:
        artist, title = split_artist_title(path)
    candidates = list()
    errors = list()
    jobs = list()
    if keys.get('acoustid_client_key'):
        jobs.append(lambda: lookup_acoustid(path, keys['acoustid_client_key'], cache))
    discogs_auth = get_discogs_auth(keys)
    if title and discogs_auth:
        jobs.append(lambda: lookup_discogs(artist, title, discogs_auth, cache))
    if artist and title and keys.get('lastfm_api_key'):
        jobs.append(lambda: lookup_lastfm(artist, title, keys['lastfm_api_key'], cache))
    for job in jobs:
        try:
            candidates += job()
        except WebInfoError as error:
            errors.append(str(error))
    return candidates, errors
