# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import audio
import math
import mfeats
import numpy
import os
import sqlite3
import threading

from utilities import Struct


# the library: every song in the playlists, once a file. found songs go to a tab of their
# own (SEARCH_TITLE, SIMILAR_TITLE), their rows copied from the playlists they came from
SEARCH_TITLE = 'Search'
SIMILAR_TITLE = 'Similar'
# the songs starred (favorite_tracks: their paths, in the order starred), shown in a tab of
# their own as the found ones are
FAVORITES_TITLE = 'Favorite tracks'
# the songs played lately (recent_tracks: their paths, the latest first), as the starred
RECENT_TITLE = 'Recent tracks'
RECENT_LIMIT = 200
TEXT_KEYS = ('filename', 'artist', 'title', 'album', 'genre')
FEATURES = dict()
FEATURES_LOCK = threading.Lock()


def get_camelot(key):
    # (number, letter) of a key in any of the analysis' formats, or None
    code = mfeats.convert_chord_type(key, 2) if key else ''
    if len(code) < 2 or code[:-1].isdigit() is False or code[-1] not in 'AB':
        return None
    return (int(code[:-1]), code[-1])


def is_key_compatible(one, other):
    # the same key, a fifth either way, or its relative (Camelot's neighbours)
    a, b = get_camelot(one), get_camelot(other)
    if a is None or b is None:
        return False
    if a == b:
        return True
    if a[1] == b[1]:
        return (a[0] - b[0]) % 12 in (1, 11)
    return a[0] == b[0]


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def get_grid_tempi():
    # the grid's tempo of every song that has one (finer than the analysis' 0.1 BPM)
    try:
        conn = mfeats.connect_grid()
        rows = conn.execute(f'SELECT mdx, bpm FROM {mfeats.GRID_TABLE} '
                            'WHERE version = ? AND bpm > 0', (mfeats.GRID_VERSION,)).fetchall()
        conn.close()
    except sqlite3.Error:
        return dict()
    return dict(rows)


def collect(listbox, skip_titles=(SEARCH_TITLE, SIMILAR_TITLE, FAVORITES_TITLE,
                                  RECENT_TITLE)):
    '''[Struct] of the library's songs, the first row of each file'''
    tempi = get_grid_tempi()
    songs = list()
    seen = set()
    for listIdx, inner in enumerate(listbox.innerList):
        if inner.title in skip_titles:
            continue
        keys = [v.key for v in inner.columns]
        for item in inner.items:
            values = dict(zip(keys, item))
            path = values.get('path')
            # a station's stream is no song of the library
            if not path or path in seen or audio.is_stream_path(path):
                continue
            seen.add(path)
            tempo = tempi.get(values.get('mdx'), to_float(values.get('tempo')))
            songs.append(Struct(path=path, mdx=values.get('mdx'), values=values,
                                tempo=tempo, key=values.get('key', '')))
    return songs


def is_tempo_in(tempo, low, high, octave):
    if tempo <= 0:
        return False
    tempi = (tempo, tempo * 2, tempo / 2) if octave else (tempo,)
    return any(low <= v <= high for v in tempi)


def search(songs, text='', low=0.0, high=0.0, octave=False, key='', compatible=False,
           genre=''):
    '''the songs matching every condition given (an empty one matches all)'''
    words = [v for v in text.lower().split() if v]
    genre = genre.lower().strip()
    found = list()
    for song in songs:
        values = song.values
        # the folders too: the playlist rows keep no tags, and a library is often kept in
        # folders by genre
        folders = os.path.dirname(song.path).lower()
        if words:
            haystack = ' '.join(str(values.get(k, '')) for k in TEXT_KEYS).lower()
            if any(w not in haystack and w not in folders for w in words):
                continue
        if genre and genre not in str(values.get('genre', '')).lower() and genre not in folders:
            continue
        if (low or high) and is_tempo_in(song.tempo, low or 0.0, high or 999.0, octave) is False:
            continue
        if key:
            if compatible:
                if is_key_compatible(key, song.key) is False:
                    continue
            elif get_camelot(key) != get_camelot(song.key):
                continue
        found.append(song)
    return found


def get_features(mdx):
    '''(energy, dynamics, low, mid, high) of a song's analyzed waveform, or None'''
    with FEATURES_LOCK:
        if mdx in FEATURES:
            return FEATURES[mdx]
    resp = mfeats.getby_key_value('mdx', mdx)
    feature = None
    if resp is not None and audio.is_waveform_3band(resp.waveform):
        wave = resp.waveform.astype(float) / 255.0
        level = wave[:, 1]
        loud = level > level.max() * 0.3
        if loud.sum() > 10:
            feature = numpy.array([level[loud].mean(), level[loud].std(),
                                   wave[loud, 2].mean(), wave[loud, 3].mean(),
                                   wave[loud, 4].mean()])
    with FEATURES_LOCK:
        FEATURES[mdx] = feature
    return feature


def get_tempo_distance(one, other):
    # how far apart in percent, the nearer of the tempo, its double and its half
    if one <= 0 or other <= 0:
        return None
    return min(abs(math.log2(other * ratio / one)) for ratio in (1.0, 2.0, 0.5)) * 100 / 1.44


def similar(songs, target, count=100):
    '''the songs nearest target: tempo (within about 8%), key (the same or a neighbour on the
    Camelot wheel), and the sound (loudness, dynamics, and the low, mid and high shares)'''
    base = get_features(target.mdx)
    features = [get_features(song.mdx) for song in songs]
    known = numpy.array([f for f in features if f is not None])
    spread = known.std(axis=0) + 1e-6 if len(known) > 1 else numpy.ones(5)
    scored = list()
    for song, feature in zip(songs, features):
        if song.path == target.path:
            continue
        distance = get_tempo_distance(target.tempo, song.tempo)
        tempo = 1.0 if distance is None else min(distance / 8.0, 1.0)
        if not target.key or not song.key:
            key = 0.5
        elif get_camelot(target.key) == get_camelot(song.key):
            key = 0.0
        elif is_key_compatible(target.key, song.key):
            key = 0.3
        else:
            key = 1.0
        if base is None or feature is None:
            sound = 0.5
        else:
            sound = min(float(numpy.sqrt((((feature - base) / spread) ** 2).mean())) / 2.0, 1.0)
        scored.append((0.4 * tempo + 0.25 * key + 0.35 * sound, song))
    scored.sort(key=lambda v: v[0])
    return [song for _, song in scored[:count]]


# (read once and kept: the list asks at every drawing, the settings' file opened each time)
FAVORITES = None


def get_favorite_tracks():
    global FAVORITES
    if FAVORITES is None:
        from macroboxlib import GetPreference
        FAVORITES = list(GetPreference('favorite_tracks') or [])
    return list(FAVORITES)


def toggle_favorite_tracks(paths):
    '''the paths starred (none of them was) or let go (one was, or all): True when
    starred'''
    from macroboxlib import SetPreference
    kept = get_favorite_tracks()
    paths = [v for v in paths if v and not audio.is_stream_path(v)]
    if not paths:
        return False
    starring = any(v not in kept for v in paths)
    if starring:
        kept += [v for v in paths if v not in kept]
    else:
        kept = [v for v in kept if v not in paths]
    global FAVORITES
    FAVORITES = list(kept)
    SetPreference('favorite_tracks', kept)
    return starring


def note_recent(path):
    # a song that started playing: first in the recent ones (once), the latest RECENT_LIMIT
    from macroboxlib import GetPreference
    from macroboxlib import SetPreference
    if not path or audio.is_stream_path(path):
        return
    paths = [v for v in (GetPreference('recent_tracks') or []) if v != path]
    SetPreference('recent_tracks', [path] + paths[:RECENT_LIMIT - 1])


def show_recent(listbox):
    # the songs played lately in their tab, the latest first (show_favorites)
    from macroboxlib import GetPreference
    return show_paths(listbox, RECENT_TITLE, GetPreference('recent_tracks') or [])


def show_favorites(listbox):
    '''the starred songs in their tab, in the order starred: their rows as in the playlists
    they are in (a song in none read from its file)'''
    return show_paths(listbox, FAVORITES_TITLE, get_favorite_tracks())


def show_paths(listbox, title, paths):
    # the songs at paths in the tab named title, in that order (show_favorites)
    from macroboxlib import ListBoxColumn
    from macroboxlib import MakeMusicFileItem
    songs = dict((v.path, v) for v in collect(listbox))
    keys = [v.key for v in ListBoxColumn()]
    found = []
    for path in paths:
        song = songs.get(path)
        if song is None:
            item = MakeMusicFileItem(path, 0, ListBoxColumn())
            if item is None:
                continue
            song = Struct(path=path, values=dict(zip(keys, item)))
        found.append(song)
    return show_results(listbox, title, found)


def show_results(listbox, title, songs):
    # the found songs in the tab named title (made, or emptied and filled), in their order
    index = [i for i, v in enumerate(listbox.innerList) if v.title == title]
    if index == []:
        listbox.AddInnerList(title)
        index = len(listbox.innerList) - 1
    else:
        index = index[0]
    inner = listbox.innerList[index]
    keys = [v.key for v in inner.columns]
    items = list()
    for order, song in enumerate(songs, 1):
        values = dict(song.values)
        values['order'] = order
        items.append(tuple(values.get(k, '') for k in keys))
    inner.items = items
    inner.filterCache = None
    inner.filterQuery = None
    inner.selectedItems = []
    orderIdx = keys.index('order') if 'order' in keys else None
    inner.lastSortedColumn = [orderIdx, 1]
    listbox.SetSelectedList(index)
    return index
